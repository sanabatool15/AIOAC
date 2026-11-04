"""Regression tests for the payment breakpoints P1-P8 and U7 (specs/breakpoints.md). One test group per bug."""
import pytest

from app.repositories import payments as payments_repo
from app.ports import Capture
from app.repositories.traces import TraceRepository
from app.services import payments, training
from app.services.payments import PaymentError
from doubles.payments import MockPaymentProvider
from tests.helpers.builders import charged, held, ready_to_pay


# ---- P1: a saved hold whose move to `paid` never happened -------------------------------------------------------
def test_p1_confirm_hold_finishes_the_paid_transition_when_already_held(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    # the hold was saved as confirmed, but the process died before the project moved to `paid`
    payments_repo.save(session, pay, provider_authorization_id="A1", state="held", verified=True)
    assert chosen.status == "awaiting_payment"
    assert payments.confirm_hold(session, provider, pay) is True
    assert chosen.status == "paid"


# ---- P2: a new quote must never orphan a hold ------------------------------------------------------------------
def test_p2_new_quote_is_refused_while_a_hold_exists(session, storage, chosen, provider):
    from app.services.cost import quotes
    q, pay = held(session, storage, chosen, provider)
    chosen.status = "awaiting_payment"  # the stuck state P1 describes: a confirmed hold, project not yet paid
    session.commit()
    with pytest.raises(quotes.QuoteError, match="hold"):
        quotes.create_quote(session, chosen)
    assert pay.state == "held" and provider.void_calls == []  # nothing orphaned, nothing voided


def test_p2_new_quote_is_refused_after_payment_started(session, storage, chosen, provider):
    from app.services.cost import quotes
    held(session, storage, chosen, provider)  # project is now `paid`
    with pytest.raises(quotes.QuoteError):
        quotes.create_quote(session, chosen)


def test_p2_new_quote_supersedes_an_unheld_order(session, storage, chosen, provider):
    from app.services.cost import quotes
    q, pay = ready_to_pay(session, storage, chosen, provider)  # order created, buyer has not approved
    q2 = quotes.create_quote(session, chosen)
    assert q2.id != q.id and pay.state == "voided" and chosen.status == "quoted"
    assert provider.void_calls == [] and provider.holds == {}  # nothing was ever held at the provider


# ---- P3: a PaymentError during settle must not crash or strand the project --------------------------------------
class UnconfirmedCaptureProvider(MockPaymentProvider):
    """The provider answers a capture but does not confirm it (settle raises PaymentError, not ProviderError)."""
    unconfirmed = True

    def capture(self, authorization_id, amount_cents, request_id):
        cap = super().capture(authorization_id, amount_cents, request_id)
        return Capture(cap.capture_id, cap.amount_cents, False) if self.unconfirmed else cap


def _backend(cost=0, fail=False):
    from tests.e2e.test_payments_and_demo import ScriptedBackend
    return ScriptedBackend(cost=cost, fail=fail)


def test_p3_unconfirmed_capture_is_traced_not_crashed_and_retry_finishes(session, storage, chosen, verdict):
    prov = UnconfirmedCaptureProvider()
    q, pay = held(session, storage, chosen, prov)
    run = training.run_training(session, chosen, _backend(cost=40), storage, prov)  # must not raise
    assert run.status == "done" and chosen.status == "done" and pay.state == "held"
    assert TraceRepository(session).steps(chosen.id, ("settle_failed",))
    assert charged(session, chosen) == 0  # nothing recorded as charged without provider confirmation
    prov.unconfirmed = False
    assert training.retry_settle(session, prov, chosen) == "released"
    assert charged(session, chosen) == 42


def test_p3_retry_settle_moves_a_project_left_in_training_to_done(session, storage, chosen, provider, verdict):
    q, pay = held(session, storage, chosen, provider)
    run = training.run_training(session, chosen, _backend(cost=40), storage, provider)
    chosen.status = "training"  # the worker died after settling but before the last status change
    session.commit()
    assert training.retry_settle(session, provider, chosen) == "released"
    assert chosen.status == "done"
    assert [c[1] for c in provider.capture_calls] == [40, 2]  # no second capture


def test_p3_failed_run_with_unconfirmed_state_ends_voided_after_retry(session, storage, chosen):
    prov = FlakyVoid()
    q, pay = held(session, storage, chosen, prov)
    training.run_training(session, chosen, _backend(fail=True), storage, prov)
    assert chosen.status == "failed" and pay.state == "held"
    prov.down = False
    training.retry_settle(session, prov, chosen)
    assert chosen.status == "voided" and pay.state == "voided"


class FlakyVoid(MockPaymentProvider):
    down = True

    def void(self, authorization_id, request_id):
        if self.down:
            raise PaymentError("provider did not confirm the void")
        return super().void(authorization_id, request_id)


# ---- P4: cancel must void before it changes the project status -----------------------------------------------
def test_p4_cancel_with_a_void_outage_keeps_the_project_cancellable(session, storage, chosen):
    from app.ports import ProviderError

    class Down(MockPaymentProvider):
        down = True

        def void(self, authorization_id, request_id):
            if self.down:
                raise ProviderError("down")
            return super().void(authorization_id, request_id)

    prov = Down()
    q, pay = held(session, storage, chosen, prov)
    with pytest.raises(ProviderError):
        payments.cancel(session, prov, chosen)
    assert chosen.status == "paid" and pay.state == "held"  # not stranded in `stopped` with a live hold
    prov.down = False
    payments.cancel(session, prov, chosen)  # the same request can simply be repeated
    assert chosen.status == "voided" and pay.state == "voided" and charged(session, chosen) == 0
