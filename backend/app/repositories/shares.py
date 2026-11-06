"""Public result links. All SQL for the `shares` table."""
from datetime import datetime

from sqlalchemy import select, update

from ..db import Session
from ..db.tables import Share


def active_for_project(session: Session, project_id: str) -> Share | None:
    return session.scalar(select(Share).where(Share.project_id == project_id, Share.revoked_at.is_(None))
                          .order_by(Share.created_at.desc()))


def add(session: Session, project_id: str, token: str) -> Share:
    sh = Share(project_id=project_id, token=token)
    session.add(sh)
    session.commit()
    return sh


def revoke_all(session: Session, project_id: str, when: datetime) -> int:
    res = session.execute(update(Share).where(Share.project_id == project_id, Share.revoked_at.is_(None)).values(revoked_at=when))
    session.commit()
    return res.rowcount


def active_by_token(session: Session, token: str) -> Share | None:
    """Lookup by the unique token index. A revoked share is the same as no share."""
    return session.scalar(select(Share).where(Share.token == token, Share.revoked_at.is_(None)))
