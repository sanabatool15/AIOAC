"""Real PayPal SANDBOX checks of the money model: hold, two partial captures on one hold, void, repeat safety.
Sandbox only (PayPalProvider refuses any other host). Amounts are tiny: a 50 cent hold, 20 cents of compute, a 5 cent fee.

Step 1 (needs only the sandbox keys in .env; moves no money):
    RUN_REAL=1 pytest tests/real/test_paypal_sandbox.py -k create -v -s
  It prints an approval link. Open it, sign in as the sandbox BUYER account and approve. Note the order id it prints.

Step 2 (after the buyer approved; captures 25 cents of sandbox money and voids the other 25):
    PAYPAL_APPROVED_ORDER_ID=<order id> RUN_REAL=1 pytest tests/real/test_paypal_sandbox.py -k lifecycle -v -s
  Check the sandbox dashboard afterwards: 25 cents charged (20 compute + 5 fee), 25 cents released.
"""
import os

import httpx
import pytest

from app.ports import ProviderError
from tests.real.conftest import need

HOLD, COMPUTE, FEE = 50, 20, 5


@pytest.fixture
def provider(real_settings):
    need(real_settings.paypal_client_id, "PAYPAL_CLIENT_ID")
    need(real_settings.paypal_client_secret, "PAYPAL_CLIENT_SECRET")
    from app.integrations.paypal.provider import PayPalProvider

    assert httpx.URL(real_settings.paypal_base_url).host == "api-m.sandbox.paypal.com"
    return PayPalProvider()


def test_create_hold_order(provider):
    order = provider.create_hold(HOLD, "real-test-project")
    print("\norder id:", order.order_id, "\napprove here as the sandbox BUYER:", order.approve_url)
    assert order.order_id
    assert order.approve_url and "paypal.com" in order.approve_url


def test_hold_lifecycle_two_captures_and_void(provider):
    order_id = os.environ.get("PAYPAL_APPROVED_ORDER_ID")
    if not order_id:
        pytest.skip("set PAYPAL_APPROVED_ORDER_ID to an order the sandbox buyer has approved (see the file docstring)")
    key = order_id[-8:]

    auth = provider.authorize_order(order_id)
    assert auth.status == "held", "the buyer may not have approved yet; nothing was captured"
    assert auth.amount_cents == HOLD
    assert provider.authorize_order(order_id).authorization_id == auth.authorization_id  # a repeat is safe

    compute = provider.capture(auth.authorization_id, COMPUTE, f"check-compute-{key}")
    fee = provider.capture(auth.authorization_id, FEE, f"check-fee-{key}")  # a second capture on the SAME hold
    assert compute.confirmed and fee.confirmed and compute.capture_id != fee.capture_id
    assert provider.capture(auth.authorization_id, COMPUTE, f"check-compute-{key}").capture_id == compute.capture_id

    provider.void(auth.authorization_id, f"check-void-{key}")  # releases the remaining 25 cents
    provider.void(auth.authorization_id, f"check-void-{key}")  # a repeat is harmless
    with pytest.raises(ProviderError):
        provider.capture(auth.authorization_id, 1, f"check-late-{key}")  # nothing can be captured after the void
