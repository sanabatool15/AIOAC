"""Payment orchestration. HUMAN REVIEW REQUIRED for any change here.

Rule 1: paid work starts only after the SERVER verifies the capture.
By proposal the buyer is charged the quote's cap and unused money is refunded (specs/payments.md).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Payment, Project, Quote, TrainingRun
from ..providers.payments.base import PaymentProvider
from ..repositories.ledger import LedgerRepository
from ..repositories.webhooks import WebhookRepository
from . import gate, lifecycle


class PaymentError(Exception):
    pass


class InvalidWebhook(Exception):
    pass


def create_order(session: Session, provider: PaymentProvider, provider_name: str, project: Project) -> tuple[Payment, str | None]:
    quote = gate.authorize(session, project, gate.Action.REQUEST_PAYMENT)
    existing = session.scalar(select(Payment).where(Payment.quote_id == quote.id))
    if existing:
        return existing, existing.approve_url
    order = provider.create_order(quote.cap_cents, project.id)
    pay = Payment(project_id=project.id, quote_id=quote.id, provider=provider_name,
                  provider_order_id=order.order_id, amount_cents=quote.cap_cents,
                  approve_url=order.approve_url)
    session.add(pay)
    session.commit()
    return pay, order.approve_url


def _apply_capture(session: Session, payment: Payment, capture_id: str, amount_cents: int) -> bool:
    """Record a confirmed capture exactly once. Safe to call repeatedly."""
    if amount_cents != payment.amount_cents:
        raise PaymentError(f"captured {amount_cents} but expected {payment.amount_cents}")
    if not payment.verified:
        payment.provider_capture_id = capture_id
        payment.verified = True
        session.commit()
    LedgerRepository(session).append(payment.project_id, "capture", amount_cents, f"capture:{capture_id}")
    project = session.get(Project, payment.project_id)
    if project.status == "awaiting_payment":
        lifecycle.transition(session, project, "paid")
    return True


def confirm_capture(session: Session, provider: PaymentProvider, payment: Payment) -> bool:
    """Capture through the provider and verify it server-side. False if the provider did not confirm."""
    if payment.verified:
        return True
    cap = provider.capture_order(payment.provider_order_id)
    if not cap.confirmed:
        return False
    return _apply_capture(session, payment, cap.capture_id, cap.amount_cents)


def handle_webhook(session: Session, provider: PaymentProvider, headers: dict, body: bytes) -> str:
    """Returns 'processed', 'duplicate' or 'ignored'. Raises InvalidWebhook if the signature check fails."""
    if not provider.verify_webhook(headers, body):
        raise InvalidWebhook("signature verification failed")
    event = provider.parse_webhook(body)
    if event is None:
        return "ignored"
    if not WebhookRepository(session).record_once(event.event_id, event.kind, event.raw or {}):
        return "duplicate"
    if event.kind != "capture_completed" or not event.order_id:
        return "ignored"
    payment = session.scalar(select(Payment).where(Payment.provider_order_id == event.order_id))
    if payment is None:
        return "ignored"
    _apply_capture(session, payment, event.capture_id, event.amount_cents)
    return "processed"


def settle(session: Session, provider: PaymentProvider, project: Project, run: TrainingRun) -> int:
    """Record actual usage and refund the unused amount. Idempotent per training run. Returns cents refunded."""
    payment = session.scalar(select(Payment).where(Payment.project_id == project.id, Payment.verified.is_(True)))
    if payment is None:
        raise PaymentError("no verified payment to settle")
    ledger = LedgerRepository(session)
    ledger.append(project.id, "usage", -run.cost_cents, f"usage:{run.id}")
    refund = payment.amount_cents - run.cost_cents
    if refund <= 0 or ledger.has_key(f"refund:{run.id}"):
        return 0
    provider.refund(payment.provider_capture_id, refund)
    ledger.append(project.id, "refund", -refund, f"refund:{run.id}")
    return refund
