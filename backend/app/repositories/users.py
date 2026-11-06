"""Users. Emails are stored lower-case."""
from sqlalchemy import select

from ..db import Session
from ..db.tables import User


def normalize(email: str) -> str:
    return email.strip().lower()


def get(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)


def by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == normalize(email)))


def add(session: Session, email: str, password_hash: str, org_id: str) -> User:
    """Adds the row without committing (see organizations.create)."""
    user = User(email=normalize(email), password_hash=password_hash, org_id=org_id)
    session.add(user)
    session.flush()
    return user
