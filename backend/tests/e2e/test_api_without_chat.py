"""The whole paid path through HTTP with NO chat call: upload, select, readiness, baseline, pilot, quote, approve,
order, authorize, train. Runs on the mock payment double and the local backend."""
import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.deps import get_ctx_factory
from app.integrations.factory import get_storage
from app.integrations.jobs.inline import InlineJobRunner
from app.integrations.training_local.backend import LocalBackend
from app.main import app
from app.routes import projects as project_routes
from app.services import training
from app.services.agent.tools import ToolContext
from app.services.data.samples import churn_csv


@pytest.fixture
def api(session, _payment_double):
    storage = get_storage()
    runner = InlineJobRunner(lambda rid: training.execute_run(session, rid, LocalBackend(), storage, _payment_double), threaded=False)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[project_routes.get_runner] = lambda: runner
    app.dependency_overrides[get_ctx_factory] = lambda: (
        lambda p, approved=frozenset(): ToolContext(session, p, storage, _payment_double, "mock", LocalBackend(), None, set()))
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_full_flow_without_chat(api):
    pid = api.post("/projects", json={"goal": "predict which customers leave"}).json()["id"]
    assert api.get("/projects").json()[0]["id"] == pid
    assert api.get(f"/projects/{pid}/training").json() == {"status": "not_started"}
    assert api.get(f"/projects/{pid}/payment").status_code == 404
    assert api.get(f"/projects/{pid}/messages").json() == []

    # wrong order is refused in plain words
    assert api.post(f"/projects/{pid}/readiness").status_code == 409
    assert api.post(f"/projects/{pid}/baseline").status_code == 409

    cid = api.post(f"/projects/{pid}/data", json={"name": "churn", "csv_text": churn_csv(1500).decode()}).json()["candidate_id"]
    no_target = api.post(f"/projects/{pid}/data/{cid}/select", json={})
    assert no_target.status_code == 400 and "left" in no_target.json()["detail"]
    assert api.post(f"/projects/{pid}/data/{cid}/select", json={"target": "nope"}).status_code == 400
    assert api.post(f"/projects/{pid}/data/nope/select", json={"target": "left"}).status_code == 400
    sel = api.post(f"/projects/{pid}/data/{cid}/select", json={"target": "left"})
    assert sel.status_code == 200 and sel.json()["status"] == "data_chosen" and sel.json()["target"] == "left"
    assert api.post(f"/projects/{pid}/data/{cid}/select", json={"target": "left"}).status_code == 409

    assert api.post(f"/projects/{pid}/baseline").status_code == 409  # readiness first
    rd = api.post(f"/projects/{pid}/readiness").json()
    assert rd["status"] == "readiness_done" and rd["grade"] and {f["kind"] for f in rd["findings"]} <= {"OK", "NOTE"}
    assert api.post(f"/projects/{pid}/readiness").status_code == 409
    bl = api.post(f"/projects/{pid}/baseline").json()
    assert bl["status"] == "baseline_done" and 0 < bl["accuracy"] <= 1 and bl["trust_level"]

    assert api.post(f"/chats/{pid}/pilot", json={"target": 0.6}).json()["eligible"]
    assert api.post(f"/agreements/{pid}/quote").status_code == 200
    first = api.post(f"/projects/{pid}/quote/approve")
    assert first.status_code == 200 and first.json()["approved"] is True
    assert api.post(f"/projects/{pid}/quote/approve").json() == first.json()  # idempotent

    order = api.post("/payments/orders", json={"project_id": pid}).json()
    assert order["state"] == "none" and order["approve_url"]
    by_project = api.get(f"/projects/{pid}/payment").json()
    assert by_project["payment_id"] == order["payment_id"] and by_project["approve_url"] == order["approve_url"]
    assert by_project["project_id"] == pid
    assert api.get(f"/payments/{order['payment_id']}").json()["approve_url"] == order["approve_url"]
    assert api.post(f"/projects/{pid}/train").status_code == 409  # no confirmed hold yet
    assert api.post(f"/payments/{order['payment_id']}/authorize").json() == {"held": True, "state": "held"}

    detail = api.get(f"/projects/{pid}").json()
    assert detail["status"] == "paid" and detail["payment"]["state"] == "held" and detail["run"] is None
    assert detail["dataset"]["target"] == "left" and detail["readiness"]["findings"] and detail["forecast"]["eligible"]

    run = api.post(f"/projects/{pid}/train").json()
    t = api.get(f"/projects/{pid}/training").json()
    assert t["run_id"] == run["run_id"] and t["status"] == "done"
    final = api.get(f"/projects/{pid}").json()
    assert final["status"] == "done" and final["run"] == {"run_id": run["run_id"], "status": "done"}
    assert final["payment"]["state"] in ("released", "fee_captured", "fee_skipped", "compute_captured")
    assert api.get(f"/projects/{pid}/payment").json()["total_charged_cents"] >= 0
