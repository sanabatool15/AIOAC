from datetime import datetime, timezone

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


def all_for_project(session: Session, project_id: str) -> list[Quote]:
    return list(session.scalars(select(Quote).where(Quote.project_id == project_id).order_by(Quote.created_at.desc(), Quote.id.desc())))


def expire(session: Session, quote: Quote) -> None:
    """The price was for data that has since changed: it can no longer be approved."""
    quote.expires_at = datetime.now(timezone.utc)
    session.commit()
