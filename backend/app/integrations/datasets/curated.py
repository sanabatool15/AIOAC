"""The hand-checked dataset list (specs/agent/11-dataset-discovery.md section 7), loaded from curated.json.

Re-check it against the live services by hand when needed (the check script was removed).
"""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name("curated.json")
PREFIXES = {"hf", "uci", "oml"}


@dataclass(frozen=True)
class CuratedItem:
    id: str
    name: str
    rows: int
    target: str
    about: str
    license: str
    domain: str
    keywords: tuple[str, ...]
    aliases: tuple[str, ...]


def parse(data: dict) -> list[CuratedItem]:
    """Validate and build the list. Raises ValueError with a plain message on any bad item."""
    items, seen = [], set()
    for raw in data.get("items", []):
        try:
            item = CuratedItem(raw["id"], raw["name"], int(raw["rows"]), raw["target"], raw["about"], raw["license"], raw["domain"],
                               tuple(raw["keywords"]), tuple(raw["aliases"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"curated item is malformed: {raw.get('id', raw)!r} ({exc})") from exc
        prefix, _, local = item.id.partition(":")
        if prefix not in PREFIXES or not local:
            raise ValueError(f"curated id must start with one of {sorted(PREFIXES)}: {item.id}")
        if item.id in seen:
            raise ValueError(f"curated id appears twice: {item.id}")
        if item.rows <= 0 or not item.target or not item.about or not item.license or not item.keywords:
            raise ValueError(f"curated item is incomplete: {item.id}")
        seen.add(item.id)
        items.append(item)
    if not items:
        raise ValueError("the curated list is empty")
    return items


@lru_cache
def load_curated() -> list[CuratedItem]:
    return parse(json.loads(PATH.read_text()))
