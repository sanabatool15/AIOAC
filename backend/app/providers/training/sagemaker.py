"""Paid CPU job on AWS SageMaker (specs/training.md sections 2a, 4). Plain boto3, no SageMaker SDK.

REVIEW: spend-cap code. The cap becomes the job's MaxRuntimeInSeconds, so AWS ends the job even if this
process dies. The polling loop below is only a backstop and the place where progress is reported.

Flow: upload dataset and source tarball to S3, CreateTrainingJob (AWS scikit-learn image, script mode),
poll DescribeTrainingJob, StopTrainingJob if asked, fetch model.tar.gz, cost = BillableTimeInSeconds x price.
"""
import io
import json
import logging
import re
import tarfile
import time
import uuid
from pathlib import Path

import sklearn

from ...config import settings
from ...services import sagemaker_cost as costs
from .base import TrainingResult

log = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent / "sagemaker_script"
SERVICES_DIR = Path(__file__).parent.parent.parent / "services"
SHARED_MODULES = ("features.py", "baseline.py")   # copied verbatim into the tarball as package `aioac_core`
SOURCE_TAR_NAME = "sourcedir.tar.gz"

# Registry accounts for the AWS scikit-learn image. Only regions we have seen in AWS docs are listed;
# for any other region set SAGEMAKER_IMAGE_URI. (683313688378 is the us-east-1 registry in AWS docs.)
SKLEARN_REGISTRY = {"us-east-1": "683313688378"}

# DescribeTrainingJob SecondaryStatus -> plain words
STAGES = {
    "Starting": "provisioning", "LaunchingMLInstances": "provisioning", "PreparingTrainingStack": "provisioning",
    "Downloading": "preparing data", "DownloadingTrainingImage": "preparing data",
    "Training": "training", "Uploading": "saving the model",
    "Stopping": "stopping",
}
# The script trains and evaluates inside one "Training" status, so there is no separate "evaluating" stage here.


class SageMakerJobError(RuntimeError):
    """The job did not produce a usable result. kind: capacity | algorithm | failed | cap_too_small | config.
    cost_cents is what AWS reported as billable (0 if unknown); the caller refunds the rest."""

    def __init__(self, kind: str, message: str, cost_cents: int = 0):
        super().__init__(message)
        self.kind = kind
        self.cost_cents = cost_cents


def container_sklearn_minor(image_version: str) -> str:
    """'1.4-2' -> '1.4'."""
    return ".".join(image_version.split("-")[0].split(".")[:2])


def local_sklearn_matches_container(image_version: str) -> bool:
    """Explicit version check: local scikit-learn must match the container's, or pickled models can fail to load."""
    return ".".join(sklearn.__version__.split(".")[:2]) == container_sklearn_minor(image_version)


def image_uri(region: str, image_version: str, override: str = "") -> str:
    if override:
        return override
    if region not in SKLEARN_REGISTRY:
        raise SageMakerJobError("config", f"no known scikit-learn image registry for {region}; set SAGEMAKER_IMAGE_URI")
    return f"{SKLEARN_REGISTRY[region]}.dkr.ecr.{region}.amazonaws.com/sagemaker-scikit-learn:{image_version}-cpu-py3"


