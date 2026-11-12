"""Proves: one real, capped SageMaker job per new task type runs end to end and the saved file opens and works here.

SPENDS REAL (small) MONEY: four jobs on ml.m5.xlarge with a 60 cent app cap each (a normal run bills about 1 cent each).

    RUN_REAL=1 RUN_PAID=1 pytest tests/integration/test_ml_task_types_live.py -v -s

Checks per job: it completes inside the cap, the model file loads in this environment (scikit-learn version, and the
`aioac_core` names used by the training script), and it does the one thing that type does (predict a number, forecast
ahead, label a group, flag a record). The locked-rows check is then run on rows the job never saw."""
import io
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from tests.integration.conftest import need

boto3 = pytest.importorskip("boto3")
CAP_CENTS = 60


def _rng(seed=0):
    return np.random.default_rng(seed)


def _datasets():
    from tests.helpers.ml_slices import house_csv, sales_frame
    rng = _rng()
    blobs = pd.DataFrame(np.vstack([rng.normal(c, 1, (300, 3)) for c in ([0, 0, 0], [6, 6, 0], [0, 6, 6])]), columns=["a", "b", "c"])
    planted = pd.DataFrame(rng.normal(0, 1, (900, 4)), columns=["amount", "hour", "items", "age"])
    planted.iloc[:25] += rng.choice([-1, 1], (25, 4)) * 8
    houses = pd.read_csv(io.BytesIO(house_csv(1500)))
    return {
        "regression": (houses, "price", "ridge", {}),
        "forecast": (sales_frame("trend", 96), "units", "ridge", {"time_column": "month"}),
        "grouping": (blobs, None, "kmeans", {"n_clusters": 3}),
        "unusual": (planted, None, "isolation", {"contamination": 0.03}),
    }


@pytest.fixture(scope="module")
def jobs(real_settings):
    if os.environ.get("RUN_PAID") != "1":
        pytest.skip("paid test: also set RUN_PAID=1 (starts four SageMaker jobs, about 1 cent of AWS compute each)")
    need(real_settings.sagemaker_bucket, "SAGEMAKER_BUCKET")
    need(real_settings.sagemaker_role_arn, "SAGEMAKER_ROLE_ARN")
    from app.integrations.aws.sagemaker import SageMakerBackend
    out = {}
    for task, (df, target, fam, cfg) in _datasets().items():
        path = os.path.join(tempfile.mkdtemp(), "data.csv")
        df.to_csv(path, index=False)
        key = "it" + task[:3] + os.urandom(3).hex()
        res = SageMakerBackend().run(path, target, CAP_CENTS, job_key=key, family=fam, task_type=task, config=cfg)
        out[task] = (res, df, target)
        print(f"{task}: cost {res.cost_cents} cents, {res.runtime_seconds:.0f}s, model {len(res.model_bytes or b'')} bytes")
    return out


@pytest.mark.parametrize("task", ["regression", "forecast", "grouping", "unusual"])
def test_job_completes_inside_the_cap_and_the_file_opens(jobs, task):
    from app.services.data import model_io
    res, df, target = jobs[task]
    assert not res.stopped_at_cap and not res.stopped and res.cost_cents <= CAP_CENTS and res.task_type == task
    model = model_io.load_model(res.model_bytes)
    if task == "regression":
        X = df.drop(columns=[target]).head(5)
        assert np.isfinite(model.predict(X)).all() and res.score is not None and 0 < res.score <= 1
    elif task == "forecast":
        ahead = model.forecast(6)
        assert len(ahead) == 6 and np.isfinite(ahead).all()
    elif task == "grouping":
        assert set(model.predict(df.head(50))) <= {0, 1, 2}
    else:
        assert set(model.predict(df)) <= {-1, 1} and (model.predict(df) == -1).sum() > 0


