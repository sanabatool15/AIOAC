"""Add a dataset from a pasted link (Hugging Face, UCI or OpenML page address) as a candidate.

Same path as the agent's fetch_dataset: the link only becomes a source id (integrations/datasets/links.py), the registered
source fetches it under the same row and size limits, and datasets.add_candidate stores it. Choosing it is still a
separate step (select), so the user's click stays the approval.
"""
from ...config import settings
from ...db import Session
from ...db.tables import Project
from ...integrations.datasets.links import LinkError, parse_dataset_link
from ...ports import SourceError, Storage
from ..agent.context import sanitise_license  # outside text is cleaned before it can reach the model's prompt
from . import datasets


def add_from_link(session: Session, storage: Storage, project: Project, registry, url: str) -> dict:
    """Returns {candidate_id, rows, columns, suggested_target?} (columns so the screen can offer the answer-column choice). Raises datasets.DatasetError with a plain message."""
    try:
        link = parse_dataset_link(url)
    except LinkError as exc:
        raise datasets.DatasetError(str(exc)) from exc
    resolved = registry.resolve(link.dataset_id)
    if resolved is None or resolved.entry is None:
        raise datasets.DatasetError("That source is not available right now.")
    try:
        f = resolved.entry.source.fetch_csv(resolved.local_id, settings.max_fetch_rows, settings.max_fetch_bytes)
    except SourceError as exc:
        raise datasets.DatasetError(str(exc)) from exc
    lic = sanitise_license(f.license)
    cand = datasets.add_candidate(session, storage, project, resolved.local_id, resolved.entry.label, f.csv_bytes,
                                  source_url=resolved.entry.url(resolved.local_id), license=None if lic == "not stated" else lic)
    out = {"candidate_id": cand.id, "rows": f.rows, "columns": datasets.candidate_columns(session, storage, project, cand.id)}
    if f.suggested_target:
        out["suggested_target"] = f.suggested_target
    return out
