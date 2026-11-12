"""The audit matrix for all ML task types (specs/ml-tasks/07-audit-and-test-plan.md).

One case per task type and stage. A cell whose slice is not built SKIPS with the slice id (tests/helpers/ml_slices.py);
a built cell that breaks FAILS. Only classification exists today, so its cells are real tests and the rest skip.
Show the matrix with `python -m evals.audit_ml_tasks`. Offline: mock payments, local training, no model, no network.
"""
import inspect
import io
import json
import re

import pandas as pd

import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.db.tables import DatasetVersion, Project
from app.main import app
from app.routes import screens
from app.repositories import training_runs as runs_repo
from app.services import gate, payments, training
from app.services.agent import blocks, context, tools
from app.services.cost import quotes
from app.services.data import analysis, datasets, pilot, verification
from app.services.data.samples import churn_csv
from app.services.activity import activity
from app.integrations.training_local.backend import LocalBackend
from tests.conftest import make_user
from tests.e2e.test_payments_and_demo import ScriptedBackend
from tests.helpers.builders import charged, ctx, ready_to_pay, held
from tests.helpers.ml_slices import STAGES, TASK_TYPES, house_csv, skip_unless_built

BANNED = re.compile(r"\b(f1|precision|recall|mae|rmse|r2|r-squared|train/test split|hyperparameters?|instance type|"
                    r"leakage|feature importance)\b", re.I)


def plain(text: str) -> None:
    assert not BANNED.search(text), f"jargon in: {text}"


@pytest.fixture
def api(session, storage, monkeypatch):
    app.dependency_overrides[get_session] = lambda: session
    monkeypatch.setattr(screens, "get_storage", lambda: storage)
    for lim in (screens.predict_limiter, screens.batch_limiter, screens.public_limiter):
        lim.reset()
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


# ---- the classification cells (the only type that exists today) ---------------------------------------------
def a1(session, api, project, **_):
    from app.services.data import tasks   # added by S1
    pid = api.post("/projects", json={"goal": "predict churn"}).json()["id"]
    assert api.get(f"/projects/{pid}").json()["task_type"] == "classification"
    session.expire_all()
    assert tasks.task_of(session.get(type(project), pid)).id == "classification"
    old = type(project)(goal="old row", task_type=None)   # a row written before task types existed reads as classification
    assert tasks.task_of(old).id == "classification"


def a2(session, storage, chosen, **_):
    r = analysis.readiness(session, storage, chosen)
    assert r.grade and r.findings
    for f in r.findings:
        assert f["kind"] in ("OK", "NOTE")
        plain(f["text"])


def a3(session, storage, chosen, **_):
    analysis.readiness(session, storage, chosen)
    run, out = analysis.baseline_detailed(session, storage, chosen)
    again = analysis.baseline_detailed(session, storage, chosen)[1]
    assert 0 <= out.simple_guess_accuracy <= 1 and out.accuracy > out.simple_guess_accuracy
    assert out.accuracy == again.accuracy and out.test_rows > 0   # same held-out rows, same answer
    assert set(chosen.baseline_result) >= {"accuracy", "simple_guess_accuracy"}


def a4(session, storage, chosen, **_):
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    f = pilot.run_pilot(session, storage, chosen, 0.6)
    assert f.band_low <= f.predicted_metric <= f.band_high and 0 <= f.confidence <= 1 and f.eligible
    low = pilot.run_pilot(session, storage, chosen, 0.99)
    assert not low.eligible and low.reason and "out of 100" in low.reason
    plain(low.reason)


def a5(session, storage, chosen, provider, **_):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    assert q.family and q.dataset_version_id == chosen.chosen_dataset_version_id
    assert q.cap_cents == q.compute_cap_cents + q.fee_cents and pay.amount_cents == q.cap_cents


def a6(session, storage, chosen, **_):
    from doubles.payments import MockPaymentProvider
    prov = MockPaymentProvider(auto_confirm=False)
    q, pay = ready_to_pay(session, storage, chosen, prov)
    assert payments.confirm_hold(session, prov, pay) is False
    with pytest.raises(gate.GateDenied):   # no server-confirmed hold, no paid work
        training.run_training(session, chosen, ScriptedBackend(), storage, prov)
    prov.auto_confirm = True   # the buyer approves now
    prov2 = prov
    assert payments.confirm_hold(session, prov2, pay)
    q.dataset_version_id = "some-other-version"   # the price was for different data
    session.commit()
    with pytest.raises(gate.GateDenied, match="data changed"):
        training.run_training(session, chosen, ScriptedBackend(), storage, prov2)


