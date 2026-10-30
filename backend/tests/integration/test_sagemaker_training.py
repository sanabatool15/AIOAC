"""Proves: one real, capped SageMaker training job runs end to end and the cost we report matches what AWS bills.

SPENDS REAL (small) MONEY. It starts one job on ml.m5.xlarge with a 60 cent app cap (max runtime about 18 minutes,
so AWS compute is at most about 7 cents; a normal run is under 1 cent). Needs an extra opt-in on top of RUN_REAL:

    RUN_REAL=1 RUN_PAID=1 pytest tests/integration/test_sagemaker_training.py -v -s

Checks: the job completes, billable seconds are inside the runtime limit, our reported cost is the formula from
`integrations/aws/sagemaker_cost.py` applied to AWS's billable seconds, the cost never exceeds the cap, the model
is better than a simple guess, and no job is left running afterwards.
"""
import os
import tempfile

import pytest

from tests.integration.conftest import need

boto3 = pytest.importorskip("boto3")

CAP_CENTS = 60
ROWS = 4800


@pytest.fixture(scope="module")
def trained(real_settings):
    if os.environ.get("RUN_PAID") != "1":
        pytest.skip("paid test: also set RUN_PAID=1 (starts one SageMaker job, about 1 cent of AWS compute)")
    need(real_settings.sagemaker_bucket, "SAGEMAKER_BUCKET")
    need(real_settings.sagemaker_role_arn, "SAGEMAKER_ROLE_ARN")
    from app.integrations.aws.sagemaker import SageMakerBackend
    from app.services.data.samples import churn_csv

    path = os.path.join(tempfile.mkdtemp(), "data.csv")
    with open(path, "wb") as f:
        f.write(churn_csv(ROWS))
    stages = []
    key = "it" + os.urandom(4).hex()  # the backend drops hyphens: the AWS job is named aioac-<key>
    result = SageMakerBackend().run(path, "left", CAP_CENTS, on_progress=lambda *a: stages.append(a[0]), job_key=key)
    return result, stages, key


def test_job_completes_inside_the_cap(trained):
    result, stages, _ = trained
    assert not result.stopped_at_cap and not result.stopped
    assert result.cost_cents <= CAP_CENTS
    assert "training" in stages


def test_model_beats_a_simple_guess(trained):
    result, _, _ = trained
    assert result.model_bytes
    assert result.accuracy > result.simple_guess_accuracy


def test_reported_cost_matches_aws_billable_seconds(real_settings, trained):
    from app.integrations.aws.sagemaker_cost import actual_cost_cents, max_runtime_seconds

    result, _, key = trained
    sm = boto3.client("sagemaker", region_name=real_settings.sagemaker_region)
    job = sm.describe_training_job(TrainingJobName=f"aioac-{key}")
    assert job["TrainingJobStatus"] == "Completed"
    billable = job["BillableTimeInSeconds"]
    assert billable <= max_runtime_seconds(CAP_CENTS, real_settings.sagemaker_instance_type)
    assert result.cost_cents == actual_cost_cents(billable, real_settings.sagemaker_instance_type, CAP_CENTS)


def test_no_job_left_running(real_settings, trained):
    sm = boto3.client("sagemaker", region_name=real_settings.sagemaker_region)
    running = sm.list_training_jobs(StatusEquals="InProgress", MaxResults=10)["TrainingJobSummaries"]
    assert running == []
