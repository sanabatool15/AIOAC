"""Dataset storage lifecycle (specs/data.md section 3): temporary candidates, one permanent chosen dataset."""
import io
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import settings
from ...db.tables import DatasetCandidate, DatasetVersion, Project
from ...ports import Storage
from .. import lifecycle


class DatasetError(Exception):
    pass


def add_candidate(session: Session, storage: Storage, project: Project, name: str, source: str,
                  csv_bytes: bytes, source_url: str | None = None, license: str | None = None) -> DatasetCandidate:
    try:
        rows = len(pd.read_csv(io.BytesIO(csv_bytes)))
    except Exception as exc:
        raise DatasetError("that does not look like a readable CSV file") from exc
    cand = DatasetCandidate(project_id=project.id, name=name, source=source, source_url=source_url, license=license,
                            rows=rows, expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.candidate_ttl_hours))
    session.add(cand)
    session.flush()
    cand.storage_key = f"candidates/{project.id}/{cand.id}.csv"
    storage.put(cand.storage_key, csv_bytes)
    session.commit()
    return cand


def select_candidate(session: Session, storage: Storage, project: Project, candidate_id: str, target: str) -> DatasetVersion:
    """Copy the chosen candidate to permanent storage and delete all the others."""
    cand = session.get(DatasetCandidate, candidate_id)
    if cand is None or cand.project_id != project.id:
        raise DatasetError("unknown dataset")
    df = pd.read_csv(io.BytesIO(storage.get(cand.storage_key)))
    if target not in df.columns:
        raise DatasetError(f"column '{target}' not found")
    key = f"datasets/{project.id}/v1.csv"
    storage.put(key, storage.get(cand.storage_key))
    version = DatasetVersion(project_id=project.id, storage_key=key, rows=len(df), columns=df.shape[1], target_column=target,
                             source=cand.source, license=cand.license)
    session.add(version)
    session.flush()
    for other in session.scalars(select(DatasetCandidate).where(DatasetCandidate.project_id == project.id)):
        if other.storage_key:
            storage.delete(other.storage_key)
        other.status = "chosen" if other.id == cand.id else "discarded"
        other.storage_key = None
    project.chosen_dataset_version_id = version.id
    session.commit()
    lifecycle.transition(session, project, "data_chosen")
    return version


def clean(session: Session, storage: Storage, version: DatasetVersion) -> DatasetVersion:
    """New version with duplicates dropped. The original is never edited."""
    df = pd.read_csv(io.BytesIO(storage.get(version.storage_key)))
    before = len(df)
    df = df.drop_duplicates()
    n = len(list(session.scalars(select(DatasetVersion).where(DatasetVersion.project_id == version.project_id)))) + 1
    key = f"datasets/{version.project_id}/v{n}.csv"
    storage.put(key, df.to_csv(index=False).encode())
    new = DatasetVersion(project_id=version.project_id, parent_id=version.id, storage_key=key, rows=len(df),
                         columns=df.shape[1], target_column=version.target_column, source=version.source, license=version.license,
                         notes=f"removed {before - len(df)} duplicate rows")
    session.add(new)
    session.commit()
    return new


def purge_expired(session: Session, storage: Storage, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    n = 0
    for c in session.scalars(select(DatasetCandidate).where(DatasetCandidate.status == "candidate")):
        exp = c.expires_at if c.expires_at.tzinfo else c.expires_at.replace(tzinfo=timezone.utc)
        if exp < now:
            if c.storage_key:
                storage.delete(c.storage_key)
            c.status, c.storage_key = "discarded", None
            n += 1
    session.commit()
    return n


def orphans(session: Session, storage: Storage) -> list[str]:
    """Stored files the database does not know about (specs/data.md: the periodic check)."""
    known = {c.storage_key for c in session.scalars(select(DatasetCandidate)) if c.storage_key}
    known |= {v.storage_key for v in session.scalars(select(DatasetVersion))}
    return [k for k in storage.list("candidates") + storage.list("datasets") if k not in known]