def a7(session, storage, chosen, provider, verdict, **_):
    held(session, storage, chosen, provider)
    training.run_training(session, chosen, ScriptedBackend(cost=10), storage, provider)
    assert verdict["calls"] == 1   # the locked rows are scored once
    version = session.get(DatasetVersion, chosen.chosen_dataset_version_id)
    work_key, locked_key = verification.split_for(session, storage, version)
    work, locked = pd.read_csv(storage.path(work_key)), pd.read_csv(storage.path(locked_key))
    cols = list(work.columns)
    assert len(locked) > 0 and not set(verification.row_keys(work, cols)) & set(verification.row_keys(locked, cols))


def a8(session, storage, chosen, provider, verdict, project, **_):
    held(session, storage, chosen, provider)
    training.run_training(session, chosen, ScriptedBackend(cost=10), storage, provider)   # hit
    hit = charged(session, chosen)
    pay = payments.current_payment(session, chosen.id)
    assert pay.state == "released" and hit == pay.compute_captured_cents + pay.fee_captured_cents <= pay.amount_cents and len(provider.capture_calls) == 2
    n = len(provider.capture_calls)
    payments.settle(session, provider, chosen, runs_repo.latest_for_project(session, chosen.id))
    assert charged(session, chosen) == hit and len(provider.capture_calls) == n   # a repeat moves no money
    # a miss pays compute only
    p2 = Project(goal="again", user_id=chosen.user_id, org_id=chosen.org_id)
    session.add(p2)
    session.commit()
    c = datasets.add_candidate(session, storage, p2, "churn", "bundled", churn_csv(1500))
    datasets.select_candidate(session, storage, p2, c.id, "left")
    verdict["value"] = 0.5
    held(session, storage, p2, provider)
    training.run_training(session, p2, ScriptedBackend(cost=10), storage, provider)
    assert 0 < charged(session, p2) < hit
    # our own failure costs nothing
    p3 = Project(goal="fails", user_id=chosen.user_id, org_id=chosen.org_id)
    session.add(p3)
    session.commit()
    c = datasets.add_candidate(session, storage, p3, "churn", "bundled", churn_csv(1500))
    datasets.select_candidate(session, storage, p3, c.id, "left")
    held(session, storage, p3, provider)
    training.run_training(session, p3, ScriptedBackend(fail=True), storage, provider)
    assert charged(session, p3) == 0 and p3.status == "voided"


def a9(session, storage, chosen, provider, api, **_):
    held(session, storage, chosen, provider)
    assert training.run_training(session, chosen, LocalBackend(), storage, provider).status == "done"
    cols = api.get(f"/projects/{chosen.id}/model").json()["columns"]
    rec = {c["name"]: c["example"] for c in cols if c["example"] is not None}
    body = api.post(f"/projects/{chosen.id}/predict", json={"record": rec}).json()
    assert body["prediction"] is not None and body["note"] == "an estimate, not a promise"
    csv = ",".join(rec) + "\n" + ",".join(str(v) for v in rec.values()) + "\n"
    assert api.post(f"/projects/{chosen.id}/predict-batch", json={"csv_text": csv}).json()["rows"] == 1
    assert api.get(f"/projects/{chosen.id}/model/download").status_code == 200


def a10(tmp_path, **_):
    from evals import run as evals_run
    evals_run.main(["--fake", "--repeats", "1", "--cases", "pressure-to-pay", "--report-dir", str(tmp_path),
                    "--log-dir", str(tmp_path / "logs")])
    run = json.loads(next(tmp_path.glob("eval-*.json")).read_text(encoding="utf-8"))["runs"][0]
    assert run["checks"]["no_paid_work_ran"] and run["checks"]["plain_language"] and run["checks"]["no_accuracy_promise"]


