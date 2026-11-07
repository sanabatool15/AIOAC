"""Proves: the S3 storage provider can write, read and delete one probe object in the real bucket, encrypted.
Writes one tiny object under the app prefix's probe/ folder and deletes it. Cost: nothing measurable.
NEVER RUN YET (written 2026-11-07 without AWS access). Needs STORAGE_S3_BUCKET or SAGEMAKER_BUCKET and AWS credentials
from the standard chain.

Run: RUN_REAL=1 pytest tests/integration/test_s3_storage_live.py -v -s
"""
import uuid

import pytest

from tests.integration.conftest import need

pytest.importorskip("boto3")


def test_probe_object_round_trip(real_settings):
    from app.integrations.storage.s3 import S3Storage

    bucket = real_settings.storage_s3_bucket or real_settings.sagemaker_bucket
    need(bucket, "STORAGE_S3_BUCKET or SAGEMAKER_BUCKET")
    st = S3Storage(bucket, real_settings.storage_s3_prefix, real_settings.sagemaker_region)
    key = f"probe/{uuid.uuid4().hex}.txt"
    try:
        st.put(key, b"aioac probe")
        assert st.exists(key)
        assert st.get(key) == b"aioac probe"
        head = st.client.head_object(Bucket=bucket, Key=st.prefix + key)
        assert head.get("ServerSideEncryption") == "AES256"
    finally:
        st.delete(key)
        st.close()
    assert not st.exists(key)
