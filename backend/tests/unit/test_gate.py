from datetime import datetime, timedelta, timezone

import pytest

from app.db.tables import Payment, Quote
from app.services import gate
from tests.helpers.builders import make_quote




def test_l0_is_free(session, project):
    gate.authorize(session, project, gate.Action.SEARCH)


def test_l1_needs_user_approval(session, project):
    with pytest.raises(gate.NeedsApproval):
        gate.authorize(session, project, gate.Action.SELECT_DATASET)
    gate.authorize(session, project, gate.Action.SELECT_DATASET, user_approved=True)


def test_payment_needs_approved_unexpired_quote(session, project):
    with pytest.raises(gate.GateDenied):
        gate.authorize(session, project, gate.Action.REQUEST_PAYMENT)
    make_quote(session, project, approved=False)
    with pytest.raises(gate.GateDenied):
        gate.authorize(session, project, gate.Action.REQUEST_PAYMENT)


def test_expired_quote_is_refused(session, project):
    make_quote(session, project, expired=True)
    with pytest.raises(gate.GateDenied, match="expired"):
        gate.authorize(session, project, gate.Action.REQUEST_PAYMENT)


def test_training_needs_verified_payment(session, project):
    q = make_quote(session, project)
    project.status = "paid"  # even a project wrongly marked paid is refused without a verified payment
    session.add(Payment(project_id=project.id, quote_id=q.id, provider="mock", provider_order_id="o", amount_cents=700, verified=False))
    session.commit()
    with pytest.raises(gate.GateDenied, match="verified"):
        gate.authorize(session, project, gate.Action.START_TRAINING)


def test_training_refused_when_budget_guard_trips(session, project):
    from app.repositories.budget import BudgetRepository
    q = make_quote(session, project)
    project.status = "paid"
    session.add(Payment(project_id=project.id, quote_id=q.id, provider="mock", provider_order_id="o", amount_cents=700, verified=True))
    session.commit()
    BudgetRepository(session).add_spend(11_500)  # ceiling is 16000 - 4000 = 12000; 11500 + 700 is over
    with pytest.raises(gate.GateDenied, match="budget"):
        gate.authorize(session, project, gate.Action.START_TRAINING)


def test_every_decision_is_traced(session, project):
    from app.repositories.traces import TraceRepository
    with pytest.raises(gate.GateDenied):
        gate.authorize(session, project, gate.Action.REQUEST_PAYMENT)
    gate.authorize(session, project, gate.Action.SEARCH)
    allowed = [s.content["allowed"] for s in TraceRepository(session).steps(project.id, ("gate",))]
    assert allowed == [False, True]
