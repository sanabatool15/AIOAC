"""Dataset storage lifecycle (specs/data.md section 3): temporary candidates, one permanent chosen dataset."""
import io
from datetime import datetime, timedelta, timezone

import pandas as pd
from ...config import settings
from ...db import Session
from ...db.tables import DatasetCandidate, DatasetVersion, Project
from ...repositories import datasets as repo
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
    def store(cand: DatasetCandidate) -> str:
        key = f"candidates/{project.id}/{cand.id}.csv"
        storage.put(key, csv_bytes)
        return key

    return repo.add_candidate(session, store, project_id=project.id, name=name, source=source, source_url=source_url,
                              license=license, rows=rows,
                              expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.candidate_ttl_hours))


def select_candidate(session: Session, storage: Storage, project: Project, candidate_id: str, target: str) -> DatasetVersion:
    """Copy the chosen candidate to permanent storage and delete all the others."""
    cand = repo.get_candidate(session, candidate_id)
    if cand is None or cand.project_id != project.id:
        raise DatasetError("unknown dataset")
    df = pd.read_csv(io.BytesIO(storage.get(cand.storage_key)))
    if target not in df.columns:
        raise DatasetError(f"column '{target}' not found")
    key = f"datasets/{project.id}/v1.csv"
    storage.put(key, storage.get(cand.storage_key))
    version = repo.choose_candidate(session, project, cand, storage.delete, storage_key=key, rows=len(df),
                                    columns=df.shape[1], target_column=target, source=cand.source, license=cand.license)
    lifecycle.transition(session, project, "data_chosen")
    return version


def clean(session: Session, storage: Storage, version: DatasetVersion) -> DatasetVersion:
    """New version with duplicates dropped. The original is never edited."""
    df = pd.read_csv(io.BytesIO(storage.get(version.storage_key)))
    before = len(df)
    df = df.drop_duplicates()
    n = repo.count_versions(session, version.project_id) + 1
    key = f"datasets/{version.project_id}/v{n}.csv"
    storage.put(key, df.to_csv(index=False).encode())
    return repo.add_version(session, project_id=version.project_id, parent_id=version.id, storage_key=key, rows=len(df),
                            columns=df.shape[1], target_column=version.target_column, source=version.source,
                            license=version.license, notes=f"removed {before - len(df)} duplicate rows")


def purge_expired(session: Session, storage: Storage, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    expired = []
    for c in repo.open_candidates(session):
        exp = c.expires_at if c.expires_at.tzinfo else c.expires_at.replace(tzinfo=timezone.utc)
        if exp < now:
            if c.storage_key:
                storage.delete(c.storage_key)
            expired.append(c)
    repo.discard_candidates(session, expired)
    return len(expired)


def orphans(session: Session, storage: Storage) -> list[str]:
    """Stored files the database does not know about (specs/data.md: the periodic check)."""
    known = repo.known_storage_keys(session)
    return [k for k in storage.list("candidates") + storage.list("datasets") if k not in known]
