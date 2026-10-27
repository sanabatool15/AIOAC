import json

import pytest

from doubles.payments import MockPaymentProvider
from app.ports import TrainingResult
from app.integrations.training_local.backend import LocalBackend
from app.repositories.ledger import LedgerRepository
from app.services.data import analysis
from app.services import gate, payments, training
from app.services.cost import quotes


class ScriptedBackend:
    name, instance_type = "scripted", "x"

    def __init__(self, cost=0, fail=False):
        self.cost, self.fail = cost, fail

    def run(self, path, target, cap, on_progress=None, should_stop=None, job_key=None):
        if self.fail:
            raise RuntimeError("boom")
        return TrainingResult(0.8, 0.7, 1.0, self.cost, False, b"model")


def ready_to_pay(session, storage, chosen, provider):
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    q = quotes.create_quote(session, chosen)
    quotes.approve_quote(session, chosen, q)
    pay, _ = payments.create_order(session, provider, "mock", chosen)
    return q, pay


def test_full_demo_flow_on_mock(session, storage, chosen, provider):
    """The demo check: describe -> data -> readiness -> baseline -> quote -> pay -> train -> refund."""
    q, pay = ready_to_pay(session, storage, chosen, provider)
    assert pay.amount_cents == q.cap_cents and chosen.status == "awaiting_payment"
    assert payments.confirm_capture(session, provider, pay) and chosen.status == "paid"
    run = training.run_training(session, chosen, LocalBackend(), storage, provider)
    assert run.status == "done" and chosen.status == "done" and run.result["accuracy"] > run.result["simple_guess_accuracy"]
    assert provider.refunds == [(pay.provider_capture_id, q.cap_cents)]  # local training costs nothing: full refund
    assert LedgerRepository(session).balance(chosen.id) == 0


def test_cost_never_exceeds_cap_and_no_refund_when_capped(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    payments.confirm_capture(session, provider, pay)
    run = training.run_training(session, chosen, ScriptedBackend(cost=99_999), storage, provider)
    assert run.cost_cents == q.cap_cents and run.stopped_at_cap and provider.refunds == []


def test_partial_refund_is_cap_minus_actual(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    payments.confirm_capture(session, provider, pay)
    training.run_training(session, chosen, ScriptedBackend(cost=q.cap_cents - 20), storage, provider)
    assert provider.refunds[0][1] == 20


def test_failed_job_refunds_everything(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    payments.confirm_capture(session, provider, pay)
    run = training.run_training(session, chosen, ScriptedBackend(fail=True), storage, provider)
    assert run.status == "failed" and chosen.status == "refunded" and provider.refunds[0][1] == q.cap_cents


def test_unconfirmed_payment_never_starts_training(session, storage, chosen):
    prov = MockPaymentProvider(auto_confirm=False)
    _, pay = ready_to_pay(session, storage, chosen, prov)
    assert payments.confirm_capture(session, prov, pay) is False
    assert chosen.status == "awaiting_payment"
    with pytest.raises(gate.GateDenied):
        training.run_training(session, chosen, ScriptedBackend(), storage, prov)


def test_capture_is_idempotent(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    payments.confirm_capture(session, provider, pay)
    payments.confirm_capture(session, provider, pay)
    assert LedgerRepository(session).balance(chosen.id) == q.cap_cents


def hook(event_id, pay, amount):
    return json.dumps({"id": event_id, "kind": "capture_completed", "order_id": pay.provider_order_id,
                       "capture_id": f"MOCK-CAP-{pay.provider_order_id}", "amount_cents": amount}).encode()


def test_webhook_confirms_once_and_repeat_is_harmless(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    h = {"x-mock-signature": "valid"}
    assert payments.handle_webhook(session, provider, h, hook("E1", pay, q.cap_cents)) == "processed"
    assert payments.handle_webhook(session, provider, h, hook("E1", pay, q.cap_cents)) == "duplicate"
    assert chosen.status == "paid" and LedgerRepository(session).balance(chosen.id) == q.cap_cents


def test_webhook_with_bad_signature_is_rejected(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    with pytest.raises(payments.InvalidWebhook):
        payments.handle_webhook(session, provider, {}, hook("E2", pay, q.cap_cents))
    assert chosen.status == "awaiting_payment"


def test_webhook_with_wrong_amount_is_rejected(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    with pytest.raises(payments.PaymentError):
        payments.handle_webhook(session, provider, {"x-mock-signature": "valid"}, hook("E3", pay, 1))


def test_baseline_ignores_row_id_columns(session, storage, project):
    """Regression from the real Telco data: a unique customerID column must not be one-hot encoded."""
    import io
    import pandas as pd
    from app.services.data.samples import churn_csv
    from app.services.data import datasets
    df = pd.read_csv(io.BytesIO(churn_csv(1500)))
    df.insert(0, "customerID", [f"C{i:05d}" for i in range(len(df))])
    c = datasets.add_candidate(session, storage, project, "withid", "bundled", df.to_csv(index=False).encode())
    datasets.select_candidate(session, storage, project, c.id, "left")
    analysis.readiness(session, storage, project)
    run = analysis.baseline(session, storage, project)
    assert run.accuracy > run.simple_guess_accuracy + 0.05
    assert project.trust_level in {"Medium", "High"}


class FlakyRefundProvider(MockPaymentProvider):
    """Refund fails until `fail_refunds` is set to False, like a PayPal outage."""
    fail_refunds = True

    def refund(self, capture_id, amount_cents):
        if self.fail_refunds:
            from app.ports import ProviderError
            raise ProviderError("down")
        return super().refund(capture_id, amount_cents)


def test_refund_outage_is_recorded_and_can_be_retried(session, storage, chosen):
    prov = FlakyRefundProvider()
    q, pay = ready_to_pay(session, storage, chosen, prov)
    payments.confirm_capture(session, prov, pay)
    run = training.run_training(session, chosen, ScriptedBackend(cost=10), storage, prov)
    assert run.status == "done" and chosen.status == "done" and prov.refunds == []
    from app.repositories.traces import TraceRepository
    assert TraceRepository(session).steps(chosen.id, ("refund_failed",))
    owed = LedgerRepository(session).balance(chosen.id)
    assert owed == q.cap_cents - 10  # money still owed back is visible in the ledger
    prov.fail_refunds = False
    assert training.retry_refund(session, prov, chosen) == q.cap_cents - 10
    assert training.retry_refund(session, prov, chosen) == 0  # repeat is harmless
    assert len(prov.refunds) == 1 and LedgerRepository(session).balance(chosen.id) == 0


def test_failed_job_with_refund_outage_ends_refunded_after_retry(session, storage, chosen):
    prov = FlakyRefundProvider()
    q, pay = ready_to_pay(session, storage, chosen, prov)
    payments.confirm_capture(session, prov, pay)
    training.run_training(session, chosen, ScriptedBackend(fail=True), storage, prov)
    assert chosen.status == "failed"
    prov.fail_refunds = False
    training.retry_refund(session, prov, chosen)
    assert chosen.status == "refunded" and prov.refunds[0][1] == q.cap_cents


def test_reloading_payment_returns_the_same_approve_link(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    again, url = payments.create_order(session, provider, "mock", chosen)
    assert again.id == pay.id and url == f"mock://approve/{pay.provider_order_id}"
