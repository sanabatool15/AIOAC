"""Regression tests for the payment breakpoints P1-P8 and U7 (specs/breakpoints.md). One test group per bug."""
import pytest

from app.repositories import payments as payments_repo
from app.services import payments
from doubles.payments import MockPaymentProvider
from tests.helpers.builders import held, ready_to_pay


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
