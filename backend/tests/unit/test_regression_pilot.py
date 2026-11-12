"""Slice S3: the free pilot and forecast for a number answer (specs/ml-tasks/01 section 2.2, 07 section 3).

Written before the code. Pure maths first, then the pilot through the real service on synthetic data."""
import math

import numpy as np
import pandas as pd
import pytest

from app.services.agent import target as target_rules
from app.services.data import analysis, datasets, forecast, pilot, task_wording, tasks
from app.services.data.tasks.regression import RegressionTask
from tests.helpers.ml_slices import house_csv

CURVE = [(100, 0.70, 0.02), (200, 0.74, 0.02), (400, 0.77, 0.02)]


# ---- extrapolate: the new argument must not move classification at all ----------------------------------------
def test_default_sigma_is_byte_identical_for_classification():
    """Golden values taken from the code BEFORE S3 (repr of the dataclass, so every digit counts)."""
    assert repr(forecast.extrapolate(CURVE, 4000, 800, 0.8)) == \
        "Prediction(predicted=np.float64(0.8521), band_low=np.float64(0.7722), band_high=np.float64(0.932), confidence=0.899)"
    assert repr(forecast.extrapolate(CURVE, 80000, 800, 0.9)) == \
        "Prediction(predicted=np.float64(0.885), band_low=np.float64(0.7286), band_high=1.0, confidence=0.425)"
    assert repr(forecast.extrapolate([(66.0, 0.8, 0.01)], 1000, 300, 0.85)) == \
        "Prediction(predicted=np.float64(0.8), band_low=np.float64(0.7061), band_high=np.float64(0.8939), confidence=0.148)"
    assert forecast.suggest_target(CURVE, 4000, 800) == 0.84
    assert forecast.extrapolate(CURVE, 4000, 800, 0.8, "classification", None) == forecast.extrapolate(CURVE, 4000, 800, 0.8)


def test_a_given_sigma_replaces_the_binomial_term_by_hand_calculation():
    # one point, no growth: sigma = sqrt(se^2 + s^2) with se = 0.02 and s = 0.03
    p = forecast.extrapolate([(100, 0.6, 0.02)], 100, 400, 0.6, "regression", finite_test_sigma=0.03)
    sigma = math.sqrt(0.02 ** 2 + 0.03 ** 2)
    assert p.predicted == 0.6 and p.confidence == 0.5
    assert p.band_low == round(0.6 - 1.96 * sigma, 4) == 0.5293 and p.band_high == round(0.6 + 1.96 * sigma, 4) == 0.6707
    # a bigger finite-test spread widens the band
    wide = forecast.extrapolate([(100, 0.6, 0.02)], 100, 400, 0.6, "regression", finite_test_sigma=0.10)
    assert wide.band_high - wide.band_low > p.band_high - p.band_low


def test_regression_sigma_is_the_spread_of_errors_over_the_frozen_scale_by_hand():
    task = RegressionTask()
    # sd of |error| 2,000, 400 locked rows, a simple guess off by 10,000: 2000 / sqrt(400) / 10000 = 0.01
    assert task.finite_test_sigma(2000, 400, 10000) == pytest.approx(0.01)
    assert task.finite_test_sigma(2000, 100, 10000) == pytest.approx(0.02)          # fewer locked rows, more spread
    assert task.finite_test_sigma(2000, 400, 20000) == pytest.approx(0.005)         # a wider scale, smaller on the score scale
    assert task.finite_test_sigma(2000, 400, 0) == 0.0 and task.finite_test_sigma(2000, 0, 10000) == 0.0   # never divides by zero
    assert task.finite_test_sigma(0, 400, 10000) == 0.0


def test_the_old_placeholder_variance_stays_only_as_a_cautious_fallback():
    assert RegressionTask().finite_test_variance(0.5, 400) == pytest.approx(0.25 / 400)


