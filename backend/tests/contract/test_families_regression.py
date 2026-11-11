"""Model families for numbers (slice S2) and the unchanged classification builders. families.py ships to SageMaker."""
import io

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier,
                              RandomForestRegressor)
from sklearn.linear_model import LogisticRegression, Ridge

from app.services.data import families
from app.services.data.samples import churn_csv


def X():
    return pd.DataFrame({"a": [1.0, 2.0, None, 4.0] * 5, "b": ["x", "y", "x", "z"] * 5})


def test_regression_forest_is_a_regressor():
    m = families.build("forest", X(), task="regression")
    assert isinstance(m.named_steps["clf"], RandomForestRegressor)


@pytest.mark.parametrize("fam,cls", [("ridge", Ridge), ("boosting", HistGradientBoostingRegressor)])
def test_other_regression_families(fam, cls):
    assert isinstance(families.build(fam, X(), task="regression").named_steps["clf"], cls)


def test_every_regression_family_fits_and_predicts_numbers():
    x = X()
    y = np.arange(len(x), dtype=float)
    for fam in families.REGRESSION_FAMILIES:
        pred = families.build(fam, x, size=20, task="regression").fit(x, y).predict(x)
        assert len(pred) == len(x) and np.isfinite(pred).all()


def test_classification_builders_are_unchanged():
    x = X()
    for fam, cls in (("logistic", LogisticRegression), ("forest", RandomForestClassifier), ("boosting", HistGradientBoostingClassifier)):
        assert isinstance(families.build(fam, x).named_steps["clf"], cls)
        assert isinstance(families.build(fam, x, task="classification").named_steps["clf"], cls)
    assert families.FAMILIES == ("logistic", "forest", "boosting")


def test_a_family_of_the_other_task_is_refused():
    with pytest.raises(ValueError):
        families.build("ridge", X())
    with pytest.raises(ValueError):
        families.build("logistic", X(), task="regression")
    with pytest.raises(ValueError):
        families.build("forest", X(), task="grouping")


def test_regression_plain_names_have_no_jargon():
    for fam in families.REGRESSION_FAMILIES:
        assert families.plain_name(fam, task="regression")
    assert families.plain_name("ridge", task="regression") == "a simple straight-line model"


def test_classification_golden_free_test_is_unchanged(tmp_path):
    from app.services.data import baseline
    p = tmp_path / "c.csv"
    p.write_bytes(churn_csv(1500))
    out = baseline.run_baseline(str(p), "left")
    assert (out.accuracy, out.simple_guess_accuracy, out.train_rows, out.test_rows) == (0.8595317725752508, 0.6956521739130435, 1193, 299)
    assert [s[0] for s in out.samples] == [74, 149, 298]


def test_classification_golden_readiness_is_unchanged():
    from app.services.data import insights
    r = insights.analyze(pd.read_csv(io.BytesIO(churn_csv(1500))), "left")
    assert r["grade"] == "A-" and r["score"] == 92
    assert r["measurements"]["minority_share"] == 0.3053 and "target_spread" not in r["measurements"]
    assert [f["text"] for f in r["findings"]] == ["Enough rows to train a useful model", "8 duplicate rows found (removed automatically)",
                                                  "1% of values are missing (filled in automatically)"]
