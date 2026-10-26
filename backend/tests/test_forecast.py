"""Free pilot, forecast, locked test set, and the three flow endpoints."""
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_session
from app.deps import get_ctx_factory
from app.models import Forecast
from app.routes import flow as flow_routes
from app.services import analysis, forecast, verify
from app.services.agent.tools import ToolContext
from app.providers.training.local import LocalBackend


def test_extrapolation_is_conservative_and_ordered():
    curve = [(100, 0.70, 0.02), (200, 0.74, 0.02), (400, 0.77, 0.02)]
    p = forecast.extrapolate(curve, 4000, 800, 0.80)
    assert 0.77 <= p.predicted <= 0.77 + 0.5 * (1 - 0.77)  # never assumes the error more than halves
    assert 0 <= p.band_low <= p.predicted <= p.band_high <= 1 and 0 <= p.confidence <= 1


def test_confidence_falls_as_the_target_rises():
    curve = [(100, 0.70, 0.02), (200, 0.74, 0.02), (400, 0.77, 0.02)]
    c = [forecast.extrapolate(curve, 4000, 800, t).confidence for t in (0.7, 0.8, 0.9, 0.99)]
    assert c == sorted(c, reverse=True) and c[0] > 0.9 and c[-1] < 0.05


def test_band_widens_with_distance_from_the_pilot():
    curve = [(100, 0.70, 0.02), (200, 0.74, 0.02), (400, 0.77, 0.02)]
    near, far = forecast.extrapolate(curve, 800, 800, 0.8), forecast.extrapolate(curve, 80_000, 800, 0.8)
    assert far.band_high - far.band_low > near.band_high - near.band_low


def test_no_learning_in_the_curve_means_no_improvement_is_assumed():
    flat = [(100, 0.70, 0.02), (200, 0.70, 0.02), (400, 0.69, 0.02)]
    assert forecast.extrapolate(flat, 4000, 800, 0.8).predicted <= 0.70 + 1e-9 + 0.0


def test_ineligible_reasons_are_plain_and_honest(monkeypatch):
    low = forecast.Prediction(0.70, 0.62, 0.78, 0.05)
    assert "best case" in forecast.not_eligible_reason(low, 0.9, 5000) and "5%" in forecast.not_eligible_reason(low, 0.9, 5000)
    unsure = forecast.Prediction(0.80, 0.60, 0.95, 0.40)
    assert "40%" in forecast.not_eligible_reason(unsure, 0.8, 5000)
    assert forecast.not_eligible_reason(forecast.Prediction(0.9, 0.8, 0.95, 0.9), 0.8, 5000) is None
    assert "too little" in forecast.not_eligible_reason(None, 0.8, 100)
    for text in (forecast.not_eligible_reason(low, 0.9, 5000), forecast.not_eligible_reason(None, 0.8, 100)):
        assert not any(w in text.lower() for w in ("f1", "precision", "train/test", "instance"))


def test_split_is_fixed_and_locked_rows_never_reach_the_work_rows(session, storage, chosen):
    from app.models import DatasetVersion
    v = session.get(DatasetVersion, chosen.chosen_dataset_version_id)
    wk, lk = verify.prepare_split(storage, v.id, v.storage_key, v.target_column)
    first = (storage.get(wk), storage.get(lk))
    assert verify.prepare_split(storage, v.id, v.storage_key, v.target_column) == (wk, lk) and (storage.get(wk), storage.get(lk)) == first
    work, locked = pd.read_csv(storage.path(wk)), pd.read_csv(storage.path(lk))
    assert abs(len(locked) / (len(work) + len(locked)) - verify.LOCKED_SHARE) < 0.02
    key = lambda df: set(map(tuple, df.astype(str).values.tolist()))
    assert not (key(work) & key(locked))


def test_pilot_uses_a_small_share_drops_models_and_costs_nothing(session, storage, chosen):
    f = forecast.run_pilot(session, storage, chosen, 0.6)
    assert 0.03 <= f.pilot["share_of_data"] <= 0.10 and f.pilot["dropped"] and f.pilot["kept"]
    assert len(f.pilot["learning_curve"]) == 3 and 0 <= f.confidence <= 1
    from app.repositories.ledger import LedgerRepository
    assert LedgerRepository(session).balance(chosen.id) == 0


def test_pilot_rejects_a_target_outside_zero_to_one(session, storage, chosen):
    with pytest.raises(forecast.ForecastError):
        forecast.run_pilot(session, storage, chosen, 1.5)


def test_small_data_is_not_eligible(session, storage, project):
    from app.samples import churn_csv
    from app.services import datasets
    c = datasets.add_candidate(session, storage, project, "tiny", "bundled", churn_csv(300))
    datasets.select_candidate(session, storage, project, c.id, "left")
    f = forecast.run_pilot(session, storage, project, 0.6)
    assert not f.eligible and "too little" in f.reason.lower()


def test_verification_is_independent_of_what_the_backend_reports(session, storage, chosen):
    from app.models import DatasetVersion
    v = session.get(DatasetVersion, chosen.chosen_dataset_version_id)
    wk, lk = verify.prepare_split(storage, v.id, v.storage_key, v.target_column)
    res = LocalBackend().run(storage.path(wk), v.target_column, 100)
    out = verify.verify_model(res.model_bytes, storage, lk, v.target_column)
    assert out["rows"] > 0 and 0.0 <= out["value"] <= 1.0
    with pytest.raises(verify.VerificationError):
        verify.verify_model(b"not a model", storage, lk, v.target_column)
    with pytest.raises(verify.VerificationError):
        verify.verify_model(None, storage, lk, v.target_column)


