"""PayPal provider tests on a mocked HTTP transport (no network, no credentials)."""
import json

import httpx
import pytest

from app.integrations.paypal.provider import PayPalError, PayPalProvider, cents_to_value, value_to_cents


def make(handler, webhook_id="WH-1"):
    calls = []

    def wrapped(req: httpx.Request):
        calls.append(req)
        if req.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return handler(req)

    p = PayPalProvider("id", "secret", webhook_id, "https://api-m.sandbox.paypal.com",
                       client=httpx.Client(transport=httpx.MockTransport(wrapped)))
    return p, calls


def test_money_conversion():
    assert cents_to_value(700) == "7.00" and cents_to_value(53) == "0.53" and cents_to_value(5) == "0.05"
    assert value_to_cents("7.00") == 700 and value_to_cents("0.5") == 50 and value_to_cents("12") == 1200


def test_live_host_is_refused():
    with pytest.raises(PayPalError):
        PayPalProvider("a", "b", "c", "https://api-m.paypal.com")


def test_create_hold_sends_authorize_intent_and_returns_payer_link():
    def h(req):
        body = json.loads(req.content)
        assert req.url.path == "/v2/checkout/orders" and req.headers["authorization"] == "Bearer tok"
        assert body["intent"] == "AUTHORIZE"
        assert body["purchase_units"][0]["amount"] == {"currency_code": "USD", "value": "8.00"}
        assert body["purchase_units"][0]["custom_id"] == "proj1" and req.headers["paypal-request-id"]
        return httpx.Response(201, json={"id": "ORD1", "links": [{"rel": "self", "href": "x"}, {"rel": "payer-action", "href": "https://pp/approve"}]})

    p, _ = make(h)
    o = p.create_hold(800, "proj1")
    assert o.order_id == "ORD1" and o.approve_url == "https://pp/approve"


def auth_json(status="CREATED", value="8.00"):
    return {"id": "ORD1", "status": "COMPLETED", "purchase_units": [{"payments": {"authorizations": [
        {"id": "AUTH1", "status": status, "amount": {"currency_code": "USD", "value": value}}]}}]}


def test_authorize_reports_held_declined_and_pending():
    p, _ = make(lambda r: httpx.Response(201, json=auth_json()))
    a = p.authorize_order("ORD1")
    assert (a.status, a.authorization_id, a.amount_cents) == ("held", "AUTH1", 800)
    p, _ = make(lambda r: httpx.Response(201, json=auth_json(status="DENIED")))
    assert p.authorize_order("ORD1").status == "declined"
    p, _ = make(lambda r: httpx.Response(201, json=auth_json(status="PENDING")))
    assert p.authorize_order("ORD1").status == "pending"  # never treated as held
    p, _ = make(lambda r: httpx.Response(201, json={"id": "ORD1", "purchase_units": [{}]}))
    assert p.authorize_order("ORD1").status == "pending"


def test_authorize_error_raises_and_a_repeat_reads_the_order():
    p, _ = make(lambda r: httpx.Response(500, json={}))
    with pytest.raises(PayPalError):
        p.authorize_order("ORD1")

    def h(req):
        if req.method == "POST":
            return httpx.Response(422, json={"details": [{"issue": "SOMETHING"}]})
        return httpx.Response(200, json=auth_json())

    p, _ = make(h)
    assert p.authorize_order("ORD1").status == "held"  # decided from the order, not from an error code


def test_capture_is_partial_not_final_and_keyed():
    def h(req):
        assert req.url.path == "/v2/payments/authorizations/AUTH1/capture" and req.headers["paypal-request-id"] == "compute-1"
        body = json.loads(req.content)
        assert body["amount"] == {"currency_code": "USD", "value": "0.40"} and body["final_capture"] is False
        return httpx.Response(201, json={"id": "CAP1", "status": "COMPLETED"})

    p, _ = make(h)
    c = p.capture("AUTH1", 40, "compute-1")
    assert c.confirmed and c.capture_id == "CAP1" and c.amount_cents == 40
    p, _ = make(lambda r: httpx.Response(201, json={"id": "CAP1", "status": "PENDING"}))
    assert not p.capture("AUTH1", 40, "x").confirmed
    p, _ = make(lambda r: httpx.Response(500, json={}))
    with pytest.raises(PayPalError):
        p.capture("AUTH1", 40, "x")


