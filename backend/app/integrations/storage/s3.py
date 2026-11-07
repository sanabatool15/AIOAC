"""S3-backed Storage (same semantics as LocalStorage). Enable with STORAGE_BACKEND=s3.

Credentials come only from the standard AWS chain (profile, AWS_* variables, role). Nothing here reads, stores or
logs a key. Every upload asks S3 for server-side encryption; no ACLs are ever set (the bucket blocks public access).

`path(key)` hands training and baseline code a LOCAL file: the object is downloaded into a private temp folder owned
by this instance. A cached copy is dropped when the key is written or deleted, and the whole folder is removed by
`close()` and at interpreter exit.
"""
import atexit
import os
import shutil
import tempfile
import threading
import weakref

_MISSING_CODES = {"NoSuchKey", "404", "NotFound"}
_DENIED_CODES = {"AccessDenied", "403", "Forbidden"}


def _code(err) -> str:
    return str(getattr(err, "response", {}).get("Error", {}).get("Code", ""))


class S3Storage:
    def __init__(self, bucket: str, prefix: str = "app/", region: str | None = None, client=None):
        if not bucket.strip():
            raise ValueError("S3 storage needs a bucket (STORAGE_S3_BUCKET or SAGEMAKER_BUCKET)")
        self.bucket = bucket.strip()
        self.prefix = self._clean_prefix(prefix)
        if client is None:
            import boto3  # only here, so the local default needs no AWS setup

            client = boto3.client("s3", region_name=region)
        self.client = client
        self._lock = threading.Lock()
        self._cache = tempfile.mkdtemp(prefix="aioac-s3-")
        self._finalizer = weakref.finalize(self, shutil.rmtree, self._cache, True)
        atexit.register(self._finalizer)

    # ---- key handling ----
    @staticmethod
    def _check(key: str) -> str:
        if not isinstance(key, str) or not key or "\x00" in key or "\\" in key or key.startswith("/"):
            raise ValueError("key escapes storage root")
        if any(p in ("", ".", "..") for p in key.split("/")):
            raise ValueError("key escapes storage root")
        return key

    @classmethod
    def _clean_prefix(cls, prefix: str) -> str:
        p = (prefix or "").strip()
        if not p:
            return ""
        return cls._check(p.rstrip("/")) + "/"

    def _full(self, key: str) -> str:
        return self.prefix + self._check(key)

    def _local(self, key: str) -> str:
        return os.path.join(self._cache, *self._check(key).split("/"))

    def _drop_cached(self, key: str) -> None:
        with self._lock:
            try:
                os.unlink(self._local(key))
            except FileNotFoundError:
                pass

    @staticmethod
    def _fail(err, key: str) -> Exception:
        code = _code(err)
        if code in _MISSING_CODES:
            return FileNotFoundError(key)
        if code in _DENIED_CODES:
            return PermissionError(f"storage access denied for {key}")
        return OSError(f"storage error ({code or 'unknown'}) for {key}")

    # ---- Storage interface ----
    def put(self, key: str, data: bytes) -> None:
        from botocore.exceptions import BotoCoreError, ClientError

        full = self._full(key)
        try:
            self.client.put_object(Bucket=self.bucket, Key=full, Body=data, ServerSideEncryption="AES256")
        except ClientError as e:
            raise self._fail(e, key) from None
        except BotoCoreError:
            raise OSError(f"storage unreachable for {key}") from None
        self._drop_cached(key)

    def get(self, key: str) -> bytes:
        from botocore.exceptions import BotoCoreError, ClientError

        full = self._full(key)
        try:
            return self.client.get_object(Bucket=self.bucket, Key=full)["Body"].read()
        except ClientError as e:
            raise self._fail(e, key) from None
        except BotoCoreError:
            raise OSError(f"storage unreachable for {key}") from None

    def delete(self, key: str) -> None:
        from botocore.exceptions import BotoCoreError, ClientError

        full = self._full(key)
        self._drop_cached(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=full)  # S3 does not fail on a missing key
        except ClientError as e:
            err = self._fail(e, key)
            if not isinstance(err, FileNotFoundError):
                raise err from None
        except BotoCoreError:
            raise OSError(f"storage unreachable for {key}") from None

    def exists(self, key: str) -> bool:
        from botocore.exceptions import BotoCoreError, ClientError

        full = self._full(key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=full)
            return True
        except ClientError as e:
            err = self._fail(e, key)
            if isinstance(err, FileNotFoundError):
                return False
            raise err from None
        except BotoCoreError:
            raise OSError(f"storage unreachable for {key}") from None

    def list(self, prefix: str) -> list[str]:
        from botocore.exceptions import BotoCoreError, ClientError

        p = self._check(prefix.rstrip("/")) if prefix else ""
        full = self.prefix + p
        out: list[str] = []
        token = None
        try:
            while True:
                kw = {"Bucket": self.bucket, "Prefix": full}
                if token:
                    kw["ContinuationToken"] = token
                resp = self.client.list_objects_v2(**kw)
                for obj in resp.get("Contents", []):
                    k = obj["Key"]
                    # same as the local folder: the exact file, or anything below that "folder"
                    if not p or k == full or k.startswith(full + "/"):
                        out.append(k[len(self.prefix):])
                if not resp.get("IsTruncated"):
                    break
                token = resp.get("NextContinuationToken")
        except ClientError as e:
            raise self._fail(e, prefix) from None
        except BotoCoreError:
            raise OSError("storage unreachable") from None
        return sorted(out)

    def path(self, key: str) -> str:
        """Local copy of the object for tools that need a file. A missing object gives a path that does not exist,
        as with LocalStorage, so reading it raises FileNotFoundError."""
        local = self._local(key)
        with self._lock:
            if os.path.isfile(local):
                return local
        try:
            data = self.get(key)
        except FileNotFoundError:
            return local
        with self._lock:
            os.makedirs(os.path.dirname(local), exist_ok=True)
            tmp = f"{local}.{threading.get_ident()}.part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, local)
        return local

    def close(self) -> None:
        self._finalizer()
