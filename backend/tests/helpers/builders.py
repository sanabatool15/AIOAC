"""Small builders shared by tests in every layer."""
from datetime import datetime, timedelta, timezone

from app.db.tables import Quote
from app.repositories import forecasts as forecasts_repo
from app.repositories.ledger import LedgerRepository
from app.integrations.training_local.backend import LocalBackend
from app.ports import LLMResponse, ToolCall
from app.services.agent.tools import ToolContext
from app.services.data import analysis
from app.services.cost import quotes
from app.services import payments

from .fakes import FakeSource


def ctx(session, storage, provider, project, approved=(), source=None):
    return ToolContext(session, project, storage, provider, "mock", LocalBackend(), source or FakeSource(), set(approved))


def call(name, **args):
    return LLMResponse(tool_calls=[ToolCall(f"c-{name}", name, args)])


def make_quote(session, project, approved=True, expired=False):
    exp = datetime.now(timezone.utc) + timedelta(minutes=-5 if expired else 60)
    q = Quote(project_id=project.id, instance_type="x", estimate_cents=500, low_cents=400, high_cents=700, cap_cents=700,
              breakdown={}, compute_cap_cents=600, fee_cents=30, prices_version="t", expires_at=exp, approved_at=datetime.now(timezone.utc) if approved else None)
    session.add(q)
    session.commit()
    return q


TARGET = 0.8


def eligible_forecast(session, project, target=TARGET, confidence=0.78):
    """A stored eligible forecast, for tests that are about money and not about the pilot."""
    return forecasts_repo.add(session, project_id=project.id, target=target, predicted_metric=0.82, band_low=0.76,
                              band_high=0.88, confidence=confidence, eligible=True, pilot={})


def ready_to_pay(session, storage, chosen, provider, target=TARGET):
    """Everything up to the hold being requested (not yet approved by the buyer)."""
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    eligible_forecast(session, chosen, target)
    q = quotes.create_quote(session, chosen)
    quotes.approve_quote(session, chosen, q)
    pay, _ = payments.create_order(session, provider, "mock", chosen)
    return q, pay


def held(session, storage, chosen, provider, target=TARGET):
    """The buyer approved and the server confirmed the hold: the project is paid, nothing is captured yet."""
    q, pay = ready_to_pay(session, storage, chosen, provider, target)
    assert payments.confirm_hold(session, provider, pay)
    return q, pay


def charged(session, project):
    """What the buyer has really been charged: the sum of the ledger."""
    return LedgerRepository(session).balance(project.id)
