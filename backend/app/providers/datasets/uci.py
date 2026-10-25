"""UCI Machine Learning Repository, called directly. No key needed. Shapes read from the live service on 2026-10-25.

Search:  GET https://archive.ics.uci.edu/api/datasets/list?search=word   -> {"data": [{"id", "name"}]}  (matches names only)
Detail:  GET https://archive.ics.uci.edu/api/dataset?id=N                -> {"data": {name, abstract, num_instances, target_col,
         tasks, characteristics, variables[{name, role, type}], ...}}  (404 body: {"status": 404, "message": ...})
Data:    GET https://archive.ics.uci.edu/static/public/N/data.csv        (we build this address ourselves; we never follow
         an address given inside the response)
License: not in the API. The dataset pages state CC BY 4.0 (checked for the hand-checked list by scripts/check_curated.py).
"""
import io
import re

import pandas as pd

from . import _http
from .base import DatasetHit, DatasetInfo, FetchedCsv, SourceError

BASE = "https://archive.ics.uci.edu"
NOT_TABLE = {"Image", "Text", "Sequential", "Relational"}
STOP = {"the", "a", "an", "of", "and", "for", "to", "in", "on", "my", "will", "which", "is", "are", "data", "dataset", "predict"}
LICENSE = "cc-by-4.0"


def _valid(dataset_id: str) -> int:
    if not re.fullmatch(r"\d{1,6}", str(dataset_id or "")):
        raise SourceError("that is not a valid UCI dataset number")
    return int(dataset_id)


class UCISource:
    def __init__(self, transport=None):
        self.http = _http.make_client(transport)

    def _json(self, url: str, **params) -> dict:
        r = _http.get(self.http, url, "the UCI repository", **params)
        if r.status_code == 404:
            raise SourceError("dataset not found")
        if r.status_code >= 400:
            raise SourceError(f"the UCI repository returned an error ({r.status_code})")
        try:
            return r.json()
        except ValueError as exc:
            raise SourceError("the UCI repository sent something unreadable") from exc

    def _detail(self, n: int) -> dict:
        body = self._json(f"{BASE}/api/dataset", id=n)
        if body.get("status") != 200 or not isinstance(body.get("data"), dict):
            raise SourceError("dataset not found")
        return body["data"]

    @staticmethod
    def _hit(d: dict) -> DatasetHit:
        chars = set(d.get("characteristics") or [])
        target = (d.get("target_col") or [None])[0]
        cols = [v["name"] for v in (d.get("variables") or []) if v.get("role") != "ID"]
        return DatasetHit(id=str(d["uci_id"]), description=(d.get("abstract") or "").strip()[:200], license=LICENSE, downloads=0, likes=0,
                          gated=False, name=d.get("name"), rows=d.get("num_instances"), target=target, columns=cols[:40],
                          tasks=list(d.get("tasks") or []), tabular=bool(d.get("data_url")) and not (chars & NOT_TABLE))

    def search(self, query: str, limit: int = 6) -> list[DatasetHit]:
        """The service matches names only, so search each meaningful word and rank by how many words matched."""
        words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) >= 3 and w not in STOP][:4]
        found: dict[int, tuple[int, str]] = {}
        for w in words:
            for d in self._json(f"{BASE}/api/datasets/list", search=w).get("data") or []:
                n, hits = found.get(d["id"], (0, d["name"]))
                found[d["id"]] = (n + 1, hits)
        order = sorted(found, key=lambda i: (-found[i][0], i))[:limit]
        out = []
        for i in order:
            try:  # add size, target and description; a failure here only leaves the hit bare
                out.append(self._hit(self._detail(i)))
            except SourceError:
                out.append(DatasetHit(str(i), "", LICENSE, 0, 0, False, name=found[i][1]))
        return out

    def info(self, dataset_id: str) -> DatasetInfo:
        d = self._detail(_valid(dataset_id))
        h = self._hit(d)
        cols = [{"name": v["name"], "dtype": v.get("type") or "unknown"} for v in (d.get("variables") or []) if v.get("role") != "ID"]
        notes = ["UCI states the license as CC BY 4.0 on its dataset pages"]
        if not h.tabular:
            notes.append("this is not a plain table (text, images or sequences), so it cannot be used")
        if "Classification" not in h.tasks:
            notes.append("UCI does not list this as a classification task")
        return DatasetInfo(str(d["uci_id"]), h.rows, None, cols, bool(h.tabular), False, LICENSE, "default", "all", notes, target=h.target)

    def fetch_csv(self, dataset_id: str, max_rows: int, max_bytes: int) -> FetchedCsv:
        n = _valid(dataset_id)
        info = self.info(str(n))
        if not info.tabular:
            raise SourceError("this dataset is not a plain table")
        raw = _http.download(self.http, f"{BASE}/static/public/{n}/data.csv", "the UCI repository", max_bytes)
        try:
            df = pd.read_csv(io.BytesIO(raw), nrows=max_rows + 1)
        except Exception as exc:
            raise SourceError("this dataset could not be read as a table") from exc
        if df.shape[1] < 2 or df.empty:
            raise SourceError("this dataset could not be read as a table")
        truncated = len(df) > max_rows
        df = df.head(max_rows)
        target = info.target if info.target in df.columns else None
        return FetchedCsv(df.to_csv(index=False).encode(), len(df), LICENSE, truncated or (info.rows or 0) > len(df), target)
