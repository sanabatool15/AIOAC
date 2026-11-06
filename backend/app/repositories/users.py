"""Users. Emails are stored lower-case."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db import Session
from ..db.tables import Organization, User


def normalize(email: str) -> str:
    return email.strip().lower()


def get(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)


def by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == normalize(email)))



def create_with_org(session: Session, email: str, password_hash: str, org_name: str) -> User | None:
    """The organization and the user in ONE transaction. None if the email is already registered (nothing is saved)."""
    try:
        org = Organization(name=org_name)
        session.add(org)
        session.flush()
        user = User(email=normalize(email), password_hash=password_hash, org_id=org.id)
        session.add(user)
        session.commit()
    except IntegrityError:
        session.rollback()
        return None
    return user
