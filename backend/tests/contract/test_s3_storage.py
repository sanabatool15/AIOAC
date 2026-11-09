"""S3Storage against a fake in-memory boto3 S3 client. No AWS, no network, no keys."""
import io
import os

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from app.integrations.storage.local import LocalStorage
from app.integrations.storage.s3 import S3Storage


def _err(code: str, op: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "x"}}, op)


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[dict] = []
        self.fail_with: str | None = None
        self.page = 1000

    def _maybe_fail(self, op):
        if self.fail_with:
            raise _err(self.fail_with, op)

    def put_object(self, **kw):
        self._maybe_fail("PutObject")
        self.put_calls.append(kw)
        self.objects[kw["Key"]] = kw["Body"]

    def get_object(self, Bucket, Key):
        self._maybe_fail("GetObject")
        if Key not in self.objects:
            raise _err("NoSuchKey", "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}

    def head_object(self, Bucket, Key):
        self._maybe_fail("HeadObject")
        if Key not in self.objects:
            raise _err("404", "HeadObject")
        return {}

    def delete_object(self, Bucket, Key):
        self._maybe_fail("DeleteObject")
        self.objects.pop(Key, None)

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
        self._maybe_fail("ListObjectsV2")
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        start = int(ContinuationToken or 0)
        chunk = keys[start:start + self.page]
        more = start + self.page < len(keys)
        out = {"Contents": [{"Key": k} for k in chunk], "IsTruncated": more}
        if more:
            out["NextContinuationToken"] = str(start + self.page)
        return out


@pytest.fixture
def fake():
    return FakeS3()


@pytest.fixture
def s3(fake):
    s = S3Storage("test-bucket", "app/", client=fake)
    yield s
    s.close()


def test_round_trip_and_prefix(s3, fake):
    s3.put("candidates/p1/c1.csv", b"a,b\n1,2\n")
    assert s3.get("candidates/p1/c1.csv") == b"a,b\n1,2\n"
    assert "app/candidates/p1/c1.csv" in fake.objects
    assert s3.exists("candidates/p1/c1.csv")
    s3.delete("candidates/p1/c1.csv")
    assert not s3.exists("candidates/p1/c1.csv")


def test_every_upload_is_encrypted_and_has_no_acl(s3, fake):
    s3.put("datasets/p/v1.csv", b"x")
    s3.put("models/p/r.joblib", b"y")
    assert len(fake.put_calls) == 2
    for c in fake.put_calls:
        assert c["ServerSideEncryption"] == "AES256"
        assert "ACL" not in c
        assert c["Bucket"] == "test-bucket"


@pytest.mark.parametrize("bad", ["../x", "a/../../x", "/abs", "a//b", "a/./b", "", "a\\b", "x\x00y", ".."])
def test_bad_keys_rejected_everywhere(s3, fake, bad):
    for call in (lambda: s3.put(bad, b"x"), lambda: s3.get(bad), lambda: s3.delete(bad),
                 lambda: s3.exists(bad), lambda: s3.path(bad)):
        with pytest.raises(ValueError):
            call()
    assert fake.objects == {} and fake.put_calls == []


def test_bad_prefix_and_bucket_rejected(fake):
    with pytest.raises(ValueError):
        S3Storage("b", "../evil/", client=fake)
    with pytest.raises(ValueError):
        S3Storage("", "app/", client=fake)


def test_missing_key_same_as_local(s3, tmp_path):
    local = LocalStorage(str(tmp_path / "l"))
    with pytest.raises(FileNotFoundError):
        local.get("nope.csv")
    with pytest.raises(FileNotFoundError):
        s3.get("nope.csv")
    assert local.exists("nope.csv") is False and s3.exists("nope.csv") is False
    local.delete("nope.csv")
    s3.delete("nope.csv")  # no error, like local
    assert local.list("nope") == [] and s3.list("nope") == []
    assert not os.path.exists(local.path("nope.csv")) and not os.path.exists(s3.path("nope.csv"))
    with pytest.raises(FileNotFoundError):
        open(s3.path("nope.csv"), "rb")


def test_list_matches_local_semantics(s3, tmp_path):
    local = LocalStorage(str(tmp_path / "l"))
    for st in (local, s3):
        for k in ("candidates/p1/a.csv", "candidates/p1/b.csv", "candidates/p2/c.csv", "datasets/p1/v1.csv", "candidatesX/z.csv"):
            st.put(k, b"1")
    for prefix in ("candidates", "candidates/", "candidates/p1", "datasets", "candidates/p1/a.csv", "missing"):
        assert s3.list(prefix) == local.list(prefix), prefix
    assert s3.list("candidates") == ["candidates/p1/a.csv", "candidates/p1/b.csv", "candidates/p2/c.csv"]


def test_list_pages(s3, fake):
    fake.page = 2
    for i in range(5):
        s3.put(f"candidates/p/{i}.csv", b"1")
    assert len(s3.list("candidates")) == 5


def test_orphan_report_works_on_s3(s3):
    """Same logic as the orphan report in services/data/datasets: stored keys the database does not know."""
    s3.put("candidates/p/known.csv", b"1")
    s3.put("candidates/p/orphan.csv", b"1")
    s3.put("datasets/p/v1.csv", b"1")
    known = {"candidates/p/known.csv", "datasets/p/v1.csv"}
    orphans = [k for k in s3.list("candidates") + s3.list("datasets") if k not in known]
    assert orphans == ["candidates/p/orphan.csv"]


def test_expiry_purge_deletes_listed_candidates(s3):
    s3.put("candidates/p/old.csv", b"1")
    s3.put("datasets/p/v1.csv", b"1")
    for k in s3.list("candidates"):
        s3.delete(k)
    assert s3.list("candidates") == [] and s3.list("datasets") == ["datasets/p/v1.csv"]


def test_path_downloads_to_temp_and_refreshes(s3):
    s3.put("datasets/p/v1.csv", b"a\n1\n")
    p = s3.path("datasets/p/v1.csv")
    assert open(p, "rb").read() == b"a\n1\n"
    assert s3.path("datasets/p/v1.csv") == p  # cached
    s3.put("datasets/p/v1.csv", b"a\n2\n")  # overwrite drops the stale copy
    assert open(s3.path("datasets/p/v1.csv"), "rb").read() == b"a\n2\n"
    s3.delete("datasets/p/v1.csv")
    assert not os.path.exists(p)


def test_temp_folder_removed_on_close(fake):
    s = S3Storage("b", "app/", client=fake)
    s.put("datasets/p/v.csv", b"1")
    p = s.path("datasets/p/v.csv")
    root = s._cache
    assert os.path.exists(p)
    s.close()
    assert not os.path.exists(root)


def test_errors_map_to_local_exceptions(s3, fake):
    fake.fail_with = "AccessDenied"
    for call in (lambda: s3.put("a", b"x"), lambda: s3.get("a"), lambda: s3.exists("a"), lambda: s3.list("a")):
        with pytest.raises(PermissionError):
            call()
    fake.fail_with = "InternalError"
    with pytest.raises(OSError) as ei:
        s3.get("a")
    assert not isinstance(ei.value, (FileNotFoundError, PermissionError))
    fake.fail_with = "SlowDown"
    with pytest.raises(OSError):
        s3.delete("a")


def test_network_failure_is_oserror(s3, fake):
    def boom(Bucket, Key):
        raise EndpointConnectionError(endpoint_url="https://s3.example")
    fake.get_object = boom
    with pytest.raises(OSError):
        s3.get("a")


def test_factory_default_is_local_and_s3_uses_bucket_fallback(monkeypatch, tmp_path):
    from app.config import settings
    from app.integrations import factory
    from app.integrations.storage import s3 as s3mod

    factory.get_storage.cache_clear()
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "st"))
    assert isinstance(factory.get_storage(), LocalStorage)

    seen = {}

    class Spy:
        def __init__(self, bucket, prefix, region=None, client=None):
            seen.update(bucket=bucket, prefix=prefix, region=region)

    monkeypatch.setattr(s3mod, "S3Storage", Spy)
    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "storage_s3_bucket", "")
    monkeypatch.setattr(settings, "sagemaker_bucket", "fallback-bucket")
    factory.get_storage.cache_clear()
    factory.get_storage()
    assert seen["bucket"] == "fallback-bucket" and seen["prefix"] == "app/"
    factory.get_storage.cache_clear()
