"""Small shared HTTP helpers for dataset sources: one retry on connection trouble, size-limited downloads."""
import httpx

from ...ports import SourceError


def make_client(transport: httpx.BaseTransport | None = None, headers: dict | None = None) -> httpx.Client:
    return httpx.Client(timeout=30, follow_redirects=True, headers=headers or {}, transport=transport)


def get(http: httpx.Client, url: str, who: str, **params) -> httpx.Response:
    """GET with one retry on a dropped connection. Errors come back as SourceError with plain wording."""
    for attempt in (1, 2):
        try:
            return http.get(url, params=params or None)
        except httpx.TransportError as exc:
            if attempt == 2:
                raise SourceError(f"could not reach {who} right now") from exc
        except httpx.HTTPError as exc:
            raise SourceError(f"could not reach {who} right now") from exc
    raise AssertionError("unreachable")


def download(http: httpx.Client, url: str, who: str, max_bytes: int) -> bytes:
    """Download a file but stop as soon as it grows past max_bytes. Nothing downloaded is ever executed."""
    try:
        with http.stream("GET", url) as r:
            if r.status_code >= 400:
                raise SourceError(f"{who} could not provide the file ({r.status_code})")
            declared = int(r.headers.get("content-length") or 0)
            if declared > max_bytes:
                raise SourceError(f"this dataset is too large ({declared / 1e6:.0f} MB; the limit is {max_bytes / 1e6:.0f} MB)")
            buf = bytearray()
            for chunk in r.iter_bytes():
                buf += chunk
                if len(buf) > max_bytes:
                    raise SourceError("this dataset is too large to download")
            return bytes(buf)
    except httpx.HTTPError as exc:
        raise SourceError(f"could not reach {who} right now") from exc
