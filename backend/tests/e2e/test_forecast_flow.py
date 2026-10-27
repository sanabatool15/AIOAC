"""The pilot, forecast and quote endpoints, the Improve round, and that the check runs once per run."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_session
from app.db.tables import Forecast
from app.deps import get_ctx_factory
from app.integrations.training_local.backend import LocalBackend
from app.routes import forecast as forecast_routes
from app.routes import quotes as quote_routes
from app.services import training
from app.services.agent.tools import ToolContext
from app.services.data import analysis
from tests.e2e.test_payments_and_demo import ScriptedBackend
from tests.helpers.builders import held


def client(session, storage, provider):
    app = FastAPI()
    app.include_router(forecast_routes.router)
    app.include_router(quote_routes.router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_ctx_factory] = lambda: (
        lambda p, approved=frozenset(): ToolContext(session, p, storage, provider, "mock", LocalBackend(), None, set()))
    return TestClient(app)


def test_endpoints_pilot_forecast_quote(session, storage, chosen, provider):
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    c = client(session, storage, provider)
    assert c.get(f"/jobs/{chosen.id}/forecast").status_code == 404
    assert c.post(f"/agreements/{chosen.id}/quote").status_code == 409  # no pilot yet
    r = c.post(f"/chats/{chosen.id}/pilot", json={"target": 0.6})
    assert r.status_code == 200 and r.json()["eligible"] and r.json()["is_estimate"]
    assert c.get(f"/jobs/{chosen.id}/forecast").json()["forecast_id"] == r.json()["forecast_id"]
    q = c.post(f"/agreements/{chosen.id}/quote").json()
    assert q["cap_cents"] == q["compute_cap_cents"] + q["success_fee_max_cents"] and q["is_estimate"]
    assert q["success_fee_estimate_cents"] <= q["success_fee_max_cents"]
    assert q["terms"] == "You pay compute either way. The success fee only if the target is verified."
    assert c.post(f"/chats/{chosen.id}/pilot", json={"target": 2}).status_code == 422


def test_not_eligible_forecast_cannot_be_quoted(session, storage, chosen, provider):
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    c = client(session, storage, provider)
    r = c.post(f"/chats/{chosen.id}/pilot", json={"target": 0.99}).json()
    assert r["eligible"] is False and r["reason"] and chosen.status == "baseline_done"
    q = c.post(f"/agreements/{chosen.id}/quote")
    assert q.status_code == 409 and q.json()["detail"] == r["reason"]


def test_pilot_before_baseline_is_refused(session, storage, chosen, provider):
    assert client(session, storage, provider).post(f"/chats/{chosen.id}/pilot", json={"target": 0.6}).status_code == 409


def test_improve_round_after_a_miss_runs_a_new_free_pilot(session, storage, chosen, provider, verdict):
    verdict["value"] = 0.5
    held(session, storage, chosen, provider)
    training.run_training(session, chosen, ScriptedBackend(cost=10), storage, provider)
    assert chosen.status == "done"
    c = client(session, storage, provider)
    r = c.post(f"/chats/{chosen.id}/pilot", json={"target": 0.55})
    assert r.status_code == 200 and chosen.status == "baseline_done"
    assert session.query(Forecast).count() == 2


def test_no_improve_round_after_a_hit(session, storage, chosen, provider, verdict):
    held(session, storage, chosen, provider)
    training.run_training(session, chosen, ScriptedBackend(cost=10), storage, provider)
    assert client(session, storage, provider).post(f"/chats/{chosen.id}/pilot", json={"target": 0.6}).status_code == 409


def test_verification_runs_exactly_once_per_run(session, storage, chosen, provider, verdict):
    held(session, storage, chosen, provider)
    run = training.start_training(session, chosen, backend := ScriptedBackend(cost=10))
    training.execute_run(session, run.id, backend, storage, provider)
    training.execute_run(session, run.id, backend, storage, provider)  # duplicate delivery
    assert verdict["calls"] == 1