def test_void_request_and_previous_void_is_fine():
    def h(req):
        assert req.url.path == "/v2/payments/authorizations/AUTH1/void" and req.headers["paypal-request-id"] == "void-1"
        return httpx.Response(204)

    p, _ = make(h)
    assert p.void("AUTH1", "void-1")
    p, _ = make(lambda r: httpx.Response(422, text='{"details":[{"issue":"PREVIOUSLY_VOIDED"}]}'))
    assert p.void("AUTH1", "void-1")
    p, _ = make(lambda r: httpx.Response(422, text='{"details":[{"issue":"PREVIOUSLY_CAPTURED"}]}'))
    with pytest.raises(PayPalError):
        p.void("AUTH1", "void-1")


HEADERS = {"PayPal-Transmission-Id": "t1", "PayPal-Transmission-Time": "2026-10-24T00:00:00Z",
           "PayPal-Cert-Url": "https://api.sandbox.paypal.com/cert", "PayPal-Transmission-Sig": "sig", "PayPal-Auth-Algo": "SHA256withRSA"}
EVENT = b'{"id":"WH-EVT-1",  "event_type":"PAYMENT.CAPTURE.COMPLETED","resource":{"id":"CAP1","amount":{"currency_code":"USD","value":"7.00"},"supplementary_data":{"related_ids":{"order_id":"ORD1"}}}}'


def test_webhook_verification_posts_raw_body_unchanged():
    seen = {}

    def h(req):
        seen["raw"] = req.content
        return httpx.Response(200, json={"verification_status": "SUCCESS"})

    p, _ = make(h)
    assert p.verify_webhook(HEADERS, EVENT) is True
    sent = json.loads(seen["raw"])
    assert sent["webhook_id"] == "WH-1" and sent["transmission_id"] == "t1" and sent["auth_algo"] == "SHA256withRSA"
    assert EVENT in seen["raw"]  # byte-for-byte, not re-serialised


def test_webhook_rejected_when_failure_missing_headers_or_no_webhook_id():
    p, _ = make(lambda r: httpx.Response(200, json={"verification_status": "FAILURE"}))
    assert p.verify_webhook(HEADERS, EVENT) is False
    p, calls = make(lambda r: httpx.Response(200, json={"verification_status": "SUCCESS"}))
    assert p.verify_webhook({}, EVENT) is False
    p2, _ = make(lambda r: httpx.Response(200, json={"verification_status": "SUCCESS"}), webhook_id="")
    assert p2.verify_webhook(HEADERS, EVENT) is False
    p3, _ = make(lambda r: httpx.Response(500))
    assert p3.verify_webhook(HEADERS, EVENT) is False


def test_parse_capture_completed_and_other_events():
    p, _ = make(lambda r: httpx.Response(200))
    e = p.parse_webhook(EVENT)
    assert (e.kind, e.event_id, e.order_id, e.capture_id, e.amount_cents) == ("capture_completed", "WH-EVT-1", "ORD1", "CAP1", 700)
    o = p.parse_webhook(b'{"id":"E2","event_type":"CHECKOUT.ORDER.APPROVED","resource":{}}')
    assert o.kind == "other"


def test_bad_credentials_raise_without_leaking_secret():
    def transport(req):
        return httpx.Response(401, json={"error": "invalid_client"})

    p = PayPalProvider("id", "supersecret", "w", client=httpx.Client(transport=httpx.MockTransport(transport)))
    with pytest.raises(PayPalError) as ei:
        p.create_hold(100, "p")
    assert "supersecret" not in str(ei.value)
