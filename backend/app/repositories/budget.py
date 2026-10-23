from sqlalchemy.orm import Session

from ..models import SpendBudget


class BudgetRepository:
    def __init__(self, session: Session):
        self.s = session

    def _row(self) -> SpendBudget:
        row = self.s.get(SpendBudget, 1)
        if row is None:
            row = SpendBudget(id=1, spent_cents=0)
            self.s.add(row)
            self.s.commit()
        return row

    def spent(self) -> int:
        return self._row().spent_cents

    def add_spend(self, cents: int) -> None:
        row = self._row()
        row.spent_cents += cents
        self.s.commit()
