"""Permission gate (specs/agent.md section 4). Ordinary code the model cannot influence.

It reads stored state, never what the model claims. Every decision is traced.
"""
from datetime import datetime, timezone
from enum import Enum

from ..db import Session
from ..db.tables import Project, Quote
from ..repositories import forecasts as forecasts_repo
from ..repositories import payments as payments_repo
from ..repositories import quotes as quotes_repo
from ..repositories.traces import TraceRepository
from .cost import budget


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


class NotReady(GateDenied):
    """Denied because of where the project is (no quote yet, not paid, already training). The API answers 409.
    A plain GateDenied is a real refusal (the global budget guard) and stays 403."""


class NeedsApproval(Exception):
    def __init__(self, card: dict):
        super().__init__(card["what"])
        self.card = card


def latest_quote(session: Session, project_id: str) -> Quote | None:
    return quotes_repo.latest_for_project(session, project_id)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def authorize(session: Session, project: Project, action: Action, user_approved: bool = False,
              now: datetime | None = None) -> Quote | None:
    """Returns the relevant quote for L2 actions. Raises GateDenied or NeedsApproval."""
    now = now or datetime.now(timezone.utc)
    trace = TraceRepository(session)

    def deny(reason: str, not_ready: bool = True):
        trace.add(project.id, "gate", {"action": action.value, "allowed": False, "reason": reason})
        raise (NotReady if not_ready else GateDenied)(reason)

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
            if payments_repo.held_for_quote(session, project.id, quote.id) is None:
                deny("no server-confirmed hold for the current quote")
            if project.status != "paid":
                deny(f"project is '{project.status}', not 'paid'")
            # The quote priced a data version and a model type. If either changed since, that price is not the work
            # that would run: refuse and ask for a new price. Quotes made before pinning have no pins and skip this.
            if quote.dataset_version_id and quote.dataset_version_id != project.chosen_dataset_version_id:
                deny("the data changed after this price was quoted; ask for a new price")
            latest = forecasts_repo.latest_for_project(session, project.id)
            if quote.family and latest is not None and latest.family and latest.family != quote.family:
                deny("the model type changed after this price was quoted; ask for a new price")
            if not budget.can_start(session, quote.compute_cap_cents):
                deny("global budget guard: not enough budget left to start a paid job", not_ready=False)

    trace.add(project.id, "gate", {"action": action.value, "allowed": True})
    return quote
