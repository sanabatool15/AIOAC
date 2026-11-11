"""Slice S2: regression free test and readiness (specs/ml-tasks/01 section 2.2). Pure maths first, then the free test."""
import io
import re

import numpy as np
import pandas as pd
import pytest

from app.services.data import analysis, features, insights, task_wording, tasks
from app.services.data.tasks.regression import RegressionTask, guess_error_ref
from tests.helpers.ml_slices import house_csv

JARGON = re.compile(r"\b(f1|precision|recall|mae|rmse|r2|r-squared|train/test split|split|hyperparameters?|leakage|"
                    r"feature importance|silhouette)\b", re.I)


def test_regression_is_registered_and_does_not_need_a_fee_change():
    k = tasks.get("regression")
    assert isinstance(k, RegressionTask) and k.needs_target and k.supports_fee and not JARGON.search(k.plain_name)
    assert tasks.get("classification").id == "classification"


def test_score_on_known_arrays():
    k = tasks.get("regression")
    y_true, y_pred = [10.0, 20.0, 30.0, 40.0], [12.0, 18.0, 33.0, 37.0]       # mean absolute error 2.5
    s = k.score(y_true, y_pred, y_train=[0.0, 20.0, 40.0], guess_error_ref=10.0)
    assert s.value == pytest.approx(0.75) and s.simple_guess == 0.0
    assert s.extras["error"] == pytest.approx(2.5)
    assert s.extras["guess_error"] == pytest.approx(10.0)    # always the training average (20): |10|,0,10,20 -> 10
    assert s.extras["rows_test"] == 4


def test_a_model_worse_than_the_guess_scores_zero_never_negative():
    s = tasks.get("regression").score([1.0, 2.0, 3.0], [10.0, 20.0, 30.0], y_train=[1.0, 2.0, 3.0], guess_error_ref=1.0)
    assert s.value == 0.0


def test_a_perfect_model_scores_one():
    assert tasks.get("regression").score([1.0, 5.0], [1.0, 5.0], y_train=[1.0, 5.0], guess_error_ref=2.0).value == 1.0


def test_guess_error_is_the_error_of_always_the_average():
    assert guess_error_ref([10, 20, 30]) == pytest.approx(20 / 3)
    assert guess_error_ref([5, 5, 5]) == 0.0


def test_the_scale_is_frozen_the_same_errors_give_the_same_score():
    k = tasks.get("regression")
    a = k.score([10.0, 20.0], [11.0, 21.0], y_train=[0.0, 100.0], guess_error_ref=4.0)
    b = k.score([10.0, 20.0], [11.0, 21.0], y_train=[500.0, 900.0], guess_error_ref=4.0)   # different guess rows, same frozen scale
    assert a.value == b.value == pytest.approx(0.75)
    assert a.extras["guess_error"] != b.extras["guess_error"]


def test_score_without_a_frozen_scale_uses_the_guess_on_those_rows():
    s = tasks.get("regression").score([10.0, 30.0], [10.0, 30.0], y_train=[20.0])
    assert s.value == 1.0 and s.extras["guess_error"] == pytest.approx(10.0)


def test_splits_are_random_not_stratified_and_disjoint():
    df = pd.read_csv(io.BytesIO(house_csv(400)))
    k = tasks.get("regression")
    Xtr, Xte, ytr, yte = k.split(df, "price", 0.2, 0)
    assert len(Xte) == 80 and not set(Xtr.index) & set(Xte.index) and "price" not in Xtr
    work, locked = k.locked_split(df, "price", 0.2, 7)
    assert len(locked) == 80 and not set(work.index) & set(locked.index)
    assert all(not set(a) & set(b) for a, b in k.folds(Xtr, ytr, 3, 0))


def test_finite_test_variance_is_positive():
    k = tasks.get("regression")
    assert k.finite_test_variance(0.5, 100) > 0 and k.finite_test_variance(0.5, 0) > 0


# ---- readiness findings --------------------------------------------------------------------------------------
def texts(df, target="price"):
    return " | ".join(f["text"] for f in insights.analyze(df, target, task="regression")["findings"])


def test_healthy_numbers_have_no_smaller_group_finding_and_no_jargon():
    df = pd.read_csv(io.BytesIO(house_csv(1500)))
    r = insights.analyze(df, "price", task="regression")
    assert r["grade"] in ("A", "A-", "B+", "B") and "minority_share" not in r["measurements"]
    assert "target_spread" in r["measurements"] and "target_skew" in r["measurements"]
    assert not any("smaller group" in f["text"] for f in r["findings"])
    for f in r["findings"]:
        assert f["kind"] in ("OK", "NOTE") and not JARGON.search(f["text"]), f


def test_a_constant_answer_fails_readiness():
    df = pd.read_csv(io.BytesIO(house_csv(500)))
    df["price"] = 100.0
    r = insights.analyze(df, "price", task="regression")
    assert "Every row has the same answer" in texts(df) and r["grade"] == "F"


