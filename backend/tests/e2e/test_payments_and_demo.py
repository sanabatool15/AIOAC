import io
import json
import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.config import settings
from app.integrations.training_local.backend import LocalBackend
from app.ports import ProviderError, TrainingResult
from app.repositories.traces import TraceRepository
from app.services import gate, payments, training
from app.services.cost import quotes
from app.services.data import analysis, datasets, pilot
from doubles.payments import MockPaymentProvider
from tests.helpers.builders import charged, eligible_forecast, held, ready_to_pay


class ScriptedBackend:
    name, instance_type = "scripted", "x"

    def __init__(self, cost=0, fail=False):
        self.cost, self.fail = cost, fail

    def run(self, path, target, cap, on_progress=None, should_stop=None, job_key=None):
        if self.fail:
            raise RuntimeError("boom")
        return TrainingResult(0.8, 0.7, 1.0, self.cost, False, b"model")


# ---- the quote ---------------------------------------------------------------------------------------------
def test_quote_is_compute_plus_success_fee_with_a_cap(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    assert q.fee_cents > 0 and q.cap_cents == q.compute_cap_cents + q.fee_cents
    assert q.low_cents <= q.estimate_cents <= q.high_cents == q.cap_cents
    assert q.breakdown["forecast_confidence"] == 0.78
    assert pay.amount_cents == q.cap_cents and pay.compute_amount_cents == q.compute_cap_cents and pay.fee_amount_cents == q.fee_cents
    assert pay.state == "none" and not pay.verified  # the hold exists only once the server has confirmed it


def test_no_quote_without_a_forecast_or_with_an_ineligible_one(session, storage, chosen):
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    with pytest.raises(quotes.QuoteError, match="pilot"):
        quotes.create_quote(session, chosen)
    f = eligible_forecast(session, chosen)
    f.eligible, f.reason = False, "Only a 40% chance."
    session.commit()
    with pytest.raises(quotes.QuoteError, match="40%"):
        quotes.create_quote(session, chosen)


# ---- the hold ----------------------------------------------------------------------------------------------
def test_hold_confirmed_by_server_moves_to_paid_and_charges_nothing(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    assert chosen.status == "awaiting_payment"
    assert payments.confirm_hold(session, provider, pay) and pay.state == "held" and pay.verified
    assert chosen.status == "paid" and charged(session, chosen) == 0 and provider.capture_calls == []


def test_unconfirmed_hold_never_starts_training(session, storage, chosen):
    prov = MockPaymentProvider(auto_confirm=False)
    _, pay = ready_to_pay(session, storage, chosen, prov)
    assert payments.confirm_hold(session, prov, pay) is False
    assert chosen.status == "awaiting_payment" and pay.state == "none"
    with pytest.raises(gate.GateDenied):
        training.run_training(session, chosen, ScriptedBackend(), storage, prov)


def test_declined_hold_is_recorded_and_blocks_training(session, storage, chosen):
    prov = MockPaymentProvider(decline=True)
    _, pay = ready_to_pay(session, storage, chosen, prov)
    assert payments.confirm_hold(session, prov, pay) is False and pay.state == "declined"
    assert chosen.status == "awaiting_payment"
    with pytest.raises(gate.GateDenied):
        training.run_training(session, chosen, ScriptedBackend(), storage, prov)


def test_hold_of_the_wrong_amount_is_rejected(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    provider.orders[pay.provider_order_id] = 1  # PayPal would hold a different amount than we asked for
    with pytest.raises(payments.PaymentError):
        payments.confirm_hold(session, provider, pay)
    assert not pay.verified


def test_confirming_twice_is_harmless(session, storage, chosen, provider):
    q, pay = held(session, storage, chosen, provider)
    assert payments.confirm_hold(session, provider, pay) and pay.state == "held"


def test_reloading_payment_returns_the_same_approve_link(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    again, url = payments.create_order(session, provider, "mock", chosen)
    assert again.id == pay.id and url == f"mock://approve/{pay.provider_order_id}"


# ---- settle: the four outcomes -----------------------------------------------------------------------------
def test_target_verified_captures_compute_and_fee_and_releases_the_rest(session, storage, chosen, provider, verdict):
    q, pay = held(session, storage, chosen, provider)
    run = training.run_training(session, chosen, ScriptedBackend(cost=40), storage, provider)
    assert run.status == "done" and run.result["verification"]["passed"] is True and verdict["calls"] == 1
    assert pay.state == "released" and pay.compute_captured_cents == 40 and pay.fee_captured_cents == 2  # ceil(5% of 40)
    assert pay.released_cents == q.cap_cents - 40 - 2
    assert charged(session, chosen) == 42
    assert [c[1] for c in provider.capture_calls] == [40, 2] and len(provider.void_calls) == 1


def test_target_missed_still_captures_compute_but_not_the_fee(session, storage, chosen, provider, verdict):
    verdict["value"] = 0.5
    q, pay = held(session, storage, chosen, provider)
    run = training.run_training(session, chosen, ScriptedBackend(cost=40), storage, provider)
    assert run.status == "done" and chosen.status == "done" and run.result["verification"]["passed"] is False
    assert pay.state == "released" and pay.fee_captured_cents == 0 and pay.compute_captured_cents == 40
    assert charged(session, chosen) == 40 and pay.released_cents == q.cap_cents - 40  # compute only, fee not charged
    assert [c[1] for c in provider.capture_calls] == [40]


def test_user_never_pays_zero_for_compute_when_the_run_was_ours_to_finish(session, storage, chosen, provider, verdict):
    """Regression for the rule in LESSONS.md: a missed target does not mean a free run."""
    verdict["value"] = 0.1
    held(session, storage, chosen, provider)
    training.run_training(session, chosen, ScriptedBackend(cost=25), storage, provider)
    assert charged(session, chosen) == 25


def test_compute_is_never_captured_above_the_compute_cap(session, storage, chosen, provider, verdict):
    q, pay = held(session, storage, chosen, provider)
    run = training.run_training(session, chosen, ScriptedBackend(cost=99_999), storage, provider)
    assert run.cost_cents == q.compute_cap_cents and run.stopped_at_cap
    assert pay.compute_captured_cents == q.compute_cap_cents
    assert charged(session, chosen) <= q.cap_cents  # compute at the cap plus the fee fills the hold exactly
    assert pay.compute_captured_cents + pay.fee_captured_cents <= pay.amount_cents


def test_our_failure_voids_everything_and_user_pays_nothing(session, storage, chosen, provider, verdict):
    q, pay = held(session, storage, chosen, provider)
    run = training.run_training(session, chosen, ScriptedBackend(fail=True), storage, provider)
    assert run.status == "failed" and chosen.status == "voided" and pay.state == "voided"
    assert provider.capture_calls == [] and charged(session, chosen) == 0 and pay.released_cents == q.cap_cents


def test_failure_to_verify_is_our_failure_and_voids_everything(session, storage, chosen, provider, verdict):
    verdict["error"] = "BadModelFile"
    q, pay = held(session, storage, chosen, provider)
    run = training.run_training(session, chosen, ScriptedBackend(cost=40), storage, provider)
    assert run.status == "failed" and chosen.status == "voided" and pay.state == "voided"
    assert provider.capture_calls == [] and charged(session, chosen) == 0  # verify BEFORE any money is captured


def test_cancel_before_the_run_voids_the_hold(session, storage, chosen, provider):
    q, pay = held(session, storage, chosen, provider)
    payments.cancel(session, provider, chosen)
    assert pay.state == "voided" and chosen.status == "voided" and provider.capture_calls == [] and charged(session, chosen) == 0


def test_cancel_is_refused_once_the_run_started(session, storage, chosen, provider):
    held(session, storage, chosen, provider)
    training.start_training(session, chosen, ScriptedBackend())
    with pytest.raises(payments.PaymentError):
        payments.cancel(session, provider, chosen)


def test_unused_holds_expire(session, storage, chosen, provider):
    q, pay = held(session, storage, chosen, provider)
    assert payments.expire_stale_holds(session) == []
    assert settings.hold_ttl_hours == 24
    assert payments.expire_stale_holds(session, now=datetime.now(timezone.utc) + timedelta(hours=23)) == []
    assert payments.expire_stale_holds(session, now=datetime.now(timezone.utc) + timedelta(hours=100)) == [pay.id]
    assert pay.state == "expired"
    with pytest.raises(gate.GateDenied):
        gate.authorize(session, chosen, gate.Action.START_TRAINING)


def test_voiding_after_a_capture_is_refused(session, storage, chosen, provider, verdict):
    q, pay = held(session, storage, chosen, provider)
    training.run_training(session, chosen, ScriptedBackend(cost=40), storage, provider)
    pay.state = "compute_captured"  # pretend settlement stopped part-way
    session.commit()
    with pytest.raises(payments.PaymentError):
        payments.void_all(session, provider, chosen, pay)


# ---- idempotency and outages ---------------------------------------------------------------------------------
def test_settling_twice_moves_money_once(session, storage, chosen, provider, verdict):
    q, pay = held(session, storage, chosen, provider)
    run = training.run_training(session, chosen, ScriptedBackend(cost=40), storage, provider)
    before = (list(provider.capture_calls), list(provider.void_calls), charged(session, chosen))
    payments.settle(session, provider, chosen, run)
    assert (provider.capture_calls, provider.void_calls, charged(session, chosen)) == before


class FlakyProvider(MockPaymentProvider):
    """Fails the named operation until `down` is cleared, like a PayPal outage."""
    down = "void"

    def void(self, authorization_id, request_id):
        if self.down == "void":
            raise ProviderError("down")
        return super().void(authorization_id, request_id)

    def capture(self, authorization_id, amount_cents, request_id):
        if self.down == "capture":
            raise ProviderError("down")
        return super().capture(authorization_id, amount_cents, request_id)


def test_void_outage_after_captures_is_resumed_without_charging_twice(session, storage, chosen, verdict):
    prov = FlakyProvider()
    q, pay = held(session, storage, chosen, prov)
    run = training.run_training(session, chosen, ScriptedBackend(cost=40), storage, prov)
    assert run.status == "done" and pay.state == "fee_captured"  # captures done, void still owed
    assert TraceRepository(session).steps(chosen.id, ("settle_failed",))
    prov.down = None
    assert training.retry_settle(session, prov, chosen) == "released"
    assert training.retry_settle(session, prov, chosen) == "released"  # repeat is harmless
    assert [c[1] for c in prov.capture_calls] == [40, 2] and len(prov.void_calls) == 1
    assert charged(session, chosen) == 42


def test_capture_outage_leaves_the_hold_and_retry_finishes(session, storage, chosen, verdict):
    prov = FlakyProvider()
    prov.down = "capture"
    q, pay = held(session, storage, chosen, prov)
    training.run_training(session, chosen, ScriptedBackend(cost=40), storage, prov)
    assert pay.state == "held" and charged(session, chosen) == 0
    prov.down = None
    assert training.retry_settle(session, prov, chosen) == "released"
    assert charged(session, chosen) == 42


def test_failed_run_with_void_outage_ends_voided_after_retry(session, storage, chosen, verdict):
    prov = FlakyProvider()
    q, pay = held(session, storage, chosen, prov)
    training.run_training(session, chosen, ScriptedBackend(fail=True), storage, prov)
    assert chosen.status == "failed" and pay.state == "held"
    prov.down = None
    training.retry_settle(session, prov, chosen)
    assert chosen.status == "voided" and pay.state == "voided"


def test_mock_provider_enforces_the_hold_limit(provider):
    o = provider.create_hold(100, "p")
    a = provider.authorize_order(o.order_id)
    provider.capture(a.authorization_id, 60, "r1")
    assert provider.capture(a.authorization_id, 60, "r1").amount_cents == 60  # same request id: same result, no new capture
    with pytest.raises(ProviderError):
        provider.capture(a.authorization_id, 60, "r2")  # 120 > 100
    provider.void(a.authorization_id, "v1")
    with pytest.raises(ProviderError):
        provider.capture(a.authorization_id, 10, "r3")


# ---- webhooks --------------------------------------------------------------------------------------------------
def hook(event_id, capture_id, order_id="x", amount=40):
    return json.dumps({"id": event_id, "kind": "capture_completed", "order_id": order_id,
                       "capture_id": capture_id, "amount_cents": amount}).encode()


def test_webhook_for_our_capture_is_processed_once(session, storage, chosen, provider, verdict):
    q, pay = held(session, storage, chosen, provider)
    training.run_training(session, chosen, ScriptedBackend(cost=40), storage, provider)
    h = {"x-mock-signature": "valid"}
    assert payments.handle_webhook(session, provider, h, hook("E1", pay.compute_capture_id)) == "processed"
    assert payments.handle_webhook(session, provider, h, hook("E1", pay.compute_capture_id)) == "duplicate"
    assert charged(session, chosen) == 42  # a webhook never charges or credits anything


def test_webhook_cannot_create_a_hold_or_mark_paid(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    assert payments.handle_webhook(session, provider, {"x-mock-signature": "valid"},
                                   hook("E2", "CAP-UNKNOWN", pay.provider_order_id)) == "ignored"
    assert chosen.status == "awaiting_payment" and pay.state == "none" and not pay.verified


def test_webhook_with_bad_signature_is_rejected(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    with pytest.raises(payments.InvalidWebhook):
        payments.handle_webhook(session, provider, {}, hook("E3", "C"))


# ---- the demo check: real pilot, real training, real locked-set verification, mock payments ---------------------
def test_full_demo_flow_on_mock(session, storage, chosen, provider):
    """describe -> data -> readiness -> baseline -> free pilot -> forecast -> quote -> hold -> train -> verify -> settle."""
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    f = pilot.run_pilot(session, storage, chosen, 0.6)
    assert f.eligible and 0.0 <= f.band_low <= f.predicted_metric <= f.band_high <= 1.0 and charged(session, chosen) == 0
    q = quotes.create_quote(session, chosen)
    quotes.approve_quote(session, chosen, q)
    pay, _ = payments.create_order(session, provider, "mock", chosen)
    assert chosen.status == "awaiting_payment" and provider.capture_calls == []
    assert payments.confirm_hold(session, provider, pay) and chosen.status == "paid"
    run = training.run_training(session, chosen, LocalBackend(), storage, provider)
    v = run.result["verification"]
    assert run.status == "done" and chosen.status == "done" and v["rows"] > 0 and v["value"] > run.result["simple_guess_accuracy"] - 0.05
    assert v["passed"] is (v["value"] >= 0.6)
    assert pay.state == "released" and pay.released_cents + charged(session, chosen) == q.cap_cents
    assert charged(session, chosen) == pay.compute_captured_cents + pay.fee_captured_cents <= q.cap_cents


def test_baseline_ignores_row_id_columns(session, storage, project):
    """Regression from the real Telco data: a unique customerID column must not be one-hot encoded."""
    from app.services.data.samples import churn_csv
    df = pd.read_csv(io.BytesIO(churn_csv(1500)))
    df.insert(0, "customerID", [f"C{i:05d}" for i in range(len(df))])
    c = datasets.add_candidate(session, storage, project, "withid", "bundled", df.to_csv(index=False).encode())
    datasets.select_candidate(session, storage, project, c.id, "left")
    analysis.readiness(session, storage, project)
    run = analysis.baseline(session, storage, project)
    assert run.accuracy > run.simple_guess_accuracy + 0.05
    assert project.trust_level in {"Medium", "High"}


# ---- success fee is 5% of compute ----------------------------------------------------------------------------
def test_quote_fee_is_five_percent_of_compute_and_cap_is_compute_cap_plus_max_fee(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    assert q.fee_cents == math.ceil(0.05 * q.compute_cap_cents) and q.cap_cents == q.compute_cap_cents + q.fee_cents
    assert q.breakdown["success_fee_max_cents"] == q.fee_cents == pay.fee_amount_cents
    assert q.breakdown["success_fee_estimate_cents"] == math.ceil(0.05 * q.breakdown["compute_estimate_cents"])
    assert q.estimate_cents == q.breakdown["compute_estimate_cents"] + q.breakdown["success_fee_estimate_cents"]


def test_fee_is_five_percent_of_actual_compute_and_never_above_the_max(session, storage, chosen, provider, verdict):
    q, pay = held(session, storage, chosen, provider)
    training.run_training(session, chosen, ScriptedBackend(cost=99_999), storage, provider)  # compute at the cap
    assert pay.compute_captured_cents == q.compute_cap_cents and pay.fee_captured_cents == q.fee_cents
    assert pay.fee_captured_cents <= pay.fee_amount_cents and charged(session, chosen) == q.cap_cents


def test_zero_compute_means_no_fee_capture(session, storage, chosen, provider, verdict):
    held(session, storage, chosen, provider)
    run = training.run_training(session, chosen, ScriptedBackend(cost=0), storage, provider)
    pay = payments.current_payment(session, chosen.id)
    assert run.status == "done" and pay.state == "released" and pay.fee_captured_cents == 0
    assert provider.capture_calls == [] and charged(session, chosen) == 0