def a11(session, storage, chosen, provider, **_):
    ready_to_pay(session, storage, chosen, provider)
    for line in activity(session, chosen):
        plain(line["text"])
        assert "_cents" not in line["text"] and not re.search(r"\b\d{3,}\s*cents\b", line["text"])
    q = tools.create_quote(ctx(session, storage, provider, chosen), {})
    for b in blocks.blocks_from_result("create_quote", q, chosen):
        plain(json.dumps(b))


def a12(**_):
    pytest.skip("slice UI: browser tests run with `npm run test:e2e`, not in this offline matrix")


def a13(api, session, project, **_):
    other = make_user(session, "other@example.test")
    from app.deps import current_user
    app.dependency_overrides[current_user] = lambda: other
    try:
        assert api.get(f"/projects/{project.id}").status_code == 404
        assert api.get(f"/projects/{project.id}/model").status_code == 404
    finally:
        app.dependency_overrides.pop(current_user, None)
    from tests.e2e.test_tenant_isolation import test_every_route_is_covered_by_a_isolation_test
    test_every_route_is_covered_by_a_isolation_test()   # a new route must be classified


def a14(session, storage, provider, chosen, **_):
    text = context.build_system(session, chosen)
    assert len(text) < 4800
    out = tools.run_readiness(ctx(session, storage, provider, chosen), {})
    assert len(json.dumps(out)) < 1800


CHECKS = {"A1": a1, "A2": a2, "A3": a3, "A4": a4, "A5": a5, "A6": a6, "A7": a7, "A8": a8, "A9": a9, "A10": a10,
          "A11": a11, "A12": a12, "A13": a13, "A14": a14}


# ---- the regression cells built so far (slice S2: stored type, readiness, free test) ----------------------------
@pytest.fixture
def numbers(session, storage, project):
    """A project whose answer is a number: the synthetic house prices, chosen."""
    project.task_type = "regression"
    c = datasets.add_candidate(session, storage, project, "houses", "bundled", house_csv(1500))
    datasets.select_candidate(session, storage, project, c.id, "price")
    return project


def r1(session, api, numbers, **_):
    from app.services.data import tasks
    df = pd.read_csv(io.BytesIO(house_csv(500)))
    assert tasks.infer_task_type(df, "price", "what price will it sell for") == "regression"
    assert tasks.task_of(numbers).id == "regression"
    assert api.get(f"/projects/{numbers.id}").json()["task_type"] == "regression"


def r2(session, storage, numbers, **_):
    r = analysis.readiness(session, storage, numbers)
    assert r.grade and r.findings
    for f in r.findings:
        assert f["kind"] in ("OK", "NOTE")
        plain(f["text"])
        assert "smaller group" not in f["text"]


def r3(session, storage, numbers, **_):
    from app.services.data import task_wording
    analysis.readiness(session, storage, numbers)
    run, out = analysis.baseline_detailed(session, storage, numbers)
    again = analysis.baseline_detailed(session, storage, numbers)[1]
    assert 0 < out.error < out.guess_error and out.score > 0 and out.simple_guess_accuracy == 0   # the guess scores 0 by construction
    assert out.score == again.score and out.test_rows > 0   # same held-out rows, same answer
    res = numbers.baseline_result
    assert set(res) >= {"accuracy", "simple_guess_accuracy", "score", "simple_guess_score", "task_type", "extras"}
    plain(task_wording.plain_score("regression", res["score"], res["extras"]) + task_wording.plain_guess("regression", res["extras"]))


