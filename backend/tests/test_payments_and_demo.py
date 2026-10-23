import json

import pytest

from app.providers.payments.mock import MockPaymentProvider
from app.providers.training.base import TrainingResult
from app.providers.training.local import LocalBackend
from app.repositories.ledger import LedgerRepository
from app.services import analysis, gate, payments, quotes, training


class ScriptedBackend:
    name, instance_type = "scripted", "x"

    def __init__(self, cost=0, fail=False):
        self.cost, self.fail = cost, fail

    def run(self, path, target, cap):
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
