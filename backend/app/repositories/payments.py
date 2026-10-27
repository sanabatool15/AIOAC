from sqlalchemy import select

from ..db import Session
from ..db.tables import Payment


def get(session: Session, payment_id: str) -> Payment | None:
    return session.get(Payment, payment_id)


def for_quote(session: Session, quote_id: str) -> Payment | None:
    return session.scalar(select(Payment).where(Payment.quote_id == quote_id))


def for_order(session: Session, provider_order_id: str) -> Payment | None:
    return session.scalar(select(Payment).where(Payment.provider_order_id == provider_order_id))


def verified_for_project(session: Session, project_id: str) -> Payment | None:
    return session.scalar(select(Payment).where(Payment.project_id == project_id, Payment.verified.is_(True)))


def verified_for_quote(session: Session, project_id: str, quote_id: str) -> Payment | None:
    return session.scalar(select(Payment).where(Payment.project_id == project_id, Payment.quote_id == quote_id,
                                                Payment.verified.is_(True)))


def add(session: Session, **fields) -> Payment:
    pay = Payment(**fields)
    session.add(pay)
    session.commit()
    return pay


def mark_verified(session: Session, payment: Payment, capture_id: str) -> None:
    """Set only by the server after it has confirmed the capture."""
    payment.provider_capture_id = capture_id
    payment.verified = True
    session.commit()
