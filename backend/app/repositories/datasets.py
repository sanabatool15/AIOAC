"""Dataset candidates (temporary) and dataset versions (permanent)."""
from typing import Callable

from sqlalchemy import select

from ..db import Session
from ..db.tables import DatasetCandidate, DatasetVersion, Project


def get_candidate(session: Session, candidate_id: str) -> DatasetCandidate | None:
    return session.get(DatasetCandidate, candidate_id)


def get_version(session: Session, version_id: str) -> DatasetVersion | None:
    return session.get(DatasetVersion, version_id)


def add_candidate(session: Session, store: Callable[[DatasetCandidate], str], **fields) -> DatasetCandidate:
    """Insert the row, let `store(candidate)` write the file and return its key, then commit."""
    cand = DatasetCandidate(**fields)
    session.add(cand)
    session.flush()
    cand.storage_key = store(cand)
    session.commit()
    return cand


def choose_candidate(session: Session, project: Project, cand: DatasetCandidate,
                     delete_file: Callable[[str], None], **version_fields) -> DatasetVersion:
    """Create the permanent version, discard every other candidate of the project and point the project at it."""
    version = DatasetVersion(project_id=project.id, **version_fields)
    session.add(version)
    session.flush()
    for other in session.scalars(select(DatasetCandidate).where(DatasetCandidate.project_id == project.id)):
        if other.storage_key:
            delete_file(other.storage_key)
        other.status = "chosen" if other.id == cand.id else "discarded"
        other.storage_key = None
    project.chosen_dataset_version_id = version.id
    session.commit()
    return version


def count_versions(session: Session, project_id: str) -> int:
    return len(list(session.scalars(select(DatasetVersion).where(DatasetVersion.project_id == project_id))))


def add_version(session: Session, **fields) -> DatasetVersion:
    new = DatasetVersion(**fields)
    session.add(new)
    session.commit()
    return new


def open_candidates(session: Session) -> list[DatasetCandidate]:
    return list(session.scalars(select(DatasetCandidate).where(DatasetCandidate.status == "candidate")))


def discard_candidates(session: Session, candidates: list[DatasetCandidate]) -> None:
    for c in candidates:
        c.status, c.storage_key = "discarded", None
    session.commit()


def known_storage_keys(session: Session) -> set[str]:
    known = {c.storage_key for c in session.scalars(select(DatasetCandidate)) if c.storage_key}
    known |= {v.storage_key for v in session.scalars(select(DatasetVersion))}
    return known
