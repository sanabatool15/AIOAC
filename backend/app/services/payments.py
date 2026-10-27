"""Payment orchestration. HUMAN REVIEW REQUIRED for any change here.

Model: "Forecast, then verify" (specs/payments.md). Never "pay $0 if the target is missed": the buyer always pays
the compute for the run.

  1. create_order   a PayPal HOLD for the quote's cap (compute cap + max success fee). Nothing is charged.
  2. confirm_hold   after the buyer approves, the SERVER asks PayPal to place the hold and checks the amount.
                    Only then is the payment `held` and paid work allowed (CLAUDE.md rule 1).
  3. settle         after the run and the independent check on the locked test set:
                      capture the actual compute (never above the compute cap), always;
                      capture the success fee only if the check passed;
                      void whatever is left on the hold.
  4. void_all       our failure (bug, infrastructure error) or a cancel before the run: void everything, user pays $0.

State machine on Payment.state:
  none -> held -> compute_captured -> (fee_captured | fee_skipped) -> released
  other end states: voided (our failure or cancel), expired, declined.
Every step is saved before the next one, every provider call carries an idempotency key, and settle can be called again
after a crash or a provider outage: it continues from the saved state and never moves money twice.
"""
import math
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..db import Session
from ..db.tables import Payment, Project, TrainingRun
from ..ports import PaymentProvider
from ..repositories import payments as payments_repo
from ..repositories import projects as projects_repo
from ..repositories.ledger import LedgerRepository
from ..repositories.traces import TraceRepository
from ..repositories.webhooks import WebhookRepository
from . import gate, lifecycle

TERMINAL = {"released", "voided", "expired", "declined"}
CAPTURED_OR_LATER = {"compute_captured", "fee_captured", "fee_skipped", "released"}


class PaymentError(Exception):
    pass


class InvalidWebhook(Exception):
    pass


def current_payment(session: Session, project_id: str) -> Payment | None:
    """The hold for the project's latest quote."""
    quote = gate.latest_quote(session, project_id)
    return payments_repo.for_quote(session, quote.id) if quote else None


def create_order(session: Session, provider: PaymentProvider, provider_name: str, project: Project) -> tuple[Payment, str | None]:
    quote = gate.authorize(session, project, gate.Action.REQUEST_PAYMENT)
    existing = payments_repo.for_quote(session, quote.id)
    if existing:
        return existing, existing.approve_url
    order = provider.create_hold(quote.cap_cents, project.id)
    pay = payments_repo.add(session, project_id=project.id, quote_id=quote.id, provider=provider_name,
                            provider_order_id=order.order_id, amount_cents=quote.cap_cents,
                            compute_amount_cents=quote.compute_cap_cents, fee_amount_cents=quote.fee_cents,
                            approve_url=order.approve_url, state="none")
    return pay, order.approve_url


def confirm_hold(session: Session, provider: PaymentProvider, payment: Payment) -> bool:
    """After the buyer approved in PayPal: place the hold and verify it server-side. False if not held (yet)."""
    if payment.state == "held" or payment.state in CAPTURED_OR_LATER:
        return True
    if payment.state != "none":
        return False  # voided, expired or declined: a new quote and a new hold are needed
    auth = provider.authorize_order(payment.provider_order_id)
    if auth.status == "declined":
        payments_repo.save(session, payment, state="declined")
        return False
    if auth.status != "held":
        return False
    if auth.amount_cents != payment.amount_cents:
        raise PaymentError(f"held {auth.amount_cents} but expected {payment.amount_cents}")
    payments_repo.save(session, payment, provider_authorization_id=auth.authorization_id, state="held", verified=True)
    project = projects_repo.get(session, payment.project_id)
    if project.status == "awaiting_payment":
        lifecycle.transition(session, project, "paid")
    return True


def handle_webhook(session: Session, provider: PaymentProvider, headers: dict, body: bytes) -> str:
    """Returns 'processed', 'duplicate' or 'ignored'. Raises InvalidWebhook if the signature check fails.

    A webhook can never create a hold or mark a project paid: only confirm_hold does that. Here a capture event is
    cross-checked against the captures our own server made. A capture we did not make is traced, never applied."""
    if not provider.verify_webhook(headers, body):
        raise InvalidWebhook("signature verification failed")
    event = provider.parse_webhook(body)
    if event is None:
        return "ignored"
    if not WebhookRepository(session).record_once(event.event_id, event.kind, event.raw or {}):
        return "duplicate"
    if event.kind != "capture_completed" or not event.capture_id:
        return "ignored"
    if payments_repo.for_capture(session, event.capture_id) is None:
        pay = payments_repo.for_order(session, event.order_id or "")
        TraceRepository(session).add(pay.project_id if pay else "unknown", "unexpected_capture",
                                     {"capture_id": event.capture_id, "order_id": event.order_id})
        return "ignored"
    return "processed"