def test_verification_runs_exactly_once_per_run(session, storage, chosen, provider, verdict):
    from tests.test_payments_and_demo import ScriptedBackend, held
    from app.services import training
    held(session, storage, chosen, provider)
    run = training.start_training(session, chosen, backend := ScriptedBackend(cost=10))
    training.execute_run(session, run.id, backend, storage, provider)
    training.execute_run(session, run.id, backend, storage, provider)  # duplicate delivery
    assert verdict["calls"] == 1


def client(session, storage, provider):
    app = FastAPI()
    app.include_router(flow_routes.router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_ctx_factory] = lambda: (
        lambda p, approved=frozenset(): ToolContext(session, p, storage, provider, "mock", LocalBackend(), None, set()))
    return TestClient(app)


def test_flow_endpoints_pilot_forecast_quote(session, storage, chosen, provider):
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    c = client(session, storage, provider)
    assert c.get(f"/jobs/{chosen.id}/forecast").status_code == 404
    assert c.post(f"/agreements/{chosen.id}/quote").status_code == 409  # no pilot yet
    r = c.post(f"/chats/{chosen.id}/pilot", json={"target": 0.6})
    assert r.status_code == 200 and r.json()["eligible"] and r.json()["is_estimate"]
    assert c.get(f"/jobs/{chosen.id}/forecast").json()["forecast_id"] == r.json()["forecast_id"]
    q = c.post(f"/agreements/{chosen.id}/quote").json()
    assert q["cap_cents"] == q["compute_cap_cents"] + q["success_fee_cents"] and q["is_estimate"]
    assert q["success_fee_max_cents"] == q["success_fee_cents"] and q["success_fee_estimate_cents"] <= q["success_fee_max_cents"]
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
    from tests.test_payments_and_demo import ScriptedBackend, held
    from app.services import training
    verdict["value"] = 0.5
    held(session, storage, chosen, provider)
    training.run_training(session, chosen, ScriptedBackend(cost=10), storage, provider)
    assert chosen.status == "done"
    c = client(session, storage, provider)
    r = c.post(f"/chats/{chosen.id}/pilot", json={"target": 0.55})
    assert r.status_code == 200 and chosen.status == "baseline_done"
    assert c.post(f"/agreements/{chosen.id}/quote").status_code in (200, 409)
    assert session.query(Forecast).count() == 2


def test_no_improve_round_after_a_hit(session, storage, chosen, provider, verdict):
    from tests.test_payments_and_demo import ScriptedBackend, held
    from app.services import training
    held(session, storage, chosen, provider)
    training.run_training(session, chosen, ScriptedBackend(cost=10), storage, provider)
    assert client(session, storage, provider).post(f"/chats/{chosen.id}/pilot", json={"target": 0.6}).status_code == 409


CURVE = [(100, 0.70, 0.02), (200, 0.74, 0.02), (400, 0.77, 0.02)]


def test_suggest_target_is_sellable_and_the_highest_such_target():
    t = forecast.suggest_target(CURVE, 4000, 800)
    assert t is not None and 0.5 <= t <= 0.99
    assert forecast.extrapolate(CURVE, 4000, 800, t).confidence >= settings.forecast_min_confidence
    if t < 0.99:
        assert forecast.extrapolate(CURVE, 4000, 800, round(t + 0.01, 2)).confidence < settings.forecast_min_confidence


def test_suggest_target_is_none_when_nothing_is_sellable():
    assert forecast.suggest_target([(100, 0.30, 0.02), (200, 0.30, 0.02), (400, 0.30, 0.02)], 4000, 800) is None


def test_reason_offers_the_suggested_target():
    low = forecast.Prediction(0.70, 0.62, 0.78, 0.05)
    assert "about 74 out of 100" in forecast.not_eligible_reason(low, 0.9, 5000, 0.74)
    assert "honestly offer" not in forecast.not_eligible_reason(low, 0.9, 5000)


def test_data_issues_are_plain_words(session, chosen):
    from app.models import DatasetVersion, InsightReport
    v = session.get(DatasetVersion, chosen.chosen_dataset_version_id)
    session.add(InsightReport(dataset_version_id=v.id, measurements={}, grade="C",
                              findings=[{"kind": "OK", "text": "fine"}, {"kind": "NOTE", "text": "Many rows are missing values"}]))
    chosen.baseline_result = {"accuracy": 0.74, "simple_guess_accuracy": 0.73}
    session.commit()
    issues = forecast.data_issues(session, chosen, v, 100)
    assert "Many rows are missing values" in issues and "fine" not in issues
    assert any("too little data" in i for i in issues) and any("barely beats a simple guess" in i for i in issues)
    assert not any(w in " ".join(issues).lower() for w in ("f1", "precision", "train/test"))
    chosen.baseline_result = {"accuracy": 0.9, "simple_guess_accuracy": 0.5}
    assert not any("barely" in i for i in forecast.data_issues(session, chosen, v, 5000))
