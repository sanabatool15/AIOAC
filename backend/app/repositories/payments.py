from datetime import datetime

from sqlalchemy import select

from ..db import Session
from ..db.tables import Payment


def get(session: Session, payment_id: str) -> Payment | None:
    return session.get(Payment, payment_id)


def for_quote(session: Session, quote_id: str) -> Payment | None:
    return session.scalar(select(Payment).where(Payment.quote_id == quote_id))


def for_order(session: Session, provider_order_id: str) -> Payment | None:
    return session.scalar(select(Payment).where(Payment.provider_order_id == provider_order_id))


def for_capture(session: Session, capture_id: str) -> Payment | None:
    """The payment that one of OUR captures (compute or fee) belongs to."""
    return session.scalar(select(Payment).where((Payment.compute_capture_id == capture_id)
                                                | (Payment.fee_capture_id == capture_id)))


def held_for_quote(session: Session, project_id: str, quote_id: str) -> Payment | None:
    """The hold the server confirmed and nothing has been captured from yet: the only state that allows paid work."""
    return session.scalar(select(Payment).where(Payment.project_id == project_id, Payment.quote_id == quote_id,
                                                Payment.verified.is_(True), Payment.state == "held"))


def open_before(session: Session, cutoff: datetime) -> list[Payment]:
    """Holds that were never used (not approved or not trained on) and are older than `cutoff`."""
    return [p for p in session.scalars(select(Payment).where(Payment.state.in_(("none", "held"))))
            if (p.created_at if p.created_at.tzinfo else p.created_at.replace(tzinfo=cutoff.tzinfo)) < cutoff]


def add(session: Session, **fields) -> Payment:
    pay = Payment(**fields)
    session.add(pay)
    session.commit()
    return pay


def save(session: Session, payment: Payment, **values) -> None:
    """Record a step of the payment state machine. `verified` is set only by the server after PayPal confirmed the hold."""
    for k, v in values.items():
        setattr(payment, k, v)
    session.commit()
