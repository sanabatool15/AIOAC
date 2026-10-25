"""Dataset source registry (specs/agent/11-dataset-discovery.md section 9, step 1).

A dataset id carries its source as a prefix: `hf:owner/name`, `uci:144`, `oml:40945`. The bundled synthetic sample keeps
its plain id (`sample-churn`, also accepted as `sample:sample-churn`). The registry resolves an id to the source that
handles it, so no tool needs to know which sources exist.
"""
from dataclasses import dataclass
from typing import Callable

from .base import DatasetSource

SAMPLE_PREFIX = "sample"
SEARCH_ORDER = ("uci", "oml", "hf")  # after the hand-checked list (specs/agent/11 section 4)


@dataclass
class Entry:
    prefix: str
    source: DatasetSource
    label: str                       # plain name shown to people and stored as the candidate's source
    url: Callable[[str], str]        # local id -> page address


@dataclass
class Resolved:
    prefix: str                      # "hf", "uci", "oml" or "sample"
    local_id: str
    entry: Entry | None              # None for the bundled sample


class SourceRegistry:
    def __init__(self):
        self.entries: dict[str, Entry] = {}

    def register(self, prefix: str, source: DatasetSource, label: str, url: Callable[[str], str]) -> "SourceRegistry":
        self.entries[prefix] = Entry(prefix, source, label, url)
        return self

    def get(self, prefix: str) -> Entry | None:
        return self.entries.get(prefix)

    def resolve(self, dataset_id: str, sample_ids: set[str] = frozenset()) -> Resolved | None:
        """Split `prefix:local` and find the source. Unknown prefixes and unknown plain ids give None."""
        did = (dataset_id or "").strip()
        if did in sample_ids:
            return Resolved(SAMPLE_PREFIX, did, None)
        if ":" not in did:
            return None
        prefix, local = did.split(":", 1)
        if prefix == SAMPLE_PREFIX:
            return Resolved(SAMPLE_PREFIX, local, None) if local in sample_ids else None
        entry = self.entries.get(prefix)
        return Resolved(prefix, local, entry) if entry and local else None


def single(source: DatasetSource) -> SourceRegistry:
    """A registry with one Hugging Face-style source. Lets tests and old callers pass a bare source."""
    return SourceRegistry().register("hf", source, "Hugging Face", lambda i: f"https://huggingface.co/datasets/{i}")


def as_registry(source) -> SourceRegistry:
    return source if isinstance(source, SourceRegistry) else single(source)
