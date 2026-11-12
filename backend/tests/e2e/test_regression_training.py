"""Slice S4 (HUMAN REVIEW): a number answer through the PAID path on the mock payment provider.

Same money rules as test_payments_and_demo.py: compute always captured (never above the cap), the success fee only if the
locked-rows check passed, the rest voided, our failure voids everything, a repeat moves no money. The model is a real
regression model trained by the local backend; only the compute COST is scripted (the local backend costs nothing).
"""
import io

import joblib
import numpy as np
import pandas as pd
import pytest

from app.integrations.training_local.backend import LocalBackend
from app.ports import TrainingResult
from app.repositories import forecasts as forecasts_repo
from app.services import payments, training
from app.services.cost import quotes
from app.services.data import analysis, datasets, pilot, verification
from app.services.data.tasks import regression
from tests.helpers.builders import charged
from tests.helpers.ml_slices import house_csv


class CostedLocal:
    """The real local regression training, but reporting a chosen compute cost."""
    name, instance_type = "local", None

    def __init__(self, cost=40, stop=False):
        self.cost, self.stop, self.seen = cost, stop, {}

    def run(self, path, target, cap, on_progress=None, should_stop=None, job_key=None, family="forest", task_type="classification"):
        self.seen = {"family": family, "task_type": task_type, "path": str(path)}
        if self.stop:
            return TrainingResult(0.0, 0.0, 0.0, self.cost, False, None, stopped=True)
        out = LocalBackend().run(path, target, cap, on_progress, None, job_key, family, task_type)
        out.cost_cents = self.cost
        return out


@pytest.fixture
def numbers(session, storage, project):
    project.task_type = "regression"
    c = datasets.add_candidate(session, storage, project, "houses", "bundled", house_csv(1500))
    datasets.select_candidate(session, storage, project, c.id, "price")
    return project


def held_regression(session, storage, numbers, provider, target=0.4):
    analysis.readiness(session, storage, numbers)
    analysis.baseline_detailed(session, storage, numbers)
    f = pilot.run_pilot(session, storage, numbers, target)
    assert f.eligible
    q = quotes.create_quote(session, numbers)
    quotes.approve_quote(session, numbers, q)
    pay, _ = payments.create_order(session, provider, "mock", numbers)
    assert payments.confirm_hold(session, provider, pay)
    return f, q, pay


def test_target_hit_pays_compute_plus_fee_and_releases_the_rest(session, storage, numbers, provider):
    f, q, pay = held_regression(session, storage, numbers, provider)
    be = CostedLocal(cost=40)
    run = training.run_training(session, numbers, be, storage, provider)
    assert be.seen["task_type"] == "regression" and be.seen["family"] == q.family
    v = run.result["verification"]
    assert run.status == "done" and v["metric"] == "error_reduction" and v["passed"] is True and v["value"] >= f.target
    assert run.result["task_type"] == "regression"
    assert pay.state == "released" and pay.compute_captured_cents == 40 and pay.fee_captured_cents == 2
    assert charged(session, numbers) == 42 and [c[1] for c in provider.capture_calls] == [40, 2]
    assert pay.released_cents == q.cap_cents - 42 and len(provider.void_calls) == 1


def test_target_missed_pays_compute_only(session, storage, numbers, provider):
    f, q, pay = held_regression(session, storage, numbers, provider)
    stored = forecasts_repo.get(session, q.forecast_id)
    stored.target = 0.999   # the locked rows cannot reach this
    session.commit()
    run = training.run_training(session, numbers, CostedLocal(cost=40), storage, provider)
    assert run.status == "done" and run.result["verification"]["passed"] is False
    assert pay.fee_captured_cents == 0 and charged(session, numbers) == 40 and pay.state == "released"
    assert [c[1] for c in provider.capture_calls] == [40] and pay.released_cents == q.cap_cents - 40


def test_compute_never_above_the_cap(session, storage, numbers, provider):
    f, q, pay = held_regression(session, storage, numbers, provider)
    run = training.run_training(session, numbers, CostedLocal(cost=99_999), storage, provider)
    assert run.cost_cents == q.compute_cap_cents and charged(session, numbers) <= q.cap_cents


def test_stop_captures_compute_so_far_and_no_fee(session, storage, numbers, provider):
    f, q, pay = held_regression(session, storage, numbers, provider)
    run = training.run_training(session, numbers, CostedLocal(cost=7, stop=True), storage, provider)
    assert run.status == "stopped" and pay.fee_captured_cents == 0 and charged(session, numbers) == 7


