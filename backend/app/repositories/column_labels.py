"""Cached plain-English column labels. All SQL for the `column_labels` table."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db import Session
from ..db.tables import ColumnLabel


def get(session: Session, dataset_version_id: str) -> dict | None:
    """The stored {column: label} for this version, or None if nothing was saved."""
    row = session.scalar(select(ColumnLabel).where(ColumnLabel.dataset_version_id == dataset_version_id))
    return None if row is None else dict(row.labels)


def save(session: Session, dataset_version_id: str, labels: dict, model: str | None) -> None:
    """Store labels once per version. A second save (a race) is ignored: the first one wins."""
    session.add(ColumnLabel(dataset_version_id=dataset_version_id, labels=labels, model=model))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
