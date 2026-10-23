from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import LedgerEntry


class NegativeBalance(Exception):
    pass


class LedgerRepository:
    """Append-only: there is intentionally no update or delete method."""

    def __init__(self, session: Session):
        self.s = session

    def balance(self, project_id: str) -> int:
        q = select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0)).where(LedgerEntry.project_id == project_id)
        return self.s.scalar(q)

    def has_key(self, key: str) -> bool:
        return self.s.scalar(select(LedgerEntry.id).where(LedgerEntry.idempotency_key == key)) is not None

    def append(self, project_id: str, kind: str, amount_cents: int, idempotency_key: str) -> bool:
        """Returns False if this key was already recorded (a repeat is harmless)."""
        if self.has_key(idempotency_key):
            return False
        if self.balance(project_id) + amount_cents < 0:
            raise NegativeBalance(f"{kind} of {amount_cents} would take the balance below zero")
        try:
            with self.s.begin_nested():
                self.s.add(LedgerEntry(project_id=project_id, kind=kind, amount_cents=amount_cents,
                                       idempotency_key=idempotency_key))
            self.s.commit()
            return True
        except IntegrityError:
            return False