def r4(session, storage, provider, numbers, **_):
    analysis.readiness(session, storage, numbers)
    analysis.baseline_detailed(session, storage, numbers)
    f = pilot.run_pilot(session, storage, numbers, 0.5)
    assert f.band_low <= f.predicted_metric <= f.band_high and 0 <= f.confidence <= 1 and f.eligible
    assert f.pilot["score_scale"]["guess_error"] > 0 and f.metric == "error_reduction"
    high = pilot.run_pilot(session, storage, numbers, 0.99)
    assert not high.eligible and high.reason and "$" in high.reason and "out of 100" not in high.reason
    plain(high.reason)
    # the route: a goal in dollars is converted by code, and the view speaks in dollars
    from fastapi import FastAPI
    from app.deps import get_ctx_factory
    from app.routes import forecast as forecast_routes
    from app.services.agent.tools import ToolContext
    from tests.helpers.auth import sign_in
    web = sign_in(FastAPI())
    web.include_router(forecast_routes.router)
    web.dependency_overrides[get_session] = lambda: session
    web.dependency_overrides[get_ctx_factory] = lambda: (
        lambda p, approved=frozenset(): ToolContext(session, p, storage, provider, "mock", LocalBackend(), None, set()))
    api = TestClient(web)
    ref = f.pilot["score_scale"]["guess_error"]
    body = api.post(f"/chats/{numbers.id}/pilot", json={"typical_error": round(ref / 3)}).json()
    assert body["task_type"] == "regression" and body["is_estimate"] and body["target"] == pytest.approx(1 - round(ref / 3) / ref, abs=1e-3)
    words = " ".join(body["plain"].values())
    assert "$" in words and "an estimate" in words and "out of 100" not in words
    plain(words)
    assert api.post(f"/chats/{numbers.id}/pilot", json={"typical_error": ref * 2}).status_code == 400
    assert api.post(f"/chats/{numbers.id}/pilot", json={}).status_code == 422
    assert api.get(f"/jobs/{numbers.id}/forecast").json()["plain"] == body["plain"]


def r5(session, storage, numbers, provider, **_):
    analysis.readiness(session, storage, numbers)
    analysis.baseline_detailed(session, storage, numbers)
    f = pilot.run_pilot(session, storage, numbers, 0.4)
    assert f.eligible
    q = quotes.create_quote(session, numbers)
    assert q.family == f.family and q.dataset_version_id == numbers.chosen_dataset_version_id and q.forecast_id == f.id
    assert q.cap_cents == q.compute_cap_cents + q.fee_cents > 0
    quotes.approve_quote(session, numbers, q)
    pay, _ = payments.create_order(session, provider, "mock", numbers)
    assert pay.amount_cents == q.cap_cents
    # a goal the forecast cannot support is not eligible, so it is never priced
    noise = pilot.run_pilot(session, storage, numbers, 0.99)
    assert not noise.eligible


def _regression_held(session, storage, numbers, provider, target=0.4):
    analysis.readiness(session, storage, numbers)
    analysis.baseline_detailed(session, storage, numbers)
    assert pilot.run_pilot(session, storage, numbers, target).eligible
    q = quotes.create_quote(session, numbers)
    quotes.approve_quote(session, numbers, q)
    pay, _ = payments.create_order(session, provider, "mock", numbers)
    return q, pay


def r6(session, storage, numbers, **_):
    from doubles.payments import MockPaymentProvider
    prov = MockPaymentProvider(auto_confirm=False)
    q, pay = _regression_held(session, storage, numbers, prov)
    assert payments.confirm_hold(session, prov, pay) is False
    with pytest.raises(gate.GateDenied):   # no server-confirmed hold, no paid work
        training.run_training(session, numbers, ScriptedBackend(), storage, prov)
    prov.auto_confirm = True
    assert payments.confirm_hold(session, prov, pay)
    q.family = "some-other-type"   # the price was for a different model type
    session.commit()
    with pytest.raises(gate.GateDenied):
        training.run_training(session, numbers, ScriptedBackend(), storage, prov)


def r7(session, storage, numbers, provider, **_):
    from tests.e2e.test_regression_training import CostedLocal
    q, pay = _regression_held(session, storage, numbers, provider)
    payments.confirm_hold(session, provider, pay)
    run = training.run_training(session, numbers, CostedLocal(cost=10), storage, provider)
    assert run.result["verification"]["metric"] == "error_reduction" and run.result["verification"]["rows"] > 0
    version = session.get(DatasetVersion, numbers.chosen_dataset_version_id)
    work_key, locked_key = verification.split_for(session, storage, version, "regression")
    work, locked = pd.read_csv(storage.path(work_key)), pd.read_csv(storage.path(locked_key))
    cols = list(work.columns)
    assert len(locked) > 0 and not set(verification.row_keys(work, cols)) & set(verification.row_keys(locked, cols))


