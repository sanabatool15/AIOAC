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
