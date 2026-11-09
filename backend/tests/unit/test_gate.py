
import pytest

from app.db.tables import Payment
from app.services import gate
from tests.helpers.builders import make_quote




def test_l0_is_free(session, project):
    gate.authorize(session, project, gate.Action.SEARCH)


def test_l1_needs_user_approval(session, project):
    with pytest.raises(gate.NeedsApproval):
        gate.authorize(session, project, gate.Action.SELECT_DATASET)
    gate.authorize(session, project, gate.Action.SELECT_DATASET, user_approved=True)


def test_changing_the_users_data_needs_their_approval(session, project):
    assert gate.LEVEL[gate.Action.CLEAN] == 1
    with pytest.raises(gate.NeedsApproval):
        gate.authorize(session, project, gate.Action.CLEAN)
    gate.authorize(session, project, gate.Action.CLEAN, user_approved=True)


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


def test_training_needs_a_server_confirmed_hold(session, project):
    q = make_quote(session, project)
    project.status = "paid"  # even a project wrongly marked paid is refused without a verified payment
    session.add(Payment(project_id=project.id, quote_id=q.id, provider="mock", provider_order_id="o", amount_cents=700, verified=False, state="none"))
    session.commit()
    with pytest.raises(gate.GateDenied, match="hold"):
        gate.authorize(session, project, gate.Action.START_TRAINING)


def test_training_refused_when_budget_guard_trips(session, project):
    from app.repositories.budget import BudgetRepository
    q = make_quote(session, project)
    project.status = "paid"
    session.add(Payment(project_id=project.id, quote_id=q.id, provider="mock", provider_order_id="o", amount_cents=700, verified=True, state="held"))
    session.commit()
    BudgetRepository(session).add_spend(11_500)  # ceiling is 16000 - 4000 = 12000; 11500 + 600 (compute cap) is over
    with pytest.raises(gate.GateDenied, match="budget"):
        gate.authorize(session, project, gate.Action.START_TRAINING)


def test_every_decision_is_traced(session, project):
    from app.repositories.traces import TraceRepository
    with pytest.raises(gate.GateDenied):
        gate.authorize(session, project, gate.Action.REQUEST_PAYMENT)
    gate.authorize(session, project, gate.Action.SEARCH)
    allowed = [s.content["allowed"] for s in TraceRepository(session).steps(project.id, ("gate",))]
    assert allowed == [False, True]


def test_a_hold_that_is_not_held_does_not_count(session, project):
    q = make_quote(session, project)
    project.status = "paid"
    session.add(Payment(project_id=project.id, quote_id=q.id, provider="mock", provider_order_id="o", amount_cents=700,
                        verified=True, state="declined"))
    session.commit()
    with pytest.raises(gate.GateDenied, match="hold"):
        gate.authorize(session, project, gate.Action.START_TRAINING)


def test_pilot_is_free(session, project):
    gate.authorize(session, project, gate.Action.PILOT)


# ---- the quote pins the data version and the model type (HUMAN REVIEW) --------------------------------------
def _paid_with_quote(session, project, **pins):
    q = make_quote(session, project)
    for k, v in pins.items():
        setattr(q, k, v)
    project.status = "paid"
    session.add(Payment(project_id=project.id, quote_id=q.id, provider="mock", provider_order_id="o", amount_cents=700,
                        verified=True, state="held"))
    session.commit()
    return q


def test_training_refused_when_the_data_version_changed_after_the_quote(session, project):
    project.chosen_dataset_version_id = "v2"
    _paid_with_quote(session, project, dataset_version_id="v1", family="forest")
    with pytest.raises(gate.NotReady, match="data changed"):
        gate.authorize(session, project, gate.Action.START_TRAINING)


def test_training_refused_when_the_model_type_changed_after_the_quote(session, project):
    from app.repositories import forecasts as forecasts_repo
    project.chosen_dataset_version_id = "v1"
    forecasts_repo.add(session, project_id=project.id, target=0.8, predicted_metric=0.8, band_low=0.7, band_high=0.9,
                       confidence=0.8, eligible=True, pilot={}, family="boosting")
    _paid_with_quote(session, project, dataset_version_id="v1", family="forest")
    with pytest.raises(gate.NotReady, match="model type"):
        gate.authorize(session, project, gate.Action.START_TRAINING)


def test_training_allowed_when_pins_match_and_for_old_quotes_without_pins(session, project):
    from app.repositories import forecasts as forecasts_repo
    project.chosen_dataset_version_id = "v1"
    forecasts_repo.add(session, project_id=project.id, target=0.8, predicted_metric=0.8, band_low=0.7, band_high=0.9,
                       confidence=0.8, eligible=True, pilot={}, family="forest")
    _paid_with_quote(session, project, dataset_version_id="v1", family="forest")
    assert gate.authorize(session, project, gate.Action.START_TRAINING) is not None


def test_old_quote_without_pins_is_not_checked(session, project):
    project.chosen_dataset_version_id = "anything"
    _paid_with_quote(session, project)
    assert gate.authorize(session, project, gate.Action.START_TRAINING) is not None
