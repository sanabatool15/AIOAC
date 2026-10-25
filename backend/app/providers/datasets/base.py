from dataclasses import dataclass, field
from typing import Protocol


class SourceError(Exception):
    """A dataset source problem, phrased so the agent can explain it to the user in plain words."""


@dataclass
class DatasetHit:
    id: str
    description: str
    license: str | None
    downloads: int
    likes: int
    gated: bool
    # optional richer fields; sources fill what they know (None/empty means unknown)
    name: str | None = None
    rows: int | None = None
    target: str | None = None
    columns: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)   # e.g. ["Classification"]
    tabular: bool | None = None


@dataclass
class DatasetInfo:
    id: str
    rows: int | None
    bytes: int | None
    columns: list[dict]            # [{"name":..., "dtype":...}]
    tabular: bool
    gated: bool
    license: str | None
    config: str
    split: str
    notes: list[str] = field(default_factory=list)
    target: str | None = None      # the source's own idea of the answer column, if it states one


@dataclass
class FetchedCsv:
    csv_bytes: bytes
    rows: int
    license: str | None
    truncated: bool
    suggested_target: str | None = None


class DatasetSource(Protocol):
    def search(self, query: str, limit: int = 6) -> list[DatasetHit]: ...
    def info(self, dataset_id: str) -> DatasetInfo: ...
    def fetch_csv(self, dataset_id: str, max_rows: int, max_bytes: int) -> FetchedCsv: ...
