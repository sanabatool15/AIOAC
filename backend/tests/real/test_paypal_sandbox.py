"""Proves: the PayPal SANDBOX credentials in .env work: we get a token and can create a 1.00 USD order with an
approval link. It does NOT capture, so no money (not even sandbox money) moves. The order is never approved and expires.

Sandbox only (PayPalProvider refuses any other host). Run: RUN_REAL=1 pytest tests/real/test_paypal_sandbox.py -v -s
"""
import httpx

from tests.real.conftest import need


def test_token_and_create_order(real_settings):
    need(real_settings.paypal_client_id, "PAYPAL_CLIENT_ID")
    need(real_settings.paypal_client_secret, "PAYPAL_CLIENT_SECRET")
    from app.integrations.paypal.provider import PayPalProvider

    assert httpx.URL(real_settings.paypal_base_url).host == "api-m.sandbox.paypal.com"
    p = PayPalProvider()
    order = p.create_order(100, "real-test-project")
    print("order:", order.order_id, order.approve_url)
    assert order.order_id
    assert order.approve_url and "paypal.com" in order.approve_url
