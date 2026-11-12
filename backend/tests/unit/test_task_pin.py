"""Slice S5 (HUMAN REVIEW: quotes, gate): the quote pins the task type; changing it after the price is refused."""
import pytest

from app.services import gate, training
from app.services.data import datasets
from tests.e2e.test_payments_and_demo import ScriptedBackend
from tests.helpers.builders import held
from tests.helpers.ml_slices import house_csv


def test_a_quote_records_the_task_type_of_the_project(session, storage, chosen, provider):
    q, _ = held(session, storage, chosen, provider)
    assert q.task_type == "classification"


def test_a_regression_quote_records_regression(session, storage, project, provider):
    from app.services.cost import quotes
    from app.services.data import analysis, pilot
    project.task_type = "regression"
    c = datasets.add_candidate(session, storage, project, "houses", "bundled", house_csv(1500))
    datasets.select_candidate(session, storage, project, c.id, "price")
    analysis.readiness(session, storage, project)
    analysis.baseline_detailed(session, storage, project)
    assert pilot.run_pilot(session, storage, project, 0.4).eligible
    assert quotes.create_quote(session, project).task_type == "regression"


def test_training_is_refused_if_the_task_changed_after_the_quote(session, storage, chosen, provider):
    q, _ = held(session, storage, chosen, provider)
    chosen.task_type = "regression"   # the project's task changed after the price was quoted
    session.commit()
    with pytest.raises(gate.GateDenied, match="kind of prediction changed"):
        training.run_training(session, chosen, ScriptedBackend(), storage, provider)


def test_an_old_quote_without_a_task_type_skips_the_check(session, storage, chosen, provider, verdict):
    q, _ = held(session, storage, chosen, provider)
    q.task_type = None   # a row written before this column existed
    chosen.task_type = "regression"
    session.commit()
    gate.authorize(session, chosen, gate.Action.START_TRAINING)   # not refused on the task