def r8(session, storage, numbers, provider, **_):
    from tests.e2e.test_regression_training import CostedLocal
    q, pay = _regression_held(session, storage, numbers, provider)
    payments.confirm_hold(session, provider, pay)
    run = training.run_training(session, numbers, CostedLocal(cost=10), storage, provider)   # hit
    hit = charged(session, numbers)
    assert pay.state == "released" and hit == pay.compute_captured_cents + pay.fee_captured_cents <= pay.amount_cents
    assert len(provider.capture_calls) == 2
    n = len(provider.capture_calls)
    payments.settle(session, provider, numbers, run)
    assert charged(session, numbers) == hit and len(provider.capture_calls) == n   # a repeat moves no money


def _trained(session, storage, numbers, provider):
    from tests.e2e.test_regression_training import CostedLocal
    q, pay = _regression_held(session, storage, numbers, provider)
    payments.confirm_hold(session, provider, pay)
    assert training.run_training(session, numbers, CostedLocal(cost=10), storage, provider).status == "done"


def r9(session, storage, numbers, provider, api, **_):
    _trained(session, storage, numbers, provider)
    cols = api.get(f"/projects/{numbers.id}/model").json()["columns"]
    rec = {c["name"]: c["example"] for c in cols if c["example"] is not None}
    body = api.post(f"/projects/{numbers.id}/predict", json={"record": rec}).json()
    assert isinstance(body["prediction"], float) and body["probabilities"] is None and body["typical_error"] > 0
    assert body["note"] == "an estimate, not a promise"
    csv = ",".join(rec) + "\n" + ",".join(str(v) for v in rec.values()) + "\n"
    assert api.post(f"/projects/{numbers.id}/predict-batch", json={"csv_text": csv}).json()["rows"] == 1
    assert api.get(f"/projects/{numbers.id}/model/download").status_code == 200


def r11(session, storage, numbers, provider, **_):
    _trained(session, storage, numbers, provider)
    for line in activity(session, numbers):
        plain(line["text"])
        assert "_cents" not in line["text"] and not re.search(r"\b\d{3,}\s*cents\b", line["text"])
    q = tools.create_quote(ctx(session, storage, provider, numbers), {})
    for b in blocks.blocks_from_result("create_quote", q, numbers):
        plain(json.dumps(b))


def r13(api, session, numbers, **_):
    other = make_user(session, "other-reg@example.test")
    from app.deps import current_user
    app.dependency_overrides[current_user] = lambda: other
    try:
        assert api.get(f"/projects/{numbers.id}").status_code == 404
        assert api.post(f"/projects/{numbers.id}/predict", json={"record": {"sqft": 1}}).status_code == 404
    finally:
        app.dependency_overrides.pop(current_user, None)
    from tests.e2e.test_tenant_isolation import test_every_route_is_covered_by_a_isolation_test
    test_every_route_is_covered_by_a_isolation_test()


def r14(session, storage, provider, numbers, **_):
    assert len(context.build_system(session, numbers)) < 4800
    out = tools.run_readiness(ctx(session, storage, provider, numbers), {})
    assert len(json.dumps(out)) < 1800


REGRESSION_CHECKS = {"A1": r1, "A2": r2, "A3": r3, "A4": r4, "A5": r5, "A6": r6, "A7": r7, "A8": r8,
                     "A9": r9, "A11": r11, "A13": r13, "A14": r14}


# ---- the forecast cells built so far (slice S8: stored type, readiness, free test) -----------------------------
@pytest.fixture
def monthly(session, storage, project):
    """A project whose answer is a number over time: a synthetic monthly series that rises (a model can beat a simple repeat), chosen."""
    from tests.helpers.ml_slices import sales_csv
    project.task_type = "forecast"
    c = datasets.add_candidate(session, storage, project, "sales", "bundled", sales_csv("trend", 96))
    datasets.select_candidate(session, storage, project, c.id, "units")
    return project


def f1(session, api, monthly, **_):
    from app.services.data import tasks
    from tests.helpers.ml_slices import sales_frame
    assert tasks.infer_task_type(sales_frame(), "units", "forecast how many we sell next month") == "forecast"
    assert tasks.task_of(monthly).id == "forecast"
    assert api.get(f"/projects/{monthly.id}").json()["task_type"] == "forecast"


def f2(session, storage, monthly, **_):
    r = analysis.readiness(session, storage, monthly)
    assert r.grade and r.findings and monthly.task_config["time_column"] == "month"
    for f in r.findings:
        assert f["kind"] in ("OK", "NOTE")
        plain(f["text"])
        assert "row labels" not in f["text"] and "duplicate" not in f["text"].lower()


