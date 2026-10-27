"""Proves: AWS credentials work and the SageMaker setup from Terraform exists. Read-only calls, no jobs, no cost:
STS get-caller-identity, S3 head_bucket on SAGEMAKER_BUCKET, SageMaker list_training_jobs (MaxResults=1).

Run: RUN_REAL=1 pytest tests/real/test_aws.py -v -s
"""
import pytest

from tests.integration.conftest import need

boto3 = pytest.importorskip("boto3")


def test_identity(real_settings):
    ident = boto3.client("sts", region_name=real_settings.sagemaker_region).get_caller_identity()
    print("account:", ident["Account"], "arn:", ident["Arn"])
    assert ident["Account"]


def test_bucket_exists(real_settings):
    need(real_settings.sagemaker_bucket, "SAGEMAKER_BUCKET")
    boto3.client("s3", region_name=real_settings.sagemaker_region).head_bucket(Bucket=real_settings.sagemaker_bucket)


def test_sagemaker_reachable(real_settings):
    r = boto3.client("sagemaker", region_name=real_settings.sagemaker_region).list_training_jobs(MaxResults=1)
    assert "TrainingJobSummaries" in r
