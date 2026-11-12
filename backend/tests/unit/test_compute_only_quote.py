"""Slice S13 (HUMAN REVIEW: quotes, payments behaviour): a kind of task with no success fee is quoted and settled compute-only."""
import pytest

from app.services import payments, training
from app.services.cost import quotes
from app.services.data import analysis, tasks
from app.services.data.tasks.classification import ClassificationTask
from tests.helpers.builders import charged, eligible_forecast


class NoFeeTask(ClassificationTask):
    id, supports_fee = "grouping", False


@pytest.fixture
def compute_only(monkeypatch, session, chosen):
    monkeypatch.setitem(tasks.TASKS, "grouping", NoFeeTask())
    chosen.task_type = "grouping"
    session.commit()
    return chosen


def test_the_quote_has_no_fee_and_the_hold_is_compute_only(session, storage, compute_only, provider):
    analysis.readiness(session, storage, compute_only)
    analysis.baseline(session, storage, compute_only)
    eligible_forecast(session, compute_only)
    q = quotes.create_quote(session, compute_only)
    assert q.fee_cents == 0 and q.cap_cents == q.compute_cap_cents and q.breakdown["success_fee_max_cents"] == 0
    assert q.estimate_cents == q.breakdown["compute_estimate_cents"]


def test_settle_with_no_fee_captures_compute_only_skips_the_fee_and_voids_the_rest(session, storage, compute_only, provider, verdict):
    from tests.e2e.test_payments_and_demo import ScriptedBackend
    from tests.helpers.builders import held
    q, pay = held(session, storage, compute_only, provider)
    run = training.run_training(session, compute_only, ScriptedBackend(cost=40), storage, provider)
    assert run.status == "done" and pay.state == "released" and pay.fee_amount_cents == 0
    assert pay.fee_captured_cents == 0 and pay.compute_captured_cents == 40 and pay.released_cents == q.cap_cents - 40
    assert [c[1] for c in provider.capture_calls] == [40] and charged(session, compute_only) == 40
    n = len(provider.capture_calls)
    payments.settle(session, provider, compute_only, run)   # a repeat moves no money
    assert len(provider.capture_calls) == n and charged(session, compute_only) == 40
