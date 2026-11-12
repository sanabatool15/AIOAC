"""Slices S11 (grouping) and S12 (unusual): no answer column, steadiness instead of accuracy, compute-only money."""
import io

import joblib
import numpy as np
import pandas as pd
import pytest

from app.integrations.training_local.backend import LocalBackend
from app.ports import TrainingResult
from app.services import model_use, payments, training
from app.services.cost import quotes
from app.services.data import analysis, datasets, pilot, tasks, verification
from app.services.data.tasks import unsupervised as un
from tests.helpers.builders import charged


def blobs(n=900, seed=0) -> bytes:
    rng = np.random.default_rng(seed)
    c = np.array([[0, 0, 0], [6, 6, 0], [0, 6, 6]])
    X = np.vstack([rng.normal(c[i], 1, (n // 3, 3)) for i in range(3)])
    df = pd.DataFrame(X, columns=["spend", "visits", "basket"])
    df["region"] = rng.choice(["n", "s"], len(df))
    return df.sample(frac=1, random_state=1).to_csv(index=False).encode()


def noise(n=900, seed=0) -> bytes:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.uniform(0, 1, (n, 3)), columns=["a", "b", "c"]).to_csv(index=False).encode()


def planted(n=900, seed=0) -> bytes:
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (n, 4))
    X[:25] += rng.choice([-1, 1], (25, 4)) * 8
    df = pd.DataFrame(X, columns=["amount", "hour", "items", "age"])
    return df.sample(frac=1, random_state=2).to_csv(index=False).encode()


def project_of(session, storage, project, task, csv):
    project.task_type = task
    c = datasets.add_candidate(session, storage, project, "d", "bundled", csv)
    datasets.select_candidate(session, storage, project, c.id, None)
    return project


class CostedLocal:
    name, instance_type = "local", None

    def __init__(self, cost=40):
        self.cost = cost

    def run(self, path, target, cap, on_progress=None, should_stop=None, job_key=None, family="forest", task_type="classification", config=None):
        out = LocalBackend().run(path, target, cap, on_progress, None, job_key, family, task_type, config)
        out.cost_cents = self.cost
        return out


# ---- the maths (pure) ---------------------------------------------------------------------------------------------
def test_three_blobs_are_found_and_steady():
    r = un.evaluate_grouping(pd.read_csv(io.BytesIO(blobs())))
    assert r["groups"] == 3 and r["stability"] > 0.9 and r["score"] > 0.7
    assert un.evaluate_grouping(pd.read_csv(io.BytesIO(blobs()))) == r   # deterministic


def test_noise_has_no_clear_groups():
    r = un.evaluate_grouping(pd.read_csv(io.BytesIO(noise())))
    assert r["score"] < 0.3


def test_planted_outliers_are_flagged_and_steady_and_noise_is_not():
    df = pd.read_csv(io.BytesIO(planted()))
    r = un.evaluate_unusual(df)
    assert r["score"] > 0.5 and abs(r["flag_share"] - 0.03) < 1e-9
    X = un.clean(df)
    model = un.build("unusual", X).fit(X)
    flagged = set(np.where(model.predict(X) == -1)[0])
    assert len(flagged) / len(X) < 0.06   # the flag rate stays near the share asked for
    assert un.evaluate_unusual(pd.read_csv(io.BytesIO(noise())))["score"] < 0.3


def test_too_few_rows_is_refused_in_plain_words():
    with pytest.raises(un.UnsupervisedDataError, match="too few"):
        un.evaluate_grouping(pd.DataFrame({"a": range(20), "b": range(20)}))


def test_the_kinds_have_no_fee_and_no_answer_column():
    for t in ("grouping", "unusual"):
        k = tasks.get(t)
        assert not k.needs_target and not k.supports_fee


# ---- the service flow, both kinds -------------------------------------------------------------------------------------
@pytest.mark.parametrize("task,csv,bar", [("grouping", blobs, 0.6), ("unusual", planted, 0.5)])
def test_free_test_pilot_quote_run_and_settle_compute_only(session, storage, project, provider, task, csv, bar):
    p = project_of(session, storage, project, task, csv())
    assert p.chosen_dataset_version_id and datasets.repo.get_version(session, p.chosen_dataset_version_id).target_column is None
    r = analysis.readiness(session, storage, p)
    assert r.grade and r.findings
    run, out = analysis.baseline_detailed(session, storage, p)
    assert out.score > 0.5 and run.simple_guess_accuracy == 0 and p.baseline_result["task_type"] == task
    f = pilot.run_pilot(session, storage, p, bar)
    assert f.eligible and f.family in ("kmeans", "isolation"), f.reason
    q = quotes.create_quote(session, p)
    assert q.fee_cents == 0 and q.cap_cents == q.compute_cap_cents and q.task_type == task
    quotes.approve_quote(session, p, q)
    pay, _ = payments.create_order(session, provider, "mock", p)
    assert pay.fee_amount_cents == 0 and payments.confirm_hold(session, provider, pay)
    done = training.run_training(session, p, CostedLocal(40), storage, provider)
    v = done.result["verification"]
    assert done.status == "done" and v["metric"] == "steadiness" and v["rows"] > 0 and v["value"] > 0.5
    assert pay.state == "released" and pay.fee_captured_cents == 0 and pay.compute_captured_cents == 40
    assert [c[1] for c in provider.capture_calls] == [40] and charged(session, p) == 40
    n = len(provider.capture_calls)
    payments.settle(session, provider, p, done)
    assert len(provider.capture_calls) == n and charged(session, p) == 40   # a repeat moves no money
    # the locked rows are rows of the file the model never saw
    version = datasets.repo.get_version(session, p.chosen_dataset_version_id)
    wk, lk = verification.split_for(session, storage, version, task)
    work, locked = pd.read_csv(storage.path(wk)), pd.read_csv(storage.path(lk))
    cols = list(work.columns)
    assert len(locked) > 0 and not set(verification.row_keys(work, cols)) & set(verification.row_keys(locked, cols))


def test_noise_is_not_sold(session, storage, project):
    p = project_of(session, storage, project, "grouping", noise())
    analysis.readiness(session, storage, p)
    analysis.baseline_detailed(session, storage, p)
    f = pilot.run_pilot(session, storage, p, 0.6)
    assert not f.eligible and "clear groups" in f.reason


def test_predict_a_group_and_an_unusual_flag(session, storage, project, provider):
    p = project_of(session, storage, project, "grouping", blobs())
    analysis.readiness(session, storage, p)
    analysis.baseline_detailed(session, storage, p)
    pilot.run_pilot(session, storage, p, 0.6)
    q = quotes.create_quote(session, p)
    quotes.approve_quote(session, p, q)
    pay, _ = payments.create_order(session, provider, "mock", p)
    payments.confirm_hold(session, provider, pay)
    training.run_training(session, p, CostedLocal(10), storage, provider)
    out = model_use.predict_one(session, storage, p, {"spend": 6, "visits": 6, "basket": 0, "region": "n"})
    assert out["task_type"] == "grouping" and out["group"] in (1, 2, 3) and out["prediction"] == f"group {out['group']}"
    same = model_use.predict_one(session, storage, p, {"spend": 6.2, "visits": 5.8, "basket": 0.1, "region": "s"})
    assert same["group"] == out["group"]   # records next to each other land in the same group
    b = model_use.predict_batch(session, storage, p, "spend,visits,basket,region\n0,0,0,n\n6,6,0,s\n")
    assert b["rows"] == 2 and {r["prediction"] for r in b["preview"]} <= {"group 1", "group 2", "group 3"}


def test_predict_unusual(session, storage, project, provider):
    p = project_of(session, storage, project, "unusual", planted())
    analysis.readiness(session, storage, p)
    analysis.baseline_detailed(session, storage, p)
    pilot.run_pilot(session, storage, p, 0.5)
    q = quotes.create_quote(session, p)
    quotes.approve_quote(session, p, q)
    pay, _ = payments.create_order(session, provider, "mock", p)
    payments.confirm_hold(session, provider, pay)
    training.run_training(session, p, CostedLocal(10), storage, provider)
    far = model_use.predict_one(session, storage, p, {"amount": 9, "hour": -9, "items": 9, "age": 9})
    mid = model_use.predict_one(session, storage, p, {"amount": 0, "hour": 0, "items": 0, "age": 0})
    assert far["looks_unusual"] is True and mid["looks_unusual"] is False and far["unusual_score"] > mid["unusual_score"]
    assert far["note"] == "an estimate, not a promise"
