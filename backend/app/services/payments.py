"""Payment orchestration. HUMAN REVIEW REQUIRED for any change here.

Rule 1: paid training starts only after the server confirms the capture.
"""
from sqlalchemy.orm import Session

from ..models import JobStatus
from ..providers.payments.base import PaymentProvider
from ..repositories.jobs import JobRepository
from ..repositories.ledger import LedgerRepository


def confirm_capture(session: Session, provider: PaymentProvider, job_id: str, order_id: str) -> bool:
    cap = provider.capture_order(order_id)
    if not cap.confirmed:
        return False
    LedgerRepository(session).append(job_id, "capture", cap.amount_cents, cap.capture_id)
    jobs = JobRepository(session)
    jobs.set_status(jobs.get(job_id), JobStatus.paid)
    return True
