"""Global budget guard (specs/cost.md section 4)."""
from sqlalchemy.orm import Session

from ..config import settings
from ..repositories.budget import BudgetRepository


def ceiling_cents() -> int:
    return settings.aws_budget_cents - settings.reserve_cents


def can_start(session: Session, cap_cents: int) -> bool:
    return BudgetRepository(session).spent() + cap_cents <= ceiling_cents()
