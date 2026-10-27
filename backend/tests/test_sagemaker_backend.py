import datetime as dt
import io
import json
import os
import subprocess
import sys
import tarfile

import pytest

from app.integrations.aws import sagemaker as sm
from app.integrations.aws.sagemaker import SageMakerBackend, SageMakerJobError
from app.services.data.samples import churn_csv
from app.integrations.aws import sagemaker_cost as costs
from app.services.cost.report import CostRecord, cost_accuracy_report
from app.services.cost.prices import INSTANCES, PLATFORM_FEE_CENTS, STORAGE_CENTS

INSTANCE = "ml.m5.xlarge"
HOURLY = INSTANCES[INSTANCE].hourly_cents


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any attempt to build a real AWS client fails the test."""
    import boto3

    def boom(*a, **k):
        raise AssertionError("tests must not create real AWS clients")
    monkeypatch.setattr(boto3, "client", boom)
    monkeypatch.setattr(boto3, "Session", boom)


def model_tar(metrics=None, with_model=True) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        if with_model:
            data = b"fake-model"
            ti = tarfile.TarInfo("model.joblib")
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))
        m = json.dumps(metrics or {"accuracy": 0.8, "simple_guess_accuracy": 0.7, "train_seconds": 5.0,
                                   "sklearn_version": __import__("sklearn").__version__}).encode()
        ti = tarfile.TarInfo("metrics.json")
        ti.size = len(m)
        tar.addfile(ti, io.BytesIO(m))
    return buf.getvalue()


class FakeS3:
    def __init__(self, artifact: bytes | None = None):
        self.puts, self.artifact = {}, artifact

    def put_object(self, **kw):
        self.puts[kw["Key"]] = kw

    def get_object(self, Bucket, Key):
        if self.artifact is None:
            raise RuntimeError("NoSuchKey")
        return {"Body": io.BytesIO(self.artifact)}


class FakeSM:
    """Plays back a list of describe_training_job responses (the last one repeats)."""

    def __init__(self, descs):
        self.descs, self.created, self.stopped, self.calls = list(descs), None, 0, 0

    def create_training_job(self, **kw):
        self.created = kw

    def describe_training_job(self, TrainingJobName):
        d = self.descs[min(self.calls, len(self.descs) - 1)]
        self.calls += 1
        return d

    def stop_training_job(self, TrainingJobName):
        self.stopped += 1


def inprogress(secondary, start=None):
    d = {"TrainingJobStatus": "InProgress", "SecondaryStatus": secondary}
    if start:
        d["TrainingStartTime"] = start
    return d


def completed(billable=300, secondary="Completed", status="Completed", **extra):
    return {"TrainingJobStatus": status, "SecondaryStatus": secondary, "BillableTimeInSeconds": billable,
            "TrainingTimeInSeconds": billable - 20, "ModelArtifacts": {"S3ModelArtifacts": "s3://b/jobs/j/output/j/output/model.tar.gz"},
            **extra}


@pytest.fixture
def csv_path(tmp_path):
    p = tmp_path / "d.csv"
    p.write_bytes(churn_csv())
    return str(p)


def backend(descs, artifact=None, **kw):
    s3, smc = FakeS3(artifact if artifact is not None else model_tar()), FakeSM(descs)
    b = SageMakerBackend(smc, s3, bucket="b", role_arn="arn:aws:iam::123456789012:role/x", region="us-east-1",
                         instance_type=INSTANCE, image_version="1.4-2", poll_seconds=0, sleep=lambda s: None,
                         job_name_factory=lambda: "j", **kw)
    return b, smc, s3


# ---- cap math -------------------------------------------------------------------------------------------
def test_max_runtime_math():
    cap = 100
    expected = int((cap - STORAGE_CENTS - PLATFORM_FEE_CENTS) / HOURLY * 3600) - 120 - 60
    assert costs.max_runtime_seconds(cap, INSTANCE) == expected
    assert costs.max_runtime_seconds(700, INSTANCE) > costs.max_runtime_seconds(100, INSTANCE)


def test_max_runtime_never_buys_more_than_the_cap():
    for cap in (60, 100, 300, 700):
        secs = costs.max_runtime_seconds(cap, INSTANCE)
        worst_bill = (secs + costs.GRACE_SECONDS) / 3600 * HOURLY + STORAGE_CENTS + PLATFORM_FEE_CENTS
        assert worst_bill <= cap


@pytest.mark.parametrize("cap", [0, 51, STORAGE_CENTS + PLATFORM_FEE_CENTS, 52])
def test_cap_too_small(cap):
    with pytest.raises(costs.CapTooSmall):
        costs.max_runtime_seconds(cap, INSTANCE)


def test_cap_too_small_refuses_before_any_aws_call(csv_path):
    b, smc, s3 = backend([completed()])
    with pytest.raises(SageMakerJobError) as e:
        b.run(csv_path, "churn", 50)
    assert e.value.kind == "cap_too_small"
    assert smc.created is None and not s3.puts


# ---- cost -----------------------------------------------------------------------------------------------
def test_cost_from_billable_seconds():
    assert costs.actual_cost_cents(3600, INSTANCE, 700) == round(HOURLY) + STORAGE_CENTS + PLATFORM_FEE_CENTS
    assert costs.actual_cost_cents(0, INSTANCE, 700) == STORAGE_CENTS + PLATFORM_FEE_CENTS


def test_cost_never_above_cap():
    assert costs.actual_cost_cents(10 * 3600, INSTANCE, 100) == 100


# ---- run: happy path, request shape ------------------------------------------------------------------
def test_run_success_and_request_shape(csv_path):
    b, smc, s3 = backend([inprogress("Starting"), inprogress("Downloading"), inprogress("Training"),
                          inprogress("Uploading"), completed(billable=300)])
    stages = []
    res = b.run(csv_path, "churn", 200, on_progress=lambda stage, frac: stages.append((stage, frac)))
    c = smc.created
    assert c["StoppingCondition"]["MaxRuntimeInSeconds"] == costs.max_runtime_seconds(200, INSTANCE)
    assert c["ResourceConfig"]["InstanceType"] == INSTANCE and c["ResourceConfig"]["InstanceCount"] == 1
    assert c["AlgorithmSpecification"]["TrainingImage"] == \
        "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.4-2-cpu-py3"
    hp = c["HyperParameters"]
    assert json.loads(hp["sagemaker_program"]) == "train.py" and json.loads(hp["target"]) == "churn"
    assert json.loads(hp["sagemaker_submit_directory"]) == "s3://b/jobs/j/code/sourcedir.tar.gz"
    assert set(s3.puts) == {"jobs/j/input/train/dataset.csv", "jobs/j/code/sourcedir.tar.gz"}
    assert all(p["ServerSideEncryption"] == "AES256" for p in s3.puts.values())
    assert res.model_bytes == b"fake-model" and not res.stopped_at_cap
    assert res.accuracy == 0.8 and res.simple_guess_accuracy == 0.7
    assert res.cost_cents == costs.actual_cost_cents(300, INSTANCE, 200)
    names = [s for s, _ in stages]
    assert names[0] == "queued" and names[1:5] == ["provisioning", "preparing data", "training", "saving the model"]
    assert all(spend <= 200 for _, spend in stages)


def test_stop_requested_calls_stop_training_job_once(csv_path):
    b, smc, _ = backend([inprogress("Training"), inprogress("Training"), completed(status="Stopped", secondary="Stopped", billable=60)])
    res = b.run(csv_path, "churn", 200, should_stop=lambda: True)
    assert smc.stopped == 1
    assert not res.stopped_at_cap and res.model_bytes == b"fake-model"


def test_user_stop_without_saved_model(csv_path):
    d = completed(status="Stopped", secondary="Stopped", billable=30)
    del d["ModelArtifacts"]
    b, smc, _ = backend([inprogress("Training"), d])
    res = b.run(csv_path, "churn", 200, should_stop=lambda: True)
    assert res.model_bytes is None and res.cost_cents <= 200


def test_cap_stop_returns_stopped_at_cap_with_model(csv_path):
    b, smc, _ = backend([inprogress("Training"), completed(status="Stopped", secondary="MaxRuntimeExceeded", billable=10_000)])
    res = b.run(csv_path, "churn", 120)
    assert res.stopped_at_cap and res.model_bytes == b"fake-model"
    assert res.cost_cents == 120 and smc.stopped == 0   # AWS stopped it, we did not


def test_cap_stop_reported_as_failed_status_is_still_a_cap_stop(csv_path):
    d = completed(status="Failed", secondary="MaxRuntimeExceeded", FailureReason="MaxRuntimeExceeded")
    b, _, _ = backend([d])
    assert b.run(csv_path, "churn", 120).stopped_at_cap


def test_cap_stop_without_model(csv_path):
    d = completed(status="Stopped", secondary="MaxRuntimeExceeded")
    del d["ModelArtifacts"]
    b, _, _ = backend([d])
    res = b.run(csv_path, "churn", 120)
    assert res.stopped_at_cap and res.model_bytes is None


@pytest.mark.parametrize("reason,kind", [
    ("CapacityError: Unable to provision requested ML compute capacity", "capacity"),
    ("AlgorithmError: ExecuteUserScriptError", "algorithm"),
    ("ClientError: something else", "failed"),
])
def test_failure_mapping(csv_path, reason, kind):
    b, _, _ = backend([{"TrainingJobStatus": "Failed", "SecondaryStatus": "Failed", "FailureReason": reason,
                        "BillableTimeInSeconds": 90}])
    with pytest.raises(SageMakerJobError) as e:
        b.run(csv_path, "churn", 200)
    assert e.value.kind == kind
    assert e.value.cost_cents == costs.actual_cost_cents(90, INSTANCE, 200) <= 200


def test_completed_but_no_model_is_a_failure(csv_path):
    b, _, _ = backend([completed()], artifact=model_tar(with_model=False))
    with pytest.raises(SageMakerJobError):
        b.run(csv_path, "churn", 200)


def test_backstop_timer_stops_a_runaway_job(csv_path):
    t = {"now": 0.0}
    b, smc, _ = backend([inprogress("Training")] * 3 + [completed(status="Stopped", secondary="Stopped")],
                        clock=lambda: t.__setitem__("now", t["now"] + 10_000) or t["now"])
    b.run(csv_path, "churn", 200)
    assert smc.stopped == 1


def test_missing_config_refused(csv_path):
    b = SageMakerBackend(FakeSM([]), FakeS3(), bucket="", role_arn="")
    with pytest.raises(SageMakerJobError) as e:
        b.run(csv_path, "churn", 200)
    assert e.value.kind == "config"


def test_version_mismatch_warning(csv_path):
    metrics = {"accuracy": 0.8, "simple_guess_accuracy": 0.7, "sklearn_version": "0.0.1"}
    b, _, _ = backend([completed()], artifact=model_tar(metrics))
    b.run(csv_path, "churn", 200)
    assert b.last_warnings and "0.0.1" in b.last_warnings[0]
    assert sm.container_sklearn_minor("1.4-2") == "1.4"
    assert isinstance(sm.local_sklearn_matches_container("1.4-2"), bool)


def test_unknown_region_needs_image_override():
    with pytest.raises(SageMakerJobError):
        sm.image_uri("eu-west-9", "1.4-2")
    assert sm.image_uri("eu-west-9", "1.4-2", "my/image:1") == "my/image:1"


def test_constructing_backend_makes_no_client():
    SageMakerBackend()   # autouse fixture would raise if a client were built


# ---- source tarball and the training script --------------------------------------------------------------
def test_tarball_contents_and_script_runs_locally(tmp_path, csv_path):
    tar_bytes = sm.build_source_tarball()
    src = tmp_path / "src"
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
        names = tar.getnames()
        tar.extractall(src, filter="data")
    assert {"train.py", "aioac_core/__init__.py", "aioac_core/features.py", "aioac_core/baseline.py"} <= set(names)
    # verbatim copies: one source of truth with the local baseline
    assert (src / "aioac_core/features.py").read_bytes() == (sm.SERVICES_DIR / "features.py").read_bytes()

    train_dir, model_dir = tmp_path / "train", tmp_path / "model"
    train_dir.mkdir()
    (train_dir / "d.csv").write_bytes(open(csv_path, "rb").read())
    env = {**os.environ, "SM_CHANNEL_TRAIN": str(train_dir), "SM_MODEL_DIR": str(model_dir), "PYTHONPATH": str(src)}
    out = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r); import train; train.main(['--target','left','--n_estimators','50'])" % str(src)],
                         env={k: v for k, v in env.items()}, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr
    metrics = json.loads((model_dir / "metrics.json").read_text())
    assert (model_dir / "model.joblib").exists()
    assert metrics["trees_built"] == 50 and not metrics["interrupted"] and 0 < metrics["accuracy"] <= 1


def test_script_saves_partial_model_on_stop(tmp_path, csv_path):
    sys.path.insert(0, str(sm.SCRIPT_DIR))
    sys.modules.setdefault("aioac_core", type(sys)("aioac_core"))
    try:
        import importlib.util
        from app.services.data import baseline, features
        sys.modules["aioac_core.baseline"], sys.modules["aioac_core.features"] = baseline, features
        spec = importlib.util.spec_from_file_location("sm_train", sm.SCRIPT_DIR / "train.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        train_dir = tmp_path / "t"
        train_dir.mkdir()
        (train_dir / "d.csv").write_bytes(open(csv_path, "rb").read())
        m = mod.train(str(train_dir), str(tmp_path / "m"), "left", n_estimators=100, should_stop=lambda: True)
        assert m["interrupted"] and m["trees_built"] == mod.BATCH_TREES
        assert (tmp_path / "m" / "model.joblib").exists()
    finally:
        sys.path.remove(str(sm.SCRIPT_DIR))
        for k in ("aioac_core", "aioac_core.baseline", "aioac_core.features"):
            sys.modules.pop(k, None)


# ---- cost accuracy report ----------------------------------------------------------------------------------
def test_cost_accuracy_report():
    recs = [CostRecord(100, 80, 130, 90), CostRecord(100, 80, 130, 140), CostRecord(100, 80, 130, 70), CostRecord(100, 80, 130, 100)]
    r = cost_accuracy_report(recs)
    assert r["jobs"] == 4 and r["inside_range"] == 2 and r["inside_share"] == 0.5
    assert r["over_high"] == 1 and r["under_low"] == 1
    assert r["mean_abs_error_cents"] == (10 + 40 + 30 + 0) / 4
    assert cost_accuracy_report([])["inside_share"] is None


# ---- same run id -> same job, no second job ---------------------------------------------------------------
def test_job_name_comes_from_the_run_id(csv_path):
    s3, smc = FakeS3(model_tar()), FakeSM([completed()])
    b = SageMakerBackend(smc, s3, bucket="b", role_arn="arn:aws:iam::123456789012:role/x", region="us-east-1",
                         instance_type=INSTANCE, image_version="1.4-2", poll_seconds=0, sleep=lambda s: None)
    b.run(csv_path, "churn", 100, job_key="0123456789abcdef0123456789abcdef")
    assert smc.created["TrainingJobName"] == "aioac-0123456789abcdef0123456789abcdef"
    assert len(smc.created["TrainingJobName"]) <= 63


def test_existing_job_is_followed_not_duplicated(csv_path):
    class ClientError(Exception):
        response = {"Error": {"Code": "ResourceInUse"}}

    b, smc, s3 = backend([completed()])

    def create(**kw):
        smc.attempts = getattr(smc, "attempts", 0) + 1
        raise ClientError()

    smc.create_training_job = create
    res = b.run(csv_path, "churn", 100, job_key="abc")
    assert smc.attempts == 1 and res.model_bytes   # followed the existing job to its end


def test_other_create_errors_still_fail(csv_path):
    class ClientError(Exception):
        response = {"Error": {"Code": "AccessDeniedException"}}

    b, smc, s3 = backend([completed()])
    smc.create_training_job = lambda **kw: (_ for _ in ()).throw(ClientError())
    with pytest.raises(ClientError):
        b.run(csv_path, "churn", 100)
