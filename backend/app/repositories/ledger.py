from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import LedgerEntry


class LedgerRepository:
    """Append-only. There is intentionally no update or delete method."""

    def __init__(self, session: Session):
        self.s = session

    def append(self, job_id: str, kind: str, amount_cents: int, idempotency_key: str) -> bool:
        """Returns False if this idempotency_key was already recorded."""
        try:
            with self.s.begin_nested():
                self.s.add(LedgerEntry(job_id=job_id, kind=kind, amount_cents=amount_cents,
                                       idempotency_key=idempotency_key))
            self.s.commit()
            return True
        except IntegrityError:
            return False

    def balance(self, job_id: str) -> int:
        q = select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0)).where(LedgerEntry.job_id == job_id)
        return self.s.scalar(q)
