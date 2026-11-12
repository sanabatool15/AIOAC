"""Slice S9 (HUMAN REVIEW: verification split, training): a number over time through the PAID path on the mock provider.

The locked rows are the NEWEST periods and never in the work rows; the model is fitted on older periods only; the check
forecasts the locked block window by window and scores it once on the pilot's frozen scale. Same money rules as always."""
import io

import joblib
import pandas as pd
import pytest

from app.integrations.training_local.backend import LocalBackend
from app.ports import TrainingResult
from app.repositories import forecasts as forecasts_repo
from app.services import payments, training
from app.services.cost import quotes
from app.services.data import analysis, datasets, pilot, verification
from app.services.data.tasks import forecast as fc
from tests.helpers.builders import charged
from tests.helpers.ml_slices import sales_csv


class CostedLocal:
    name, instance_type = "local", None

    def __init__(self, cost=40, stop=False):
        self.cost, self.stop = cost, stop

    def run(self, path, target, cap, on_progress=None, should_stop=None, job_key=None, family="forest", task_type="classification", config=None):
        if self.stop:
            return TrainingResult(0.0, 0.0, 0.0, self.cost, False, None, stopped=True)
        out = LocalBackend().run(path, target, cap, on_progress, None, job_key, family, task_type, config)
        out.cost_cents = self.cost
        return out


def make(session, storage, project, kind="trend", n=96):
    project.task_type = "forecast"
    c = datasets.add_candidate(session, storage, project, "sales", "bundled", sales_csv(kind, n))
    datasets.select_candidate(session, storage, project, c.id, "units")
    return project


@pytest.fixture
def monthly(session, storage, project):
    return make(session, storage, project)


def held_forecast(session, storage, monthly, provider, target=0.3):
    analysis.readiness(session, storage, monthly)
    analysis.baseline_detailed(session, storage, monthly)
    f = pilot.run_pilot(session, storage, monthly, target)
    assert f.eligible, f.reason
    q = quotes.create_quote(session, monthly)
    quotes.approve_quote(session, monthly, q)
    pay, _ = payments.create_order(session, provider, "mock", monthly)
    assert payments.confirm_hold(session, provider, pay)
    return f, q, pay


def version_of(session, project):
    from app.repositories import datasets as datasets_repo
    return datasets_repo.get_version(session, project.chosen_dataset_version_id)


def test_the_locked_rows_are_the_newest_periods_and_the_date_column_survives(session, storage, monthly):
    work_key, locked_key = verification.split_for(session, storage, version_of(session, monthly), "forecast")
    work, locked = pd.read_csv(storage.path(work_key)), pd.read_csv(storage.path(locked_key))
    assert "month" in work.columns and "month" in locked.columns   # not dropped as a row label
    assert len(work) + len(locked) == 96 and len(locked) == round(0.2 * 96)
    assert pd.to_datetime(work["month"]).max() < pd.to_datetime(locked["month"]).min()


def test_a_pilot_gives_a_forecast_in_the_answers_units(session, storage, monthly):
    analysis.readiness(session, storage, monthly)
    analysis.baseline_detailed(session, storage, monthly)
    f = pilot.run_pilot(session, storage, monthly, 0.3)
    assert f.eligible and f.metric == "error_reduction" and f.family in ("ridge", "forest")
    assert f.pilot["score_scale"]["guess_error"] > 0 and f.band_low <= f.predicted_metric <= f.band_high
    assert pilot.run_pilot(session, storage, monthly, 0.3).predicted_metric == f.predicted_metric   # deterministic


def test_a_random_walk_is_not_sold(session, storage, project):
    walk = make(session, storage, project, "walk")
    analysis.readiness(session, storage, walk)
    analysis.baseline_detailed(session, storage, walk)
    f = pilot.run_pilot(session, storage, walk, 0.5)
    assert not f.eligible and f.reason


def test_too_few_periods_is_not_sold(session, storage, project):
    short = make(session, storage, project, "trend", 30)
    analysis.readiness(session, storage, short)
    analysis.baseline_detailed(session, storage, short)
    f = pilot.run_pilot(session, storage, short, 0.3)
    assert not f.eligible and f.reason   # never sold on a short history, whatever the stated reason