def test_verification_failure_voids_everything(session, storage, numbers, provider, monkeypatch):
    f, q, pay = held_regression(session, storage, numbers, provider)

    def broken(*a, **k):
        raise verification.VerificationError("boom")
    monkeypatch.setattr(verification, "verify_model", broken)
    run = training.run_training(session, numbers, CostedLocal(cost=40), storage, provider)
    assert run.status == "failed" and charged(session, numbers) == 0 and provider.capture_calls == []
    assert pay.state == "voided"


def test_settling_again_moves_no_money(session, storage, numbers, provider):
    held_regression(session, storage, numbers, provider)
    run = training.run_training(session, numbers, CostedLocal(cost=40), storage, provider)
    before, n = charged(session, numbers), len(provider.capture_calls)
    payments.settle(session, provider, numbers, run)
    assert charged(session, numbers) == before and len(provider.capture_calls) == n


def test_the_check_uses_the_frozen_scale_not_the_locked_rows_own(session, storage, numbers, provider):
    """value = 1 - average distance / the frozen average-guess distance from the pilot (same scale as the target)."""
    f, q, pay = held_regression(session, storage, numbers, provider)
    ref = f.pilot["score_scale"]["guess_error"]
    run = training.run_training(session, numbers, CostedLocal(cost=1), storage, provider)
    version = datasets_version(session, numbers)
    _, locked_key = verification.split_for(session, storage, version, "regression")
    locked = pd.read_csv(storage.path(locked_key))
    key = f"models/{numbers.id}/{run.id}.joblib"
    with open(storage.path(key), "rb") as fh:
        model = joblib.load(fh)
    err = float(np.mean(np.abs(locked["price"] - model.predict(locked.drop(columns=["price"])))))
    assert run.result["verification"]["value"] == pytest.approx(max(0.0, 1 - err / ref), abs=1e-6)
    assert run.result["verification"]["rows"] == len(locked)


def datasets_version(session, project):
    from app.repositories import datasets as datasets_repo
    return datasets_repo.get_version(session, project.chosen_dataset_version_id)


def test_locked_rows_are_numbers_and_never_in_the_work_rows(session, storage, project):
    """A price stored as text ("$1,200") is read as a number in BOTH files, and no row is in both."""
    df = pd.read_csv(io.BytesIO(house_csv(400)))
    df["price"] = df["price"].map(lambda v: f"${v:,.0f}")
    project.task_type = "regression"
    c = datasets.add_candidate(session, storage, project, "houses", "bundled", df.to_csv(index=False).encode())
    datasets.select_candidate(session, storage, project, c.id, "price")
    work_key, locked_key = verification.split_for(session, storage, datasets_version(session, project), "regression")
    work, locked = pd.read_csv(storage.path(work_key)), pd.read_csv(storage.path(locked_key))
    assert pd.api.types.is_numeric_dtype(work["price"]) and pd.api.types.is_numeric_dtype(locked["price"]) and len(locked) > 0
    cols = list(work.columns)
    assert not set(verification.row_keys(work, cols)) & set(verification.row_keys(locked, cols))


def test_local_backend_trains_a_regressor_and_reports_the_number_score(tmp_path):
    p = tmp_path / "work.csv"
    p.write_bytes(house_csv(600))
    out = LocalBackend().run(str(p), "price", 0, family="ridge", task_type="regression")
    assert out.task_type == "regression" and out.score is not None and 0 < out.score <= 1
    assert out.simple_guess_accuracy == 0.0 and out.accuracy == out.score
    model = joblib.load(io.BytesIO(out.model_bytes))
    assert model.predict(pd.read_csv(p).drop(columns=["price"]).head(3)).dtype.kind == "f"


def test_a_classification_run_is_unchanged(tmp_path):
    from app.services.data.samples import churn_csv
    p = tmp_path / "w.csv"
    p.write_bytes(churn_csv(300))
    out = LocalBackend().run(str(p), pd.read_csv(p).columns[-1], 0)
    assert out.task_type == "classification" and out.score is None and 0 <= out.accuracy <= 1


def test_predicting_a_number_gives_a_number_and_the_typical_error(session, storage, numbers, provider):
    from app.services import model_use
    held_regression(session, storage, numbers, provider)
    training.run_training(session, numbers, CostedLocal(cost=10), storage, provider)
    out = model_use.predict_one(session, storage, numbers, {"sqft": 2000, "bedrooms": 3, "neighborhood": "north"})
    assert isinstance(out["prediction"], float) and 100_000 < out["prediction"] < 700_000
    assert out["probabilities"] is None and out["typical_error"] > 0 and out["note"] == "an estimate, not a promise"
    csv = "sqft,bedrooms,neighborhood\n2000,3,north\n1200,2,south\n"
    b = model_use.predict_batch(session, storage, numbers, csv)
    assert b["rows"] == 2 and "confidence" not in b["columns"]