def test_an_almost_constant_answer_is_flagged_and_not_sold():
    df = pd.read_csv(io.BytesIO(house_csv(500)))
    df["price"] = 100000.0 + np.arange(len(df)) * 0.001
    r = insights.analyze(df, "price", task="regression")
    assert "same answer" in texts(df) and r["grade"] == "F"


def test_a_heavily_skewed_answer_is_noted():
    df = pd.read_csv(io.BytesIO(house_csv(1500)))
    df["price"] = np.exp(np.random.default_rng(0).normal(0, 2.0, len(df)))
    t = texts(df)
    assert "very large answers" in t and insights.analyze(df, "price", task="regression")["measurements"]["target_skew"] > 2


def test_many_zeros_and_missing_answers_are_noted():
    df = pd.read_csv(io.BytesIO(house_csv(1500)))
    df.loc[df.index[:600], "price"] = 0.0
    df.loc[df.index[600:900], "price"] = np.nan
    t = texts(df)
    assert "exactly 0" in t and "300 rows have no answer and are left out" in t


def test_text_money_answers_are_read_as_numbers():
    df = pd.read_csv(io.BytesIO(house_csv(500)))
    df["price"] = df["price"].map(lambda v: f"${v:,.0f}")
    assert insights.analyze(df, "price", task="regression")["measurements"]["target_spread"] > 0.01


def test_classification_readiness_is_the_default():
    df = pd.read_csv(io.BytesIO(house_csv(500))).assign(flag=lambda d: (d["sqft"] > 1500).astype(int)).drop(columns=["price"])
    assert "minority_share" in insights.analyze(df, "flag")["measurements"]


# ---- features -----------------------------------------------------------------------------------------------
def test_prepare_features_without_a_target_and_with_keep():
    df = pd.DataFrame({"id": [f"r{i}" for i in range(100)], "v": np.arange(100) % 7, "w": np.arange(100) % 5})
    assert "id" not in features.prepare_features(df, None).columns
    assert "id" in features.prepare_features(df, None, keep=["id"]).columns
    assert list(features.prepare_features(df, "v", keep=["id"]).columns) == ["id", "v", "w"]


# ---- plain wording --------------------------------------------------------------------------------------------
def test_plain_wording_for_a_number():
    extras = {"error": 18400.0, "guess_error": 48500.0, "unit": "$"}
    a = task_wording.plain_score("regression", 0.62, extras)
    b = task_wording.plain_guess("regression", extras)
    assert "off by about $18,400" in a and "estimate" in a
    assert "always the average" in b and "$48,500" in b
    assert not JARGON.search(a + b) and "out of 100" not in a + b


def test_wording_without_a_unit_and_for_small_numbers():
    assert "off by about 3.2" in task_wording.plain_score("regression", 0.5, {"error": 3.2, "guess_error": 6.4, "unit": ""})
    assert task_wording.unit_for("sale_price") == "$" and task_wording.unit_for("temperature") == ""


def test_wording_for_classification_is_the_old_out_of_100():
    assert "out of 100" in task_wording.plain_score("classification", 0.86, {})
    assert "out of 100" in task_wording.plain_guess("classification", {"simple_guess": 0.7})


# ---- the free test through the real service --------------------------------------------------------------------
@pytest.fixture
def numeric(session, storage, project):
    from app.services.data import datasets
    project.task_type = "regression"
    c = datasets.add_candidate(session, storage, project, "houses", "bundled", house_csv(1500))
    datasets.select_candidate(session, storage, project, c.id, "price")
    return project


def test_the_free_test_reports_error_against_the_guess(session, storage, numeric):
    analysis.readiness(session, storage, numeric)
    run, out = analysis.baseline_detailed(session, storage, numeric)
    res = numeric.baseline_result
    assert 0 < out.error < out.guess_error and 0.3 < out.score <= 1 and out.test_rows > 0
    assert set(res) >= {"accuracy", "simple_guess_accuracy", "task_type", "metric", "score", "simple_guess_score", "extras"}
    assert res["task_type"] == "regression" and res["metric"] == "error_reduction"
    assert res["accuracy"] == res["score"] and res["simple_guess_accuracy"] == res["simple_guess_score"] == 0.0
    assert res["extras"]["error"] < res["extras"]["guess_error"] and res["extras"]["unit"] == "$" and res["extras"]["rows_test"] == out.test_rows
    assert run.accuracy == res["score"] and run.samples and numeric.status == "baseline_done"
    text = task_wording.plain_score("regression", res["score"], res["extras"]) + task_wording.plain_guess("regression", res["extras"])
    assert "off by about $" in text


def test_the_free_test_is_deterministic(session, storage, numeric):
    analysis.readiness(session, storage, numeric)
    a = analysis.baseline_detailed(session, storage, numeric)[1]
    b = analysis.baseline_detailed(session, storage, numeric)[1]
    assert a.score == b.score and a.error == b.error and a.guess_error == b.guess_error


def test_trust_for_a_number_uses_the_same_lift_rules(session, storage, numeric):
    analysis.readiness(session, storage, numeric)
    analysis.baseline_detailed(session, storage, numeric)
    assert numeric.trust_level in ("Medium", "High")
