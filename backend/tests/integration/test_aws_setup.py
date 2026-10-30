"""Proves: the AWS side is ready for a SageMaker training job, before any money is spent.

Checks: write access to the project bucket (one 5-byte probe object, deleted at once), the training role exists and
SageMaker can assume it, the scikit-learn container image tag exists in the AWS registry, the training quota is above
zero, and the role is limited to the project bucket (known gap, see below). No training job is started.

Cost: nothing (a few requests, one tiny object).
Run: RUN_REAL=1 pytest tests/integration/test_aws_setup.py -v -s
"""
import uuid

import pytest

from tests.integration.conftest import need

boto3 = pytest.importorskip("boto3")

SAGEMAKER_REGISTRY_US_EAST_1 = "683313688378"  # from AWS docs, see specs/training.md section 2a


def test_bucket_accepts_writes(real_settings):
    need(real_settings.sagemaker_bucket, "SAGEMAKER_BUCKET")
    s3 = boto3.client("s3", region_name=real_settings.sagemaker_region)
    key = f"_probe/{uuid.uuid4().hex}.txt"
    s3.put_object(Bucket=real_settings.sagemaker_bucket, Key=key, Body=b"probe")
    try:
        assert s3.head_object(Bucket=real_settings.sagemaker_bucket, Key=key)["ContentLength"] == 5
    finally:
        s3.delete_object(Bucket=real_settings.sagemaker_bucket, Key=key)


def _role_name(real_settings) -> str:
    need(real_settings.sagemaker_role_arn, "SAGEMAKER_ROLE_ARN")
    return real_settings.sagemaker_role_arn.rsplit("/", 1)[-1]


def test_training_role_is_assumable_by_sagemaker(real_settings):
    role = boto3.client("iam").get_role(RoleName=_role_name(real_settings))["Role"]
    principals = [s["Principal"].get("Service") for s in role["AssumeRolePolicyDocument"]["Statement"]]
    assert "sagemaker.amazonaws.com" in principals


@pytest.mark.xfail(reason="known gap (2026-10-30): the role has AmazonS3FullAccess and AmazonSageMakerFullAccess, "
                          "so it can reach every bucket in the account. Replace both with an inline policy for the "
                          "project bucket, then remove this marker.", strict=True)
def test_training_role_is_limited_to_the_project_bucket(real_settings):
    iam = boto3.client("iam")
    attached = iam.list_attached_role_policies(RoleName=_role_name(real_settings))["AttachedPolicies"]
    names = {p["PolicyName"] for p in attached}
    assert not names & {"AmazonS3FullAccess", "AmazonSageMakerFullAccess"}


def test_sklearn_image_tag_exists(real_settings):
    if real_settings.sagemaker_region != "us-east-1":
        pytest.skip("registry id is known for us-east-1 only; set SAGEMAKER_IMAGE_URI for other regions")
    tag = f"{real_settings.sagemaker_sklearn_version}-cpu-py3"
    ecr = boto3.client("ecr", region_name="us-east-1")
    r = ecr.describe_images(registryId=SAGEMAKER_REGISTRY_US_EAST_1, repositoryName="sagemaker-scikit-learn",
                            imageIds=[{"imageTag": tag}])
    assert r["imageDetails"][0]["imageStatus"] == "ACTIVE"


def test_training_quota_is_above_zero(real_settings):
    sq = boto3.client("service-quotas", region_name=real_settings.sagemaker_region)
    wanted = f"{real_settings.sagemaker_instance_type} for training job usage"
    for page in sq.get_paginator("list_service_quotas").paginate(ServiceCode="sagemaker"):
        for q in page["Quotas"]:
            if q["QuotaName"] == wanted:
                print(wanted, "=", q["Value"])
                assert q["Value"] >= 1
                return
    pytest.fail(f"quota '{wanted}' not found")