# ---- the pilot through the real service ------------------------------------------------------------------------
@pytest.fixture
def numeric(session, storage, project):
    project.task_type = "regression"
    c = datasets.add_candidate(session, storage, project, "houses", "bundled", house_csv(1500))
    datasets.select_candidate(session, storage, project, c.id, "price")
    analysis.readiness(session, storage, project)
    analysis.baseline_detailed(session, storage, project)
    return project


def noise_csv(n=1500, seed=3) -> bytes:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({"a": rng.normal(size=n), "b": rng.integers(0, 50, n), "c": rng.choice(["x", "y", "z"], n),
                       "d": rng.normal(size=n), "amount": rng.normal(1000, 300, n).round(2)})
    return df.to_csv(index=False).encode()


@pytest.fixture
def noise(session, storage, project):
    project.task_type = "regression"
    c = datasets.add_candidate(session, storage, project, "noise", "bundled", noise_csv())
    datasets.select_candidate(session, storage, project, c.id, "amount")
    analysis.readiness(session, storage, project)
    analysis.baseline_detailed(session, storage, project)
    return project


def test_a_number_pilot_gives_a_forecast_with_a_frozen_scale(session, storage, numeric):
    f = pilot.run_pilot(session, storage, numeric, 0.5)
    sc = f.pilot["score_scale"]
    assert f.metric == "error_reduction" and f.pilot["task_type"] == "regression" and f.family in ("ridge", "forest", "boosting")
    assert sc["guess_error"] > 0 and sc["abs_error_sd"] > 0
    assert 0 <= f.band_low <= f.predicted_metric <= f.band_high <= 1 and 0 < f.predicted_metric < 1
    assert 0 <= f.confidence <= 1 and f.eligible and f.reason is None
    # the frozen scale is the mean distance of the WORK rows from their own average
    work = pd.read_csv(storage.path(f"splits/{numeric.chosen_dataset_version_id}/work.csv"))
    assert sc["guess_error"] == pytest.approx(float(np.mean(np.abs(work["price"] - work["price"].mean()))))
    assert f.pilot["dropped"] and f.pilot["share_of_data"] <= 0.10


def test_learning_curve_keys_carry_score_and_accuracy_for_every_type(session, storage, numeric, user):
    from app.db.tables import Project
    from app.services.data.samples import churn_csv
    other = Project(goal="churn", user_id=user.id, org_id=user.org_id)
    session.add(other)
    session.commit()
    c = datasets.add_candidate(session, storage, other, "churn", "bundled", churn_csv(1500))
    datasets.select_candidate(session, storage, other, c.id, "left")
    analysis.readiness(session, storage, other)
    analysis.baseline(session, storage, other)
    for p in (numeric, other):
        f = pilot.run_pilot(session, storage, p, 0.5 if p is numeric else 0.6)
        assert len(f.pilot["learning_curve"]) == 3
        for pt in f.pilot["learning_curve"]:
            assert set(pt) == {"training_rows", "score", "accuracy"} and pt["score"] == pt["accuracy"]


def test_the_pilot_is_deterministic_and_never_reads_the_locked_rows(session, storage, numeric, monkeypatch):
    a = pilot.run_pilot(session, storage, numeric, 0.5)
    b = pilot.run_pilot(session, storage, numeric, 0.5)
    assert (a.predicted_metric, a.band_low, a.band_high, a.confidence) == (b.predicted_metric, b.band_low, b.band_high, b.confidence)
    assert a.pilot["score_scale"] == b.pilot["score_scale"]
    locked_key = f"splits/{numeric.chosen_dataset_version_id}/locked.csv"
    locked = pd.read_csv(storage.path(locked_key))
    assert a.pilot["score_scale"]["guess_error"] != pytest.approx(float(np.mean(np.abs(locked["price"] - locked["price"].mean()))), abs=1e-9)