def test_hit_pays_compute_plus_fee(session, storage, monthly, provider):
    f, q, pay = held_forecast(session, storage, monthly, provider)
    run = training.run_training(session, monthly, CostedLocal(40), storage, provider)
    v = run.result["verification"]
    assert run.status == "done" and v["metric"] == "error_reduction" and v["passed"] and v["value"] >= f.target and v["typical_error"] > 0
    assert pay.state == "released" and pay.compute_captured_cents == 40 and pay.fee_captured_cents == 2
    assert [c[1] for c in provider.capture_calls] == [40, 2] and charged(session, monthly) == 42


def test_miss_pays_compute_only(session, storage, monthly, provider):
    f, q, pay = held_forecast(session, storage, monthly, provider)
    forecasts_repo.get(session, q.forecast_id).target = 0.999
    session.commit()
    run = training.run_training(session, monthly, CostedLocal(40), storage, provider)
    assert run.result["verification"]["passed"] is False and pay.fee_captured_cents == 0 and charged(session, monthly) == 40


def test_stop_and_our_failure_and_repeat(session, storage, project, provider, monkeypatch):
    monthly = make(session, storage, project)
    f, q, pay = held_forecast(session, storage, monthly, provider)
    run = training.run_training(session, monthly, CostedLocal(7, stop=True), storage, provider)
    assert run.status == "stopped" and pay.fee_captured_cents == 0 and charged(session, monthly) == 7
    before, n = charged(session, monthly), len(provider.capture_calls)
    payments.settle(session, provider, monthly, run)
    assert charged(session, monthly) == before and len(provider.capture_calls) == n


def test_verification_failure_voids_everything(session, storage, monthly, provider, monkeypatch):
    f, q, pay = held_forecast(session, storage, monthly, provider)

    def broken(*a, **k):
        raise verification.VerificationError("boom")
    monkeypatch.setattr(verification, "verify_model", broken)
    run = training.run_training(session, monthly, CostedLocal(40), storage, provider)
    assert run.status == "failed" and charged(session, monthly) == 0 and pay.state == "voided"


def test_the_saved_model_forecasts_forward_from_the_end_of_its_history(session, storage, monthly, provider):
    held_forecast(session, storage, monthly, provider)
    run = training.run_training(session, monthly, CostedLocal(10), storage, provider)
    with open(storage.path(f"models/{monthly.id}/{run.id}.joblib"), "rb") as fh:
        model = joblib.load(fh)
    ahead = model.forecast(6)
    assert len(ahead) == 6 and model.next_dates(1)[0] > model.dates[-1]
    work_key, _ = verification.split_for(session, storage, version_of(session, monthly), "forecast")
    assert model.dates[-1] == pd.to_datetime(pd.read_csv(storage.path(work_key))["month"]).max()   # trained on work periods only


def test_the_forecast_never_runs_on_sagemaker_yet():
    from app.integrations.aws.sagemaker import SageMakerBackend, SageMakerJobError
    b = SageMakerBackend(object(), object(), bucket="b", role_arn="arn:aws:iam::123456789012:role/x", region="us-east-1",
                         instance_type="ml.m5.xlarge", image_version="1.9-0")
    with pytest.raises(SageMakerJobError, match="forecast"):
        b.run("x.csv", "units", 200, task_type="forecast")


def test_predict_gives_the_next_periods_with_dates_and_the_typical_miss(session, storage, monthly, provider):
    from app.services import model_use
    held_forecast(session, storage, monthly, provider)
    training.run_training(session, monthly, CostedLocal(10), storage, provider)
    out = model_use.predict_one(session, storage, monthly, {"periods": 6})
    d = pd.to_datetime(out["dates"])
    assert len(out["prediction"]) == 6 and out["probabilities"] is None and out["typical_error"] > 0 and out["period"] == "month"
    assert (d[1:] - d[:-1]).days.min() >= 28 and d[0] > pd.Timestamp("2022-05-01")   # continues after the work periods the model was trained on (no refit, by decision)   # one month apart, after the history
    assert out["note"] == "an estimate, not a promise"
    assert len(model_use.predict_one(session, storage, monthly, {})["prediction"]) >= 1   # no number given: one horizon
    for bad in ({"periods": 0}, {"periods": 500}, {"periods": "many"}):
        with pytest.raises(model_use.BadInput):
            model_use.predict_one(session, storage, monthly, bad)
    with pytest.raises(model_use.BadInput, match="does not take a file"):
        model_use.predict_batch(session, storage, monthly, "a,b\n1,2\n")
    desc = model_use.describe(session, storage, monthly)
    assert desc["usable"] and desc["task_type"] == "forecast" and desc["columns"] == []
