"""The quote pins the data version and the model type; the paid run trains exactly that type (HUMAN REVIEW area)."""
import pytest

from app.repositories import forecasts as forecasts_repo
from app.repositories import training_runs as runs_repo
from app.services import payments, training
from app.services.cost import quotes
from app.services.data import analysis, families, pilot
from tests.e2e.test_payments_and_demo import ScriptedBackend


def piloted(session, storage, chosen, target=0.6):
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    return pilot.run_pilot(session, storage, chosen, target)


def paid(session, provider, chosen):
    q = quotes.create_quote(session, chosen)
    quotes.approve_quote(session, chosen, q)
    pay, _ = payments.create_order(session, provider, "mock", chosen)
    assert payments.confirm_hold(session, provider, pay)
    return q


def test_the_quote_pins_the_data_version_and_the_family_of_the_pilot(session, storage, chosen):
    f = piloted(session, storage, chosen)
    assert f.eligible and f.family in families.FAMILIES
    q = quotes.create_quote(session, chosen)
    assert q.family == f.family and q.dataset_version_id == chosen.chosen_dataset_version_id


def test_the_cost_is_timed_on_the_chosen_family(session, storage, chosen):
    f = piloted(session, storage, chosen)
    slow = [[100, 30000.0], [200, 60000.0], [400, 120000.0]]  # made-up timings of the chosen type: a very slow model
    f.pilot = {**f.pilot, "cost_samples": slow}
    session.commit()
    with pytest.raises(Exception, match="above the per-job maximum"):
        quotes.create_quote(session, chosen)  # the quote follows the chosen family's timings, not the forest baseline's


def test_a_forecast_from_other_data_cannot_be_quoted(session, storage, chosen):
    f = piloted(session, storage, chosen)
    f.dataset_version_id = "some-other-version"
    session.commit()
    with pytest.raises(quotes.QuoteError, match="data changed"):
        quotes.create_quote(session, chosen)


@pytest.mark.parametrize("family", families.FAMILIES)
def test_the_paid_run_trains_the_family_the_quote_pinned(session, storage, chosen, provider, verdict, family):
    piloted(session, storage, chosen)
    forecasts_repo.latest_for_project(session, chosen.id).family = family
    session.commit()
    paid(session, provider, chosen)
    backend = ScriptedBackend(cost=10)
    run = training.run_training(session, chosen, backend, storage, provider)
    assert run.status == "done" and backend.families == [family]
    assert runs_repo.current_model(session, chosen.id).family == family
