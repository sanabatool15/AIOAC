"""'Try a higher target' after a FINISHED run that reached its target: a second round through the real routes."""
import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.db.tables import Forecast, Quote
from app.deps import get_ctx_factory
from app.integrations.training_local.backend import LocalBackend
from app.main import app
from app.repositories import training_runs as runs_repo
from app.routes import projects as project_routes
from app.services import training
from app.services.agent.tools import ToolContext


@pytest.fixture
def api(session, storage, provider, monkeypatch):
    import sys
    monkeypatch.setattr(project_routes, "get_storage", lambda: storage)
    for name, mod in list(sys.modules.items()):  # the routes and the test must talk to the SAME payment double
        if name.startswith("app.") and hasattr(mod, "get_payment_provider"):
            monkeypatch.setattr(mod, "get_payment_provider", lambda: provider)
    queued = []

    class Recording:  # records the run id; the test plays the worker
        stale_after_seconds = 0
        enqueue = staticmethod(queued.append)
        is_active = staticmethod(lambda rid: False)

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[project_routes.get_runner] = lambda: Recording()
    app.dependency_overrides[get_ctx_factory] = lambda: (
        lambda p, approved=frozenset(): ToolContext(session, p, storage, provider, "mock", LocalBackend(), None, set()))
    c = TestClient(app)
    c.queued = queued
    yield c
    for dep in (get_session, project_routes.get_runner, get_ctx_factory):
        app.dependency_overrides.pop(dep, None)


def one_round(api, session, storage, provider, p, target):
    """Pilot, quote, approve, order, authorize, train and settle, all through the real routes."""
    pid = p.id
    r = api.post(f"/chats/{pid}/pilot", json={"target": target})
    assert r.status_code == 200, r.text
    assert r.json()["eligible"], r.json()["reason"]
    q = api.post(f"/agreements/{pid}/quote")
    assert q.status_code == 200, q.text
    assert api.post(f"/projects/{pid}/quote/approve").status_code == 200
    order = api.post("/payments/orders", json={"project_id": pid})
    assert order.status_code == 200, order.text
    assert api.post(f"/payments/{order.json()['payment_id']}/authorize").json()["held"] is True
    t = api.post(f"/projects/{pid}/train")
    assert t.status_code == 200, t.text
    training.execute_run(session, api.queued[-1], LocalBackend(), storage, provider)
    session.refresh(p)
    return api.get(f"/projects/{pid}/training").json()


def test_second_round_after_a_hit_with_a_higher_target(api, session, storage, provider, chosen, verdict):
    pid = chosen.id
    assert api.post(f"/projects/{pid}/readiness").status_code == 200
    assert api.post(f"/projects/{pid}/baseline").status_code == 200
    verdict["value"] = 0.9
    first = one_round(api, session, storage, provider, chosen, 0.6)
    assert first["status"] == "done" and first["result"]["verification"]["passed"] is True and chosen.status == "done"

    # not higher: refused with plain words (both numbers out of 100), nothing changes
    for bad in (0.6, 0.5):
        r = api.post(f"/chats/{pid}/pilot", json={"target": bad})
        assert r.status_code == 400 and "60 out of 100" in r.json()["detail"] and "higher" in r.json()["detail"]
    assert chosen.status == "done" and session.query(Forecast).count() == 1

    # strictly higher: a new round at the free-pilot step; old records stay
    old_quote = session.query(Quote).one().id
    second = one_round(api, session, storage, provider, chosen, 0.65)
    assert second["status"] == "done" and chosen.status == "done"
    assert second["run_id"] != first["run_id"]
    assert session.query(Forecast).count() == 2 and session.query(Quote).count() == 2
    assert session.query(Quote).filter(Quote.id == old_quote).one().approved_at is not None
    versions = api.get(f"/projects/{pid}/model/versions").json()
    assert [v["version_no"] for v in versions] == [2, 1]
    assert len(runs_repo.models_for_project(session, pid)) == 2


def test_nothing_to_start_a_round_from_before_a_run(api, session, storage, provider, chosen):
    r = api.post(f"/chats/{chosen.id}/pilot", json={"target": 0.9})
    assert r.status_code == 409  # not at baseline_done and not done: the existing gate message
