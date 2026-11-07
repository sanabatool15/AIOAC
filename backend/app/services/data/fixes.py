"""One guided data fix (specs/model-versions-and-improve.md, option B-small).

A fixed whitelist of two fixes. Nothing else can be applied, and the model cannot invent a new one.

  drop_duplicate_rows     exact repeated rows. Repeats let a model "remember" rows it is later scored on, which makes a
                          result look better than it is (skill: suspiciously-good-baseline, check 3).
  drop_mostly_empty_columns  columns that are missing in more than MISSING_SHARE of the rows. A column that is mostly empty
                          carries little to learn from and the gaps have to be filled in with guesses (skill: data-insights).

`propose_fix` only reads: it returns what WOULD change. `apply_fix` writes a child dataset version (parent_id, notes), points
the project at it and sends the project back to the free steps, so the readiness check, free test and free pilot all run
again on the new data. The original version is never edited. The locked test rows do not change (see verification.py).

Honest note: training already ignores repeated rows when it learns, so the duplicate fix mostly tidies the saved copy.
Whether either fix changes the estimate is something the free pilot is run again to find out; nothing here promises it.
"""
import io
from dataclasses import asdict, dataclass, field

import pandas as pd

from ...config import settings
from ...db import Session
from ...db.tables import DatasetVersion, Project
from ...ports import Storage
from ...repositories import datasets as datasets_repo
from ...repositories import projects as projects_repo
from ...repositories import quotes as quotes_repo
from .. import lifecycle
from . import analysis

MISSING_SHARE = 0.5   # a column missing in more than half of the rows is "mostly empty"
KINDS = ("drop_duplicate_rows", "drop_mostly_empty_columns")  # the whole whitelist

NOTE = ("Training already ignores repeated rows, so removing them mostly tidies your saved copy. "
        "We will test whether this changes the estimate; it may not.")


class FixError(Exception):
    """A plain-words reason a fix cannot be proposed or applied (the API answers 409)."""


@dataclass
class FixProposal:
    available: bool
    version_id: str
    message: str
    rows_before: int = 0
    rows_after: int = 0
    columns_before: int = 0
    columns_after: int = 0
    rows_removed: int = 0
    columns_dropped: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)   # {kind, what, why}
    fixes_used: int = 0
    fixes_left: int = 0
    note: str = NOTE

    def as_dict(self) -> dict:
        return asdict(self)


def fixes_used(session: Session, project_id: str) -> int:
    """Applied fixes are the dataset versions that have a parent."""
    return sum(1 for v in datasets_repo.versions_for_project(session, project_id) if v.parent_id)


def _read(storage: Storage, version: DatasetVersion) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(storage.get(version.storage_key)))


def _plan(df: pd.DataFrame, target: str) -> tuple[pd.DataFrame, list[dict], int, list[str]]:
    """The cleaned frame and the steps taken. Never drops the answer column."""
    steps, dropped = [], []
    empty_cols = [c for c in df.columns if c != target and df[c].isna().mean() > MISSING_SHARE]
    if empty_cols:
        dropped = [str(c) for c in empty_cols]
        steps.append({"kind": "drop_mostly_empty_columns",
                      "what": f"Remove {len(empty_cols)} column(s) that are mostly empty: {', '.join(dropped)}",
                      "why": f"A column that is empty in more than {round(MISSING_SHARE * 100)} of rows gives a model very little to learn from."})
        df = df.drop(columns=empty_cols)
    dups = int(df.duplicated().sum())
    if dups:
        steps.append({"kind": "drop_duplicate_rows", "what": f"Remove {dups:,} repeated row(s)",
                      "why": "Exact repeats can make a result look better than it is, because the same row can be both learned from and tested on."})
        df = df.drop_duplicates()
    return df, steps, dups, dropped


def propose_fix(session: Session, storage: Storage, project: Project) -> FixProposal:
    """What would change if the fix were applied. No side effect."""
    if not project.chosen_dataset_version_id:
        raise FixError("choose a dataset first")
    version = datasets_repo.get_version(session, project.chosen_dataset_version_id)
    used = fixes_used(session, project.id)
    left = max(0, settings.max_fixes_per_project - used)
    base = dict(version_id=version.id, rows_before=version.rows, rows_after=version.rows, columns_before=version.columns,
                columns_after=version.columns, fixes_used=used, fixes_left=left)
    if left == 0:
        return FixProposal(available=False, message=f"We have already tried {used} fixes on this data, which is the most we try. "
                           "More tries would only make a lucky result look like a real one.", **base)
    df = _read(storage, version)
    cleaned, steps, dups, dropped = _plan(df, version.target_column)
    if not steps:
        return FixProposal(available=False, message="We checked for repeated rows and mostly empty columns and found none, "
                           "so there is nothing we can safely change in this data.", **base)
    parts = []
    if dups:
        parts.append(f"{dups:,} repeated row(s)")
    if dropped:
        parts.append(f"{len(dropped)} mostly empty column(s)")
    return FixProposal(available=True, message="We can remove " + " and ".join(parts) + ".",
                       **{**base, "rows_after": len(cleaned), "columns_after": cleaned.shape[1]},
                       rows_removed=len(df) - len(cleaned), columns_dropped=dropped, steps=steps)


def apply_fix(session: Session, storage: Storage, project: Project, expected_version_id: str | None = None) -> tuple[DatasetVersion, FixProposal]:
    """Create the child version, point the project at it, and send the project back to the free steps.

    The user's click (or the approval card) is the consent: the gate runs in the caller with Action.CLEAN at level 1.
    `expected_version_id` is the version the user saw in the proposal; if the data moved on since, nothing is applied.
    """
    if project.status not in {"baseline_done", "quoted"}:
        raise FixError("a data fix can only be tried after the free test and before you pay")
    proposal = propose_fix(session, storage, project)
    if expected_version_id and expected_version_id != proposal.version_id:
        raise FixError("the data changed since the fix was shown; look at it again")
    if not proposal.available:
        raise FixError(proposal.message)
    parent = datasets_repo.get_version(session, proposal.version_id)
    cleaned, _, _, _ = _plan(_read(storage, parent), parent.target_column)
    n = datasets_repo.count_versions(session, project.id) + 1
    key = f"datasets/{project.id}/v{n}.csv"
    storage.put(key, cleaned.to_csv(index=False).encode())
    notes = "; ".join(s["what"] for s in proposal.steps)
    child = datasets_repo.add_version(session, project_id=project.id, parent_id=parent.id, storage_key=key, rows=len(cleaned),
                                      columns=cleaned.shape[1], target_column=parent.target_column, source=parent.source,
                                      license=parent.license, notes=notes)
    old = quotes_repo.latest_for_project(session, project.id)
    if old is not None:
        quotes_repo.expire(session, old)   # the price was for the old data
    projects_repo.set_chosen_version(session, project, child.id)
    lifecycle.reopen_for_new_data(session, project)
    analysis.readiness(session, storage, project)   # free; the new data gets its own findings and free test
    analysis.baseline(session, storage, project)
    return child, proposal
