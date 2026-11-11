"""Every registered TaskKind keeps the same promises (specs/ml-tasks/07 section 2). Only classification exists now."""
import json
import re

import numpy as np
import pandas as pd
import pytest

from app.services.data import tasks
from app.services.data.samples import churn_csv
import io

BANNED = re.compile(r"\b(f1|precision|recall|mae|rmse|r2|r-squared|train/test split|hyperparameters?|leakage)\b", re.I)


def frame(kind=None):
    """A small table with an answer column for the kind: 'left' (yes/no) or 'price' (a number)."""
    if kind is not None and kind.id == "regression":
        from tests.helpers.ml_slices import house_csv
        return pd.read_csv(io.BytesIO(house_csv(600)))
    return pd.read_csv(io.BytesIO(churn_csv(600)))


def answer(kind):
    return "price" if kind.id == "regression" else "left"


@pytest.fixture(params=sorted(tasks.TASKS))
def kind(request):
    return tasks.TASKS[request.param]


def test_every_kind_provides_the_whole_interface(kind):
    for name in ("id", "plain_name", "needs_target", "supports_fee", "families", "split", "locked_split", "folds",
                 "build", "score", "finite_test_variance"):
        assert hasattr(kind, name), name
    assert kind.id in tasks.TASK_IDS and not BANNED.search(kind.plain_name) and kind.families


def test_splits_are_deterministic_and_disjoint(kind):
    df, t = frame(kind), answer(kind)
    a, b = kind.locked_split(df, t, 0.2, 7), kind.locked_split(df, t, 0.2, 7)
    assert a[0].equals(b[0]) and a[1].equals(b[1])
    assert not set(a[0].index) & set(a[1].index) and len(a[0]) + len(a[1]) == len(df)
    Xtr, Xte, ytr, yte = kind.split(df, t, 0.2, 0)
    assert not set(Xtr.index) & set(Xte.index) and len(Xte) == len(yte)


def test_scores_are_plain_json_numbers(kind):
    labels = ([10.0, 20.0, 30.0, 40.0], [12.0, 18.0, 33.0, 37.0], [10.0, 20.0, 30.0]) if kind.id == "regression" else \
        (["a", "b", "a", "a"], ["a", "a", "a", "a"], ["a", "a", "b"])
    s = kind.score(labels[0], labels[1], y_train=labels[2])
    assert 0 <= s.value <= 1 and 0 <= s.simple_guess <= 1
    json.dumps({"v": s.value, "g": s.simple_guess, "x": s.extras})
    assert kind.finite_test_variance(0.8, 100) > 0 and kind.finite_test_variance(0.8, 0) > 0


def test_a_built_kind_builds_every_family(kind):
    df = frame(kind)
    X = df.drop(columns=[answer(kind)])
    for fam in kind.families:
        assert hasattr(kind.build(fam, X), "fit")


def test_classification_numbers_are_what_they_were():
    k = tasks.get("classification")
    assert k.score([1, 0, 1, 1], [1, 0, 0, 1], y_train=[1, 1, 0]).value == 0.75
    assert k.score([1, 0, 1, 1], [1, 0, 0, 1], y_train=[1, 1, 0]).simple_guess == 0.75   # the common answer is 1
    assert k.finite_test_variance(0.8, 100) == pytest.approx(0.0016)
    assert k.finite_test_variance(1.5, 100) == pytest.approx(0.99 * 0.01 / 100)   # clamped like the old binomial term


def test_unknown_and_unbuilt_ids_are_refused_in_plain_words():
    assert tasks.get(None).id == "classification"
    with pytest.raises(tasks.UnknownTask, match="not built yet"):
        tasks.get("forecast")
    with pytest.raises(tasks.UnknownTask, match="unknown"):
        tasks.get("nonsense")


def test_a_project_row_without_a_task_type_reads_as_classification():
    class P:
        task_type = None
    assert tasks.task_of(P()).id == "classification"
    P.task_type = "classification"
    assert tasks.task_of(P()).id == "classification"


def test_every_known_id_is_registered_or_listed_as_unbuilt():
    assert set(tasks.TASKS) <= set(tasks.TASK_IDS) and "classification" in tasks.TASKS


# ---- infer_task_type (pure, not yet wired into any behaviour) -------------------------------------------------
def _df(n=300):
    rng = np.random.default_rng(0)
    return pd.DataFrame({"stars": rng.integers(1, 6, n), "flag": rng.integers(0, 2, n), "price": rng.normal(200000, 50000, n),
                         "kind": rng.choice(["a", "b", "c"], n), "day": pd.date_range("2020-01-01", periods=n).astype(str),
                         "qty": rng.integers(0, 500, n).astype(float)})


@pytest.mark.parametrize("target,goal,expected", [
    ("flag", "will they leave", "classification"), ("stars", "rate it", "classification"), ("kind", "which kind", "classification"),
    ("price", "what price will it sell for", "regression"), ("qty", "how many will we sell", "regression"),
    ("qty", "forecast how many we sell next month", "forecast"),
    (None, "group my customers", "grouping"), (None, "find strange payments", "unusual"),
])
def test_infer_task_type_table(target, goal, expected):
    assert tasks.infer_task_type(_df(), target, goal) == expected


def test_a_future_goal_without_a_date_column_is_regression():
    assert tasks.infer_task_type(_df().drop(columns=["day"]), "qty", "forecast next month") == "regression"


def test_a_new_project_stores_classification_and_the_api_returns_it(session, user):
    from app.repositories import projects
    p = projects.create(session, "predict churn", user.id, user.org_id)
    session.expire_all()
    assert session.get(type(p), p.id).task_type == "classification"
