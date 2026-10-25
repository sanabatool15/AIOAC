"""OpenML, called directly through its REST API. No key needed. Shapes read from the live service on 2026-10-25.

List:      GET https://www.openml.org/api/v1/json/data/list/data_name/{name}/status/active/limit/{n}
           -> {"data": {"dataset": [{"did", "name", "version", "status", "quality": [{"name", "value"}]}]}}
           (no free-text search exists; "no results" is HTTP 412 with {"error": {"code": "372"}})
Detail:    GET .../data/{id}            -> {"data_set_description": {name, description, licence, parquet_url,
           default_target_attribute, format, status, visibility, ...}}
Features:  GET .../data/features/{id}   -> {"data_features": {"feature": [{name, data_type, is_target, is_ignore, is_row_identifier}]}}
Qualities: GET .../data/qualities/{id}  -> {"data_qualities": {"quality": [{name, value}]}}
Data:      the `parquet_url` in the detail, accepted only on https://data.openml.org (an address inside a response is not trusted)
"""
import io
import re
from urllib.parse import quote, urlparse

import pandas as pd

from . import _http
from .base import DatasetHit, DatasetInfo, FetchedCsv, SourceError

API = "https://www.openml.org/api/v1/json"
STOP = {"the", "a", "an", "of", "and", "for", "to", "in", "on", "my", "will", "which", "is", "are", "data", "dataset", "predict"}
PARQUET_HOST = "data.openml.org"


def _valid(dataset_id: str) -> int:
    if not re.fullmatch(r"\d{1,8}", str(dataset_id or "")):
        raise SourceError("that is not a valid OpenML dataset number")
    return int(dataset_id)


def _q(items) -> dict:
    return {q["name"]: q["value"] for q in items or []}


def _num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


class OpenMLSource:
    def __init__(self, transport=None):
        self.http = _http.make_client(transport)

    def _json(self, path: str, empty_ok: bool = False) -> dict:
        r = _http.get(self.http, f"{API}/{path}", "OpenML")
        if r.status_code == 412:  # OpenML answers 412 with a coded error for both "no results" and "unknown dataset"
            code = ((r.json() or {}).get("error") or {}).get("code") if r.headers.get("content-type", "").startswith("application/json") else None
            if code == "372" and empty_ok:
                return {}
            raise SourceError("dataset not found" if code in ("111", "372") else "OpenML refused the request")
        if r.status_code >= 400:
            raise SourceError(f"OpenML returned an error ({r.status_code})")
        try:
            return r.json()
        except ValueError as exc:
            raise SourceError("OpenML sent something unreadable") from exc

    def search(self, query: str, limit: int = 6) -> list[DatasetHit]:
        """OpenML has no text search. Try the phrase and each word as a dataset name (at most 4 requests)."""
        words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) >= 3 and w not in STOP]
        names = []
        for n in ["-".join(words), "_".join(words), *words]:
            if n and n not in names:
                names.append(n)
        seen: dict[str, DatasetHit] = {}
        for name in names[:4]:
            body = self._json(f"data/list/data_name/{quote(name, safe='')}/status/active/limit/{limit}", empty_ok=True)
            for d in (body.get("data") or {}).get("dataset", []):
                q = _q(d.get("quality"))
                rows, classes = _num(q.get("NumberOfInstances")), _num(q.get("NumberOfClasses")) or 0
                did = str(d["did"])
                if did not in seen:
                    seen[did] = DatasetHit(id=did, description="", license=None, downloads=0, likes=0, gated=False, name=d.get("name"),
                                           rows=rows, tasks=["Classification"] if classes >= 2 else [], tabular=None)
        return list(seen.values())[:limit]

    def _description(self, n: int) -> dict:
        d = self._json(f"data/{n}").get("data_set_description")
        if not isinstance(d, dict):
            raise SourceError("dataset not found")
        return d

    def _features(self, n: int) -> list[dict]:
        f = (self._json(f"data/features/{n}").get("data_features") or {}).get("feature") or []
        return f if isinstance(f, list) else [f]

    def info(self, dataset_id: str) -> DatasetInfo:
        n = _valid(dataset_id)
        d = self._description(n)
        feats = self._features(n)
        rows = _num(_q((self._json(f"data/qualities/{n}").get("data_qualities") or {}).get("quality")).get("NumberOfInstances"))
        notes = []
        usable = d.get("status") == "active" and d.get("visibility", "public") == "public"
        fmt = str(d.get("format", ""))
        tabular = usable and bool(d.get("parquet_url")) and fmt.lower() != "sparse_arff" \
            and all(f.get("data_type") in ("numeric", "nominal", "string", "date") for f in feats)
        if not usable:
            notes.append("this dataset is not active on OpenML")
        elif not tabular:
            notes.append("this is not a plain table, so it cannot be used")
        target = d.get("default_target_attribute")
        if not target:
            notes.append("OpenML does not name an answer column for this dataset")
        cols = [{"name": f["name"], "dtype": f.get("data_type", "unknown")} for f in feats if f.get("is_row_identifier") != "true"]
        lic = d.get("licence")
        if not lic:
            notes.append("OpenML does not state a license")
        return DatasetInfo(str(n), rows, None, cols, tabular, False, str(lic) if lic else None, "default", "all", notes, target=target)

    def fetch_csv(self, dataset_id: str, max_rows: int, max_bytes: int) -> FetchedCsv:
        n = _valid(dataset_id)
        info = self.info(str(n))
        if not info.tabular:
            raise SourceError("this dataset is not a plain table")
        d = self._description(n)
        url = urlparse(str(d.get("parquet_url", "")))
        if url.scheme != "https" or url.hostname != PARQUET_HOST:
            raise SourceError("OpenML gave a download address we do not trust, so we did not fetch it")
        raw = _http.download(self.http, url.geturl(), "OpenML", max_bytes)
        try:
            df = pd.read_parquet(io.BytesIO(raw))
        except Exception as exc:
            raise SourceError("this dataset could not be read as a table") from exc
        drop = [f["name"] for f in self._features(n) if (f.get("is_row_identifier") == "true" or f.get("is_ignore") == "true")
                and f.get("is_target") != "true" and f["name"] in df.columns]
        df = df.drop(columns=drop)
        truncated = len(df) > max_rows
        df = df.head(max_rows)
        target = info.target if info.target in df.columns else None
        return FetchedCsv(df.to_csv(index=False).encode(), len(df), info.license, truncated, target)