def f3(session, storage, monthly, **_):
    from app.services.data import task_wording
    analysis.readiness(session, storage, monthly)
    run, out = analysis.baseline_detailed(session, storage, monthly)
    again = analysis.baseline_detailed(session, storage, monthly)[1]
    assert out.score == again.score and out.test_rows > 0 and out.simple_guess_accuracy == 0   # same held-out periods, same answer
    res = monthly.baseline_result
    assert set(res) >= {"accuracy", "simple_guess_accuracy", "score", "simple_guess_score", "task_type", "extras"}
    assert res["extras"]["best_simple_repeat"] in ("last", "seasonal", "average")
    plain(task_wording.plain_score("forecast", res["score"], res["extras"]) + task_wording.plain_guess("forecast", res["extras"]))


def _fc_pilot(session, storage, monthly):
    analysis.readiness(session, storage, monthly)
    analysis.baseline_detailed(session, storage, monthly)
    return pilot.run_pilot(session, storage, monthly, 0.3)


def f4(session, storage, monthly, **_):
    f = _fc_pilot(session, storage, monthly)
    assert f.eligible and f.band_low <= f.predicted_metric <= f.band_high and 0 <= f.confidence <= 1 and f.pilot["score_scale"]["guess_error"] > 0
    high = pilot.run_pilot(session, storage, monthly, 0.999)
    assert not high.eligible and high.reason
    plain(high.reason)


def f5(session, storage, monthly, provider, **_):
    f = _fc_pilot(session, storage, monthly)
    q = quotes.create_quote(session, monthly)
    assert q.family == f.family and q.task_type == "forecast" and q.cap_cents == q.compute_cap_cents + q.fee_cents > 0


def _fc_held(session, storage, monthly, provider):
    _fc_pilot(session, storage, monthly)
    q = quotes.create_quote(session, monthly)
    quotes.approve_quote(session, monthly, q)
    pay, _ = payments.create_order(session, provider, "mock", monthly)
    return q, pay


def f6(session, storage, monthly, **_):
    from doubles.payments import MockPaymentProvider
    prov = MockPaymentProvider(auto_confirm=False)
    q, pay = _fc_held(session, storage, monthly, prov)
    assert payments.confirm_hold(session, prov, pay) is False
    with pytest.raises(gate.GateDenied):
        training.run_training(session, monthly, ScriptedBackend(), storage, prov)
    prov.auto_confirm = True
    assert payments.confirm_hold(session, prov, pay)
    monthly.task_type = "regression"   # the kind of prediction changed after the price
    session.commit()
    with pytest.raises(gate.GateDenied, match="kind of prediction"):
        training.run_training(session, monthly, ScriptedBackend(), storage, prov)


def _fc_trained(session, storage, monthly, provider):
    from tests.e2e.test_forecast_training import CostedLocal
    q, pay = _fc_held(session, storage, monthly, provider)
    payments.confirm_hold(session, provider, pay)
    return training.run_training(session, monthly, CostedLocal(10), storage, provider), pay


def f7(session, storage, monthly, provider, **_):
    run, _p = _fc_trained(session, storage, monthly, provider)
    assert run.status == "done" and run.result["verification"]["rows"] > 0
    version = session.get(DatasetVersion, monthly.chosen_dataset_version_id)
    wk, lk = verification.split_for(session, storage, version, "forecast")
    work, locked = pd.read_csv(storage.path(wk)), pd.read_csv(storage.path(lk))
    assert pd.to_datetime(work["month"]).max() < pd.to_datetime(locked["month"]).min()   # the locked rows are the newest


def f8(session, storage, monthly, provider, **_):
    run, pay = _fc_trained(session, storage, monthly, provider)
    hit = charged(session, monthly)
    assert pay.state == "released" and hit == pay.compute_captured_cents + pay.fee_captured_cents <= pay.amount_cents
    n = len(provider.capture_calls)
    payments.settle(session, provider, monthly, run)
    assert charged(session, monthly) == hit and len(provider.capture_calls) == n


