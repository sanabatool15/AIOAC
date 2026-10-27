from datetime import datetime

from sqlalchemy import select

from ..db import Session
from ..db.tables import Quote


def latest_for_project(session: Session, project_id: str) -> Quote | None:
    return session.scalar(select(Quote).where(Quote.project_id == project_id).order_by(Quote.created_at.desc()))


def add(session: Session, **fields) -> Quote:
    q = Quote(**fields)
    session.add(q)
    session.commit()
    return q


def mark_approved(session: Session, quote: Quote, when: datetime) -> None:
    quote.approved_at = when
    session.commit()