def settle(session: Session, provider: PaymentProvider, project: Project, run: TrainingRun) -> Payment:
    """Capture compute, capture the fee only if verified, void the rest. Idempotent and resumable.

    Compute is the run's actual cost, never above the compute cap. The fee needs run.result['verification']['passed'].
    A run that FAILED on our side is not settled here: it goes to void_all."""
    pay = current_payment(session, project.id)
    if pay is None or not pay.verified:
        raise PaymentError("no server-confirmed hold to settle")
    if run.status == "failed":
        return void_all(session, provider, project, pay)
    ledger = LedgerRepository(session)
    if pay.state == "held":
        compute = max(0, min(run.cost_cents, pay.compute_amount_cents))
        if compute > 0:
            cap = provider.capture(pay.provider_authorization_id, compute, f"compute-{pay.id}")
            if not cap.confirmed:
                raise PaymentError("the provider did not confirm the compute capture")
            ledger.append(project.id, "compute_capture", compute, f"compute_capture:{cap.capture_id}")
            payments_repo.save(session, pay, compute_captured_cents=compute, compute_capture_id=cap.capture_id)
        payments_repo.save(session, pay, state="compute_captured")
    if pay.state == "compute_captured":
        passed = run.status == "done" and bool((run.result or {}).get("verification", {}).get("passed"))
        # the fee is a share of the compute actually captured, never above the maximum fee held
        fee = min(math.ceil(settings.success_fee_percent * pay.compute_captured_cents), pay.fee_amount_cents)
        if passed and fee > 0:
            cap = provider.capture(pay.provider_authorization_id, fee, f"fee-{pay.id}")
            if not cap.confirmed:
                raise PaymentError("the provider did not confirm the fee capture")
            ledger.append(project.id, "fee_capture", fee, f"fee_capture:{cap.capture_id}")
            payments_repo.save(session, pay, fee_captured_cents=fee, fee_capture_id=cap.capture_id, state="fee_captured")
        else:
            payments_repo.save(session, pay, state="fee_skipped")
    if pay.state in {"fee_captured", "fee_skipped"}:
        left = pay.amount_cents - pay.compute_captured_cents - pay.fee_captured_cents
        if left > 0:
            provider.void(pay.provider_authorization_id, f"void-{pay.id}")
        payments_repo.save(session, pay, released_cents=left, state="released")
    return pay


def void_all(session: Session, provider: PaymentProvider, project: Project, pay: Payment | None = None) -> Payment:
    """Our failure, or a cancel before the run: release the whole hold. The user pays $0.
    Only possible while nothing has been captured."""
    pay = pay or current_payment(session, project.id)
    if pay is None:
        raise PaymentError("there is no hold to void")
    if pay.state in TERMINAL:
        return pay
    if pay.state == "none":
        payments_repo.save(session, pay, state="voided")  # the buyer never approved: there is no hold at the provider
        return pay
    if pay.state != "held":
        raise PaymentError(f"money was already captured ({pay.state}); it cannot be voided")
    provider.void(pay.provider_authorization_id, f"void-{pay.id}")
    payments_repo.save(session, pay, state="voided", released_cents=pay.amount_cents)
    return pay


def cancel(session: Session, provider: PaymentProvider, project: Project) -> Payment:
    """The user changes their mind after the hold and before training starts. Releases everything."""
    if project.status not in {"awaiting_payment", "paid"}:
        raise PaymentError("it is too late to cancel: the run has started or finished")
    pay = current_payment(session, project.id)
    if pay is None:
        raise PaymentError("there is no hold to cancel")
    lifecycle.transition(session, project, "stopped")
    void_all(session, provider, project, pay)
    lifecycle.transition(session, project, "voided")
    return pay


def expire_stale_holds(session: Session, now: datetime | None = None) -> list[str]:
    """Holds that were never used end as `expired` after hold_ttl_hours. PayPal lets a hold lapse by itself."""
    now = now or datetime.now(timezone.utc)
    out = []
    for pay in payments_repo.open_before(session, now - timedelta(hours=settings.hold_ttl_hours)):
        if projects_repo.get(session, pay.project_id).status in {"awaiting_payment", "paid"}:
            payments_repo.save(session, pay, state="expired")
            out.append(pay.id)
    return out
