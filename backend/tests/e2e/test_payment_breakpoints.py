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


# ---- P5: a late authorize must not create a hold nobody will void -----------------------------------------------
def test_p5_late_authorize_after_the_project_left_awaiting_payment_creates_no_hold(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    chosen.status = "stopped"  # e.g. the project ended while the buyer was still on the PayPal page
    session.commit()
    with pytest.raises(PaymentError):
        payments.confirm_hold(session, provider, pay)
    assert provider.holds == {} and pay.state == "none" and not pay.verified


def test_p5_authorize_after_cancel_does_not_hold(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    payments.cancel(session, provider, chosen)
    assert payments.confirm_hold(session, provider, pay) is False
    assert provider.holds == {} and pay.state == "voided"


def test_p5_project_changing_during_authorize_voids_the_new_authorization(session, storage, chosen):
    class Racy(MockPaymentProvider):
        def authorize_order(self, order_id):
            auth = super().authorize_order(order_id)
            chosen.status = "stopped"  # a cancel/failure lands while PayPal is answering
            session.commit()
            return auth

    prov = Racy()
    q, pay = ready_to_pay(session, storage, chosen, prov)
    with pytest.raises(PaymentError):
        payments.confirm_hold(session, prov, pay)
    assert pay.state == "voided" and not pay.verified and len(prov.void_calls) == 1


# ---- P6: a hold of the wrong amount must not stay at PayPal ---------------------------------------------------
def test_p6_wrong_amount_hold_is_voided_before_raising(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    provider.orders[pay.provider_order_id] = 1  # PayPal holds a different amount than we asked for
    with pytest.raises(PaymentError):
        payments.confirm_hold(session, provider, pay)
    assert len(provider.void_calls) == 1 and provider.void_calls[0] in provider.voided
    assert pay.state == "voided" and not pay.verified and chosen.status == "awaiting_payment"


# ---- P7: a dead payment is never handed out again; expiry releases the hold at the provider ---------------------
from datetime import datetime, timedelta, timezone  # noqa: E402


@pytest.mark.parametrize("dead", ["expired", "declined", "voided"])
def test_p7_create_order_refuses_a_dead_payment_and_a_new_quote_gets_a_new_hold(session, storage, chosen, provider, dead):
    from app.services.cost import quotes
    q, pay = ready_to_pay(session, storage, chosen, provider)
    payments_repo.save(session, pay, state=dead)
    with pytest.raises(PaymentError, match="new quote"):
        payments.create_order(session, provider, "mock", chosen)  # was: the dead payment and its link, forever
    q2 = quotes.create_quote(session, chosen)
    quotes.approve_quote(session, chosen, q2)
    pay2, url = payments.create_order(session, provider, "mock", chosen)
    assert pay2.id != pay.id and pay2.state == "none" and url


def test_p7_expiry_voids_the_authorization_at_the_provider(session, storage, chosen, provider):
    q, pay = held(session, storage, chosen, provider)
    auth = pay.provider_authorization_id
    later = datetime.now(timezone.utc) + timedelta(hours=100)
    assert payments.expire_stale_holds(session, now=later, provider=provider) == [pay.id]
    assert pay.state == "expired" and auth in provider.voided and pay.released_cents == pay.amount_cents


def test_p7_expiry_stays_held_if_the_provider_void_fails(session, storage, chosen):
    from app.ports import ProviderError

    class Down(MockPaymentProvider):
        def void(self, authorization_id, request_id):
            raise ProviderError("down")

    prov = Down()
    q, pay = held(session, storage, chosen, prov)
    later = datetime.now(timezone.utc) + timedelta(hours=100)
    assert payments.expire_stale_holds(session, now=later, provider=prov) == []
    assert pay.state == "held"  # not marked expired while the hold may still exist at PayPal


# ---- P8a: two /train requests must create exactly one run -------------------------------------------------------
def test_p8_second_train_request_with_a_stale_status_creates_no_second_run(session, storage, chosen, provider):
    from sqlalchemy.orm import Session as OrmSession
    from app.db.tables import Project, TrainingRun
    from app.services import gate
    from sqlalchemy import select
    held(session, storage, chosen, provider)
    other = OrmSession(bind=session.get_bind(), expire_on_commit=False)  # a second request, same database
    stale = other.get(Project, chosen.id)
    assert stale.status == "paid"
    training.start_training(session, chosen, _backend())  # request 1 wins
    with pytest.raises(gate.GateDenied):
        training.start_training(other, stale, _backend())  # request 2 still believes the project is `paid`
    assert len(list(session.scalars(select(TrainingRun).where(TrainingRun.project_id == chosen.id)))) == 1
    other.close()


# ---- P8b: two /payments/orders requests for one quote return one payment, not a 500 -------------------------------
def test_p8_concurrent_create_order_returns_the_winners_payment(session, storage, chosen):
    from sqlalchemy.orm import Session as OrmSession

    class Racy(MockPaymentProvider):
        raced = False

        def create_hold(self, amount_cents, project_id):
            order = super().create_hold(amount_cents, project_id)
            if not self.raced:  # another request finishes first, while this one waits for PayPal
                self.raced = True
                from app.services import gate
                other = OrmSession(bind=session.get_bind(), expire_on_commit=False)
                quote = gate.latest_quote(other, project_id)
                winner_order = super().create_hold(amount_cents, project_id)
                payments_repo.add(other, project_id=project_id, quote_id=quote.id, provider="mock",
                                  provider_order_id=winner_order.order_id, amount_cents=quote.cap_cents,
                                  compute_amount_cents=quote.compute_cap_cents, fee_amount_cents=quote.fee_cents,
                                  approve_url=winner_order.approve_url, state="none")
                other.close()
            return order

    prov = Racy()
    q, pay = ready_to_pay(session, storage, chosen, MockPaymentProvider())  # quote approved; order made by a plain double
    session.delete(pay)
    session.commit()
    got, url = payments.create_order(session, prov, "mock", chosen)
    assert got.quote_id == q.id and got.state == "none" and url == got.approve_url
    assert payments_repo.for_quote(session, q.id).id == got.id