def test_a_pure_noise_number_is_not_eligible(session, storage, noise):
    for t in (0.5, 0.2, 0.02):   # even a tiny goal is not sold: the columns barely help
        f = pilot.run_pilot(session, storage, noise, t)
        assert not f.eligible and f.reason and f.pilot["issues"] is not None
        assert "barely help" in f.reason or "sure" in f.reason or "best case" in f.reason
    low = pilot.run_pilot(session, storage, noise, 0.02)
    assert "barely help" in low.reason and "out of 100" not in low.reason
    assert not any(w in low.reason.lower() for w in ("accuracy", "f1", "r-squared", "split"))


def test_a_high_goal_on_a_good_signal_is_not_eligible_and_speaks_in_dollars(session, storage, numeric):
    f = pilot.run_pilot(session, storage, numeric, 0.99)
    assert not f.eligible and "$" in f.reason and "out of 100" not in f.reason and "off by" in f.reason
    assert f.pilot["suggested_target"] is None or 0.05 <= f.pilot["suggested_target"] < 0.99


def test_target_from_a_typical_error_is_converted_by_code(session, storage, numeric):
    ref = pilot.run_pilot(session, storage, numeric, 0.5).pilot["score_scale"]["guess_error"]
    t = pilot.target_for_error(session, storage, numeric, ref / 4)
    assert t == pytest.approx(0.75, abs=1e-3)                       # 1 - X / guess_error
    with pytest.raises(pilot.ForecastError, match="simple guess"):
        pilot.target_for_error(session, storage, numeric, ref * 1.5)  # not better than always guessing the average


def test_plain_dollars_no_jargon_in_the_forecast_words(session, storage, numeric):
    f = pilot.run_pilot(session, storage, numeric, 0.5)
    words = task_wording.plain_forecast(f.predicted_metric, f.band_low, f.band_high, f.target, f.confidence, f.pilot["score_scale"], "$")
    text = " ".join(words.values())
    assert "$" in words["typical_error_text"] and "off by about" in words["typical_error_text"] and "an estimate" in words["typical_error_text"]
    assert words["band_text"].startswith("between about $") and "simple guess" in words["simple_guess_error_text"]
    assert "% chance" in words["confidence_text"]
    for bad in ("out of 100", "accuracy", "f1", "mae", "rmse", "r2", "r-squared", "split", "0."):
        assert bad not in text.lower(), (bad, text)
    # the band runs from the smaller error (best case) to the bigger one
    lo, hi = [float(x.replace(",", "")) for x in __import__("re").findall(r"\$([\d,]+)", words["band_text"])]
    assert lo <= hi


# ---- target phrases: the user must still name the goal ---------------------------------------------------------
def test_regression_phrases_are_read_as_amounts():
    amounts = lambda *t: target_rules.stated_amounts(list(t))
    assert amounts("typically within $5,000") == [5000.0]
    assert amounts("off by no more than 5000 dollars") == [5000.0]
    assert amounts("within 5k please") == [5000.0]
    assert amounts("about 2 million is fine") == [2_000_000.0]
    assert amounts("$1.5k") == [1500.0]
    assert amounts("no number here", "80%") == []                      # a bare percent is ambiguous for a number answer
    assert target_rules.stated_percent_errors(["within 10%", "10 percent off"]) == [0.1, 0.1]


def test_a_number_answer_never_takes_the_model_choice_or_approval_text_as_the_goal():
    texts = ["I want to predict prices", "Yes, I approve: use this data, typically within $9,000"]
    assert not target_rules.user_named_error(texts, 9000)               # the server's own approval text never counts
    assert not target_rules.user_named_error(texts, 5000)
    assert target_rules.user_named_error(texts + ["typically within $5,000"], 5000)
    assert target_rules.stated_targets(["80 out of 100", "80%"], "regression") == []        # out of 100 is classification wording
    assert target_rules.stated_targets(["80 out of 100"]) == [0.8]                          # classification unchanged
