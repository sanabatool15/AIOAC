"""describe/predict on pipelines with no text columns or no number columns, for every model family."""
import io

import joblib
import numpy as np
import pandas as pd
import pytest

from app.repositories import training_runs as runs_repo
from app.services import model_use
from app.services.data import families


class FakeStorage:
    def __init__(self, blobs):
        self.blobs = blobs

    def get(self, key):
        return self.blobs[key]


def _df(kind):
    rng = np.random.default_rng(0)
    n = 120
    y = rng.integers(0, 2, n)
    df = pd.DataFrame({"a": rng.normal(size=n) + y, "b": rng.normal(size=n)})
    if kind == "text":
        df = pd.DataFrame({"colour": np.where(y == 1, "red", "blue"), "size": rng.choice(["s", "m", "l"], n)})
    return df, pd.Series(y)


def _model(session, project, storage_blobs, family, kind):
    X, y = _df(kind)
    pipe = families.build(family, X, size=20).fit(X, y)
    buf = io.BytesIO()
    joblib.dump(pipe, buf)
    key = f"m/{family}-{kind}"
    storage_blobs[key] = buf.getvalue()
    return runs_repo.add_model(session, project.id, "run1", key, {}, is_current=True)


@pytest.mark.parametrize("family", families.FAMILIES)
@pytest.mark.parametrize("kind", ["number", "text"])
def test_describe_and_predict_work_without_one_kind_of_column(session, project, family, kind):
    blobs = {}
    row = _model(session, project, blobs, family, kind)
    storage = FakeStorage(blobs)
    d = model_use.describe(session, storage, project, row.id)
    assert d["usable"] is True
    kinds = {c["kind"] for c in d["columns"]}
    assert kinds == ({"number"} if kind == "number" else {"text"})
    if kind == "text":
        assert all(c["choices"] for c in d["columns"])
        rec = {"colour": "red", "size": "m"}
    else:
        assert all(c["choices"] is None for c in d["columns"])
        assert all(c["example"] is not None for c in d["columns"])
        rec = {"a": 1.0}
    out = model_use.predict_one(session, storage, project, rec, row.id)
    assert out["prediction"] in (0, 1)
    csv = ",".join(rec) + "\n" + ",".join(str(v) for v in rec.values()) + "\n"
    assert model_use.predict_batch(session, storage, project, csv, row.id)["rows"] == 1