def build_source_tarball() -> bytes:
    """train.py at the top level plus aioac_core/ (verbatim features.py and baseline.py, one source of truth)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(SCRIPT_DIR / "train.py", arcname="train.py")
        init = tarfile.TarInfo("aioac_core/__init__.py")
        init.size = 0
        tar.addfile(init, io.BytesIO(b""))
        for name in SHARED_MODULES:
            tar.add(SERVICES_DIR / name, arcname=f"aioac_core/{name}")
    return buf.getvalue()


def _hp(value) -> str:
    return json.dumps(value)   # the container expects JSON-encoded hyperparameter values


class SageMakerBackend:
    name = "sagemaker"

    def __init__(self, sm_client=None, s3_client=None, *, bucket=None, role_arn=None, region=None,
                 instance_type=None, image_version=None, poll_seconds=None, sleep=time.sleep, clock=time.time,
                 job_name_factory=None):
        self.region = region or settings.sagemaker_region
        self.bucket = bucket or settings.sagemaker_bucket
        self.role_arn = role_arn or settings.sagemaker_role_arn
        self.instance_type = instance_type or settings.sagemaker_instance_type
        self.image_version = image_version or settings.sagemaker_sklearn_version
        self.poll_seconds = settings.sagemaker_poll_seconds if poll_seconds is None else poll_seconds
        self._sm, self._s3 = sm_client, s3_client
        self._sleep, self._clock = sleep, clock
        self._job_name = job_name_factory or (lambda: f"aioac-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}")
        self.last_warnings: list[str] = []

    # clients are created lazily so importing or constructing the backend never touches the network
    @property
    def sm(self):
        if self._sm is None:
            import boto3
            self._sm = boto3.client("sagemaker", region_name=self.region)
        return self._sm

    @property
    def s3(self):
        if self._s3 is None:
            import boto3
            self._s3 = boto3.client("s3", region_name=self.region)
        return self._s3

    # ---- helpers -------------------------------------------------------------------------------------------
    def _put(self, key: str, body: bytes):
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ServerSideEncryption="AES256")

    def _create_job(self, job: str, target: str, max_runtime: int) -> None:
        base = f"s3://{self.bucket}/jobs/{job}"
        self.sm.create_training_job(
            TrainingJobName=job,
            AlgorithmSpecification={
                "TrainingImage": image_uri(self.region, self.image_version, settings.sagemaker_image_uri),
                "TrainingInputMode": "File",
            },
            RoleArn=self.role_arn,
            InputDataConfig=[{
                "ChannelName": "train",
                "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri": f"{base}/input/train/",
                                                "S3DataDistributionType": "FullyReplicated"}},
                "ContentType": "text/csv",
            }],
            OutputDataConfig={"S3OutputPath": f"{base}/output"},
            ResourceConfig={"InstanceType": self.instance_type, "InstanceCount": 1, "VolumeSizeInGB": 5},
            StoppingCondition={"MaxRuntimeInSeconds": max_runtime,
                               "MaxPendingTimeInSeconds": settings.sagemaker_max_pending_seconds},
            HyperParameters={
                "sagemaker_program": _hp("train.py"),
                "sagemaker_submit_directory": _hp(f"{base}/code/{SOURCE_TAR_NAME}"),
                "sagemaker_region": _hp(self.region),
                "target": _hp(target),
            },
            ProfilerConfig={"DisableProfiler": True},
            Tags=[{"Key": "project", "Value": "aioac"}],
        )

    def _fetch_artifacts(self, desc: dict) -> tuple[bytes | None, dict]:
        """Returns (model.joblib bytes or None, metrics dict) from the job's model.tar.gz."""
        uri = (desc.get("ModelArtifacts") or {}).get("S3ModelArtifacts")
        if not uri:
            return None, {}
        bucket, _, key = uri.removeprefix("s3://").partition("/")
        try:
            body = self.s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            model, metrics = None, {}
            with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tar:
                for member in tar.getmembers():
                    name = Path(member.name).name
                    if name == "model.joblib":
                        model = tar.extractfile(member).read()
                    elif name == "metrics.json":
                        metrics = json.loads(tar.extractfile(member).read())
            return model, metrics
        except Exception as e:   # missing or unreadable artifact: treated as "no model saved"
            log.warning("could not read model artifact %s: %s", uri, e)
            return None, {}

    def _cost(self, desc: dict, cap_cents: int) -> int:
        return costs.actual_cost_cents(desc.get("BillableTimeInSeconds") or 0, self.instance_type, cap_cents)

    # ---- main entry ----------------------------------------------------------------------------------------
    def run(self, dataset_path, target, cap_cents, on_progress=None, should_stop=None) -> TrainingResult:
        progress = on_progress or (lambda *a, **k: None)
        stop_check = should_stop or (lambda: False)
        if not self.bucket or not self.role_arn:
            raise SageMakerJobError("config", "SAGEMAKER_BUCKET and SAGEMAKER_ROLE_ARN must be set")
        try:   # raises before anything is uploaded or started
            max_runtime = costs.max_runtime_seconds(cap_cents, self.instance_type)
        except costs.CapTooSmall as e:
            raise SageMakerJobError("cap_too_small", str(e)) from e

        job = self._job_name()
        progress("queued", 0.0, 0)
        self._put(f"jobs/{job}/input/train/dataset.csv", Path(dataset_path).read_bytes())
        self._put(f"jobs/{job}/code/{SOURCE_TAR_NAME}", build_source_tarball())
        self._create_job(job, target, max_runtime)

        started = self._clock()
        stop_sent = False
        backstop = max_runtime + costs.GRACE_SECONDS + 300 + settings.sagemaker_max_pending_seconds
        last_stage = "queued"
        while True:
            desc = self.sm.describe_training_job(TrainingJobName=job)
            status = desc["TrainingJobStatus"]
            if status in ("Completed", "Failed", "Stopped"):
                break
            elapsed = self._clock() - started
            stage = STAGES.get(desc.get("SecondaryStatus", ""), last_stage)
            last_stage = stage
            running_for = 0.0
            if desc.get("TrainingStartTime"):
                running_for = max(0.0, self._clock() - desc["TrainingStartTime"].timestamp())
            progress(stage, elapsed, costs.actual_cost_cents(running_for, self.instance_type, cap_cents))
            if not stop_sent and (stop_check() or elapsed > backstop):   # backstop only: AWS enforces the cap
                self.sm.stop_training_job(TrainingJobName=job)
                stop_sent = True
            self._sleep(self.poll_seconds)

        return self._finish(desc, cap_cents, progress, self._clock() - started)

    def _finish(self, desc: dict, cap_cents: int, progress, elapsed: float) -> TrainingResult:
        status = desc["TrainingJobStatus"]
        secondary = desc.get("SecondaryStatus", "")
        reason = desc.get("FailureReason", "") or ""
        cost = self._cost(desc, cap_cents)

        if status == "Failed" and "MaxRuntimeExceeded" not in (secondary + reason):
            kind = "capacity" if "CapacityError" in reason else "algorithm" if "AlgorithmError" in reason else "failed"
            raise SageMakerJobError(kind, reason or "training job failed", cost_cents=cost)

        stopped_at_cap = "MaxRuntimeExceeded" in (secondary + reason)
        progress("saving the model", elapsed, cost)
        model, metrics = self._fetch_artifacts(desc)
        if not model and status == "Completed":
            raise SageMakerJobError("failed", "job finished but no model was saved", cost_cents=cost)

        self.last_warnings = []
        sk = metrics.get("sklearn_version")
        if sk and ".".join(sk.split(".")[:2]) != ".".join(sklearn.__version__.split(".")[:2]):
            msg = f"model trained with scikit-learn {sk} but this machine has {sklearn.__version__}"
            self.last_warnings.append(msg)
            log.warning(msg)

        runtime = float(desc.get("TrainingTimeInSeconds") or metrics.get("train_seconds") or 0)
        return TrainingResult(
            accuracy=float(metrics.get("accuracy", 0.0)),
            simple_guess_accuracy=float(metrics.get("simple_guess_accuracy", 0.0)),
            runtime_seconds=runtime,
            cost_cents=cost,
            stopped_at_cap=stopped_at_cap,
            model_bytes=model,
        )
