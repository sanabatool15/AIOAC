"""Hugging Face Hub + dataset viewer, called directly (no MCP). Shapes verified against the live API.

Hub search:    GET /api/datasets?search=&filter=&limit=&sort=downloads&direction=-1&full=true
Hub detail:    GET /api/datasets/{id}
Viewer:        GET https://datasets-server.huggingface.co/{size,splits,first-rows,parquet}?dataset=...
"""
import io
import re

import httpx
import pandas as pd

from ...ports import DatasetHit, DatasetInfo, FetchedCsv, SourceError

HUB = "https://huggingface.co"
VIEWER = "https://datasets-server.huggingface.co"
TABULAR_FILTER = "task_categories:tabular-classification"
ID_RE = re.compile(r"^[\w.-]+(/[\w.-]+)?$")  # agent-controlled text goes into URLs, so validate it
SCALAR_TYPES = {"Value", "ClassLabel"}


def _valid(dataset_id: str) -> str:
    if not ID_RE.match(dataset_id or ""):
        raise SourceError("that is not a valid dataset name")
    return dataset_id


class HuggingFaceSource:
    def __init__(self, token: str = "", transport: httpx.BaseTransport | None = None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.http = httpx.Client(timeout=30, follow_redirects=True, headers=headers, transport=transport)

    def _get(self, url: str, **params):
        try:
            r = self.http.get(url, params=params or None)
        except httpx.HTTPError as exc:
            raise SourceError("could not reach Hugging Face right now") from exc
        if r.status_code == 404:
            raise SourceError("dataset not found")
        if r.status_code in (401, 403):
            raise SourceError("this dataset needs a login or is gated, so it cannot be used")
        if r.status_code == 429:
            raise SourceError("Hugging Face is rate-limiting us; try again shortly")
        if r.status_code >= 400:
            raise SourceError(f"Hugging Face returned an error ({r.status_code})")
        return r

    def search(self, query: str, limit: int = 6) -> list[DatasetHit]:
        """Tabular-classification matches first, then untagged matches, because good datasets are often untagged."""
        seen: dict[str, DatasetHit] = {}
        for flt in (TABULAR_FILTER, None):
            params = {"search": query, "limit": limit, "sort": "downloads", "direction": -1, "full": "true"}
            if flt:
                params["filter"] = flt
            for d in self._get(f"{HUB}/api/datasets", **params).json():
                if d.get("private") or d.get("disabled") or d["id"] in seen:
                    continue
                seen[d["id"]] = DatasetHit(
                    id=d["id"], description=(d.get("description") or "").strip()[:200],
                    license=(d.get("cardData") or {}).get("license"), downloads=d.get("downloads", 0),
                    likes=d.get("likes", 0), gated=bool(d.get("gated")))
        return list(seen.values())[:limit]

    def info(self, dataset_id: str) -> DatasetInfo:
        _valid(dataset_id)
        hub = self._get(f"{HUB}/api/datasets/{dataset_id}").json()
        gated = bool(hub.get("gated"))
        license_ = (hub.get("cardData") or {}).get("license")
        notes = []
        if gated:
            return DatasetInfo(dataset_id, None, None, [], False, True, license_, "", "", ["gated: needs access approval"])
        splits = self._get(f"{VIEWER}/splits", dataset=dataset_id).json().get("splits", [])
        if not splits:
            raise SourceError("the viewer has not processed this dataset, so it cannot be previewed")
        chosen = next((s for s in splits if s["split"] == "train"), splits[0])
        config, split = chosen["config"], chosen["split"]
        size = self._get(f"{VIEWER}/size", dataset=dataset_id).json()["size"]
        cfg_size = next((c for c in size["configs"] if c["config"] == config), size["dataset"])
        rows = cfg_size.get("num_rows") or cfg_size.get("estimated_num_rows")
        first = self._get(f"{VIEWER}/first-rows", dataset=dataset_id, config=config, split=split).json()
        cols = [{"name": f["name"], "dtype": f["type"].get("dtype") or f["type"]["_type"]} for f in first["features"]]
        tabular = all(f["type"]["_type"] in SCALAR_TYPES for f in first["features"])
        if not tabular:
            notes.append("has non-table columns (text lists, images or audio), so it is not a plain table")
        if cfg_size.get("num_bytes_parquet_files"):
            notes.append(f"about {cfg_size['num_bytes_parquet_files'] / 1e6:.1f} MB")
        return DatasetInfo(dataset_id, rows, cfg_size.get("num_bytes_parquet_files"), cols, tabular, False, license_,
                           config, split, notes)

    def fetch_csv(self, dataset_id: str, max_rows: int, max_bytes: int) -> FetchedCsv:
        info = self.info(dataset_id)
        if info.gated:
            raise SourceError("this dataset is gated and cannot be used")
        if not info.tabular:
            raise SourceError("this dataset is not a plain table")
        if info.bytes and info.bytes > max_bytes:
            raise SourceError(f"this dataset is too large ({info.bytes / 1e6:.0f} MB; the limit is {max_bytes / 1e6:.0f} MB)")
        files = self._get(f"{VIEWER}/parquet", dataset=dataset_id).json()["parquet_files"]
        files = [f for f in files if f["config"] == info.config and f["split"] == info.split]
        if not files:
            raise SourceError("no downloadable table found for this dataset")
        first = self._get(f"{VIEWER}/first-rows", dataset=dataset_id, config=info.config, split=info.split).json()
        names = {f["name"]: f["type"]["names"] for f in first["features"] if f["type"]["_type"] == "ClassLabel"}
        frames, total, got = [], 0, 0
        for f in files:
            if got >= max_rows:
                break
            total += f["size"]
            if total > max_bytes:
                raise SourceError("this dataset is too large to download")
            frames.append(pd.read_parquet(io.BytesIO(self._get(f["url"]).content)))
            got += len(frames[-1])
        df = pd.concat(frames, ignore_index=True)
        truncated = len(df) > max_rows or (info.rows or 0) > len(df)
        df = df.head(max_rows)
        for col, labels in names.items():  # numbers like 0/1 become readable labels
            if col in df.columns:
                df[col] = df[col].map(lambda i, labels=labels: labels[i] if isinstance(i, int) and 0 <= i < len(labels) else i)
        return FetchedCsv(df.to_csv(index=False).encode(), len(df), info.license, truncated)