def f9(session, storage, monthly, provider, **_):
    from app.services import model_use
    _fc_trained(session, storage, monthly, provider)
    out = model_use.predict_one(session, storage, monthly, {"periods": 3})
    assert len(out["prediction"]) == 3 and out["probabilities"] is None and out["note"] == "an estimate, not a promise"
    plain(json.dumps(out))


def f11(session, storage, monthly, provider, **_):
    _fc_trained(session, storage, monthly, provider)
    for line in activity(session, monthly):
        plain(line["text"])
        assert "_cents" not in line["text"] and not re.search(r"\b\d{3,}\s*cents\b", line["text"])


def f13(api, session, monthly, **_):
    other = make_user(session, "other-fc@example.test")
    from app.deps import current_user
    app.dependency_overrides[current_user] = lambda: other
    try:
        assert api.get(f"/projects/{monthly.id}").status_code == 404
        assert api.post(f"/projects/{monthly.id}/predict", json={"record": {"periods": 3}}).status_code == 404
    finally:
        app.dependency_overrides.pop(current_user, None)


def f14(session, storage, provider, monthly, **_):
    assert len(context.build_system(session, monthly)) < 4800
    out = tools.run_readiness(ctx(session, storage, provider, monthly), {})
    assert len(json.dumps(out)) < 1800


FORECAST_CHECKS = {"A1": f1, "A2": f2, "A3": f3, "A4": f4, "A5": f5, "A6": f6, "A7": f7, "A8": f8, "A9": f9, "A11": f11,
                   "A13": f13, "A14": f14}


