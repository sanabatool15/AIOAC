"""Permission gate (specs/agent.md section 4). Ordinary code the model cannot influence.

It reads stored state, never what the model claims. Every decision is traced.
"""
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Payment, Project, Quote
from ..repositories.traces import TraceRepository
from . import budget


class Action(str, Enum):
    SEARCH = "search"
    DISCOVER = "discover"
    FETCH = "fetch"
    ANALYZE = "analyze"
    BASELINE = "baseline"
    CLEAN = "clean"
    CREATE_QUOTE = "create_quote"
    PILOT = "pilot"
    SELECT_DATASET = "select_dataset"
    REQUEST_PAYMENT = "request_payment"
    START_TRAINING = "start_training"


LEVEL = {
    Action.SEARCH: 0, Action.DISCOVER: 0, Action.FETCH: 0, Action.ANALYZE: 0, Action.BASELINE: 0, Action.CLEAN: 0, Action.CREATE_QUOTE: 0, Action.PILOT: 0,
    Action.SELECT_DATASET: 1,
    Action.REQUEST_PAYMENT: 2, Action.START_TRAINING: 2,
}


class GateDenied(Exception):
    pass


class NeedsApproval(Exception):
    def __init__(self, card: dict):
        super().__init__(card["what"])
        self.card = card


def latest_quote(session: Session, project_id: str) -> Quote | None:
    return session.scalar(select(Quote).where(Quote.project_id == project_id).order_by(Quote.created_at.desc()))


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def authorize(session: Session, project: Project, action: Action, user_approved: bool = False,
              now: datetime | None = None) -> Quote | None:
    """Returns the relevant quote for L2 actions. Raises GateDenied or NeedsApproval."""
    now = now or datetime.now(timezone.utc)
    trace = TraceRepository(session)

    def deny(reason: str):
        trace.add(project.id, "gate", {"action": action.value, "allowed": False, "reason": reason})
        raise GateDenied(reason)

    level = LEVEL[action]
    quote = None
    if level == 1 and not user_approved:
        card = {"what": f"The agent wants to {action.value.replace('_', ' ')}", "level": 1}
        trace.add(project.id, "gate", {"action": action.value, "allowed": False, "reason": "needs user approval"})
        raise NeedsApproval(card)

    if level == 2:
        quote = latest_quote(session, project.id)
        if quote is None:
            deny("no quote exists")
        if action == Action.REQUEST_PAYMENT:
            if quote.approved_at is None:
                deny("the quote has not been approved by the user")
            if _aware(quote.expires_at) < now:
                deny("the approved quote has expired")
        if action == Action.START_TRAINING:
            paid = session.scalar(select(Payment).where(Payment.project_id == project.id, Payment.quote_id == quote.id,
                                                        Payment.verified.is_(True), Payment.state == "held"))
            if paid is None:
                deny("no server-confirmed hold for the current quote")
            if project.status != "paid":
                deny(f"project is '{project.status}', not 'paid'")
            if not budget.can_start(session, quote.compute_cap_cents):
                deny("global budget guard: not enough budget left to start a paid job")

    trace.add(project.id, "gate", {"action": action.value, "allowed": True})
    return quote
