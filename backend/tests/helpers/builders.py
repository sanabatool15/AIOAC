"""Small builders shared by tests in every layer."""
from datetime import datetime, timedelta, timezone

from app.db.tables import Quote
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
              breakdown={}, prices_version="t", expires_at=exp, approved_at=datetime.now(timezone.utc) if approved else None)
    session.add(q)
    session.commit()
    return q


def ready_to_pay(session, storage, chosen, provider):
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    q = quotes.create_quote(session, chosen)
    quotes.approve_quote(session, chosen, q)
    pay, _ = payments.create_order(session, provider, "mock", chosen)
    return q, pay