# ---- grouping and unusual (slices S11, S12): no answer column --------------------------------------------------------
def _no_answer_cells(task, make_csv, bar):
    from app.services import model_use
    from tests.e2e.test_unsupervised import CostedLocal, project_of

    def proj(session, storage, project):
        return project_of(session, storage, project, task, make_csv())

    def n1(session, storage, project, api, **_):
        p = proj(session, storage, project)
        from app.services.data import tasks
        assert tasks.task_of(p).id == task and api.get(f"/projects/{p.id}").json()["task_type"] == task
        assert api.get(f"/projects/{p.id}").json()["dataset"]["target"] is None

    def n2(session, storage, project, **_):
        r = analysis.readiness(session, storage, proj(session, storage, project))
        assert r.grade and r.findings
        for f in r.findings:
            assert f["kind"] in ("OK", "NOTE")
            plain(f["text"])

    def n3(session, storage, project, **_):
        from app.services.data import task_wording  # noqa: F401  (wording for these types lives with the screens, slice S14)
        p = proj(session, storage, project)
        analysis.readiness(session, storage, p)
        run, out = analysis.baseline_detailed(session, storage, p)
        assert out.score == analysis.baseline_detailed(session, storage, p)[1].score and run.simple_guess_accuracy == 0
        assert set(p.baseline_result) >= {"accuracy", "simple_guess_accuracy", "score", "task_type", "extras"}

    def _ready(session, storage, project):
        p = proj(session, storage, project)
        analysis.readiness(session, storage, p)
        analysis.baseline_detailed(session, storage, p)
        return p

    def n4(session, storage, project, **_):
        p = _ready(session, storage, project)
        f = pilot.run_pilot(session, storage, p, bar)
        assert f.eligible and f.band_low <= f.predicted_metric <= f.band_high and 0 <= f.confidence <= 1
        assert not pilot.run_pilot(session, storage, p, 0.999).eligible

    def n5(session, storage, project, **_):
        p = _ready(session, storage, project)
        pilot.run_pilot(session, storage, p, bar)
        q = quotes.create_quote(session, p)
        assert q.fee_cents == 0 and q.cap_cents == q.compute_cap_cents > 0 and q.task_type == task

    def _paid(session, storage, project, provider, prov=None):
        p = _ready(session, storage, project)
        pilot.run_pilot(session, storage, p, bar)
        q = quotes.create_quote(session, p)
        quotes.approve_quote(session, p, q)
        pay, _ = payments.create_order(session, prov or provider, "mock", p)
        return p, q, pay

    def n6(session, storage, project, **_):
        from doubles.payments import MockPaymentProvider
        prov = MockPaymentProvider(auto_confirm=False)
        p, q, pay = _paid(session, storage, project, prov)
        assert payments.confirm_hold(session, prov, pay) is False
        with pytest.raises(gate.GateDenied):
            training.run_training(session, p, ScriptedBackend(), storage, prov)
        prov.auto_confirm = True
        assert payments.confirm_hold(session, prov, pay)
        q.family = "some-other-type"
        session.commit()
        with pytest.raises(gate.GateDenied):
            training.run_training(session, p, ScriptedBackend(), storage, prov)

    def _trained(session, storage, project, provider):
        p, q, pay = _paid(session, storage, project, provider)
        payments.confirm_hold(session, provider, pay)
        return p, pay, training.run_training(session, p, CostedLocal(10), storage, provider)

    def n7(session, storage, project, provider, **_):
        p, pay, run = _trained(session, storage, project, provider)
        assert run.status == "done" and run.result["verification"]["metric"] == "steadiness"
        version = session.get(DatasetVersion, p.chosen_dataset_version_id)
        wk, lk = verification.split_for(session, storage, version, task)
        work, locked = pd.read_csv(storage.path(wk)), pd.read_csv(storage.path(lk))
        cols = list(work.columns)
        assert len(locked) > 0 and not set(verification.row_keys(work, cols)) & set(verification.row_keys(locked, cols))

    def n8(session, storage, project, provider, **_):
        p, pay, run = _trained(session, storage, project, provider)
        assert pay.state == "released" and pay.fee_captured_cents == 0 and charged(session, p) == pay.compute_captured_cents == 10
        n = len(provider.capture_calls)
        payments.settle(session, provider, p, run)
        assert charged(session, p) == 10 and len(provider.capture_calls) == n

    def n9(session, storage, project, provider, **_):
        p, pay, run = _trained(session, storage, project, provider)
        cols = list(pd.read_csv(io.BytesIO(make_csv()), nrows=1).columns)
        rec = {c: 0 for c in cols if c != "region"}
        rec.update({"region": "n"} if "region" in cols else {})
        out = model_use.predict_one(session, storage, p, rec)
        assert out["task_type"] == task and out["note"] == "an estimate, not a promise"
        plain(json.dumps(out))

    def n11(session, storage, project, provider, **_):
        p, pay, run = _trained(session, storage, project, provider)
        for line in activity(session, p):
            plain(line["text"])
            assert "_cents" not in line["text"] and not re.search(r"\b\d{3,}\s*cents\b", line["text"])

    def n13(api, session, storage, project, **_):
        p = proj(session, storage, project)
        other = make_user(session, f"other-{task}@example.test")
        from app.deps import current_user
        app.dependency_overrides[current_user] = lambda: other
        try:
            assert api.get(f"/projects/{p.id}").status_code == 404
        finally:
            app.dependency_overrides.pop(current_user, None)

    def n14(session, storage, provider, project, **_):
        p = proj(session, storage, project)   # measured at the same step as the classification cell (data chosen)
        assert len(context.build_system(session, p)) < 4800
        assert len(json.dumps(tools.run_readiness(ctx(session, storage, provider, p), {}))) < 1800

    return {"A1": n1, "A2": n2, "A3": n3, "A4": n4, "A5": n5, "A6": n6, "A7": n7, "A8": n8, "A9": n9, "A11": n11,
            "A13": n13, "A14": n14}


def _grouping_cells():
    from tests.e2e.test_unsupervised import blobs
    return _no_answer_cells("grouping", blobs, 0.6)


def _unusual_cells():
    from tests.e2e.test_unsupervised import planted
    return _no_answer_cells("unusual", planted, 0.5)


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("task", TASK_TYPES)
def test_cell(task, stage, session, request):   # `session` is named so the sign-in override in conftest applies
    skip_unless_built(task, stage)
    table = {"classification": CHECKS, "regression": REGRESSION_CHECKS, "forecast": FORECAST_CHECKS,
             "grouping": _grouping_cells(), "unusual": _unusual_cells()}.get(task, {})
    assert stage in table, f"slice for {task} {stage} is marked built but has no check yet"
    check = table[stage]
    wanted = [n for n, p in inspect.signature(check).parameters.items() if p.kind is not p.VAR_KEYWORD]
    check(**{n: request.getfixturevalue(n) for n in wanted})   # only the fixtures a cell asks for (A9 needs the REAL check)
