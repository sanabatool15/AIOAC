"""PayPal sandbox provider (Orders v2 authorize, Payments v2 capture and void, webhook signature verification).

Endpoints, fields and statuses were checked against PayPal's published OpenAPI specs
(developer.paypal.com/api/{orders/v2,payments/v2,webhooks/v1}/schema.json). Sandbox only:
the base URL refuses anything but the sandbox host.
"""
import json
import time
import uuid

import httpx

from ...config import settings
from ...ports import Authorization, Capture, Order, PaymentEvent, ProviderError

SANDBOX_HOST = "api-m.sandbox.paypal.com"
CURRENCY = "USD"


class PayPalError(ProviderError):
    pass


def cents_to_value(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def value_to_cents(value: str) -> int:
    whole, _, frac = value.partition(".")
    return int(whole) * 100 + int((frac + "00")[:2])


class PayPalProvider:
    def __init__(self, client_id: str | None = None, client_secret: str | None = None,
                 webhook_id: str | None = None, base_url: str | None = None,
                 client: httpx.Client | None = None):
        self.client_id = client_id if client_id is not None else settings.paypal_client_id
        self.client_secret = client_secret if client_secret is not None else settings.paypal_client_secret
        self.webhook_id = webhook_id if webhook_id is not None else settings.paypal_webhook_id
        self.base_url = (base_url or settings.paypal_base_url).rstrip("/")
        if httpx.URL(self.base_url).host != SANDBOX_HOST:
            raise PayPalError("Only the PayPal sandbox is allowed")
        self.http = client or httpx.Client(timeout=30)
        self._token: str | None = None
        self._token_expires = 0.0

    # --- auth ---
    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        r = self.http.post(f"{self.base_url}/v1/oauth2/token", auth=(self.client_id, self.client_secret),
                           data={"grant_type": "client_credentials"})
        if r.status_code != 200:
            raise PayPalError(f"PayPal authentication failed ({r.status_code})")
        d = r.json()
        self._token = d["access_token"]
        self._token_expires = time.time() + int(d.get("expires_in", 300))
        return self._token

    def _request(self, method: str, path: str, request_id: str | None = None, **kw) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id  # makes retries safe (PayPal dedupes on it)
        return self.http.request(method, f"{self.base_url}{path}", headers=headers, **kw)

    # --- PaymentProvider interface ---
    # Hold = Orders v2 with intent AUTHORIZE, then POST /v2/checkout/orders/{id}/authorize after the buyer approves.
    # Capture = POST /v2/payments/authorizations/{id}/capture with an amount and final_capture=false (so a second,
    # smaller capture for the success fee is possible). Void = POST /v2/payments/authorizations/{id}/void.
    # Checked against developer.paypal.com/api/{orders,payments}/v2/schema.json on 2026-10-27. NOT yet run against the
    # sandbox: authorize after buyer approval, two partial captures on one hold, and void of the remainder.
    def create_hold(self, amount_cents: int, project_id: str) -> Order:
        body = {
            "intent": "AUTHORIZE",
            "purchase_units": [{
                "custom_id": project_id,
                "description": "AIOAC model training: a hold for the maximum price. You are charged for the compute used, "
                               "plus the success fee only if the result is verified. Anything left on the hold is released.",
                "amount": {"currency_code": CURRENCY, "value": cents_to_value(amount_cents)},
            }],
            "payment_source": {"paypal": {"experience_context": {
                "return_url": settings.paypal_return_url,
                "cancel_url": settings.paypal_cancel_url,
                "user_action": "CONTINUE",
                "shipping_preference": "NO_SHIPPING",
            }}},
        }
        r = self._request("POST", "/v2/checkout/orders", request_id=f"order-{uuid.uuid4()}", json=body)
        if r.status_code not in (200, 201):
            raise PayPalError(f"Could not create PayPal order ({r.status_code})")
        d = r.json()
        links = {l["rel"]: l["href"] for l in d.get("links", [])}
        return Order(d["id"], links.get("payer-action") or links.get("approve"))

    def authorize_order(self, order_id: str) -> Authorization:
        r = self._request("POST", f"/v2/checkout/orders/{order_id}/authorize", request_id=f"authorize-{order_id}")
        if r.status_code == 422:
            # Either this order is already authorized (a repeat call) or the buyer has not approved it yet.
            # Read the order instead of guessing from an error code: authorizations present means held, otherwise pending.
            r = self._request("GET", f"/v2/checkout/orders/{order_id}")
        if r.status_code not in (200, 201):
            raise PayPalError(f"Could not authorize PayPal order ({r.status_code})")
        d = r.json()
        auths = [a for u in d.get("purchase_units", []) for a in u.get("payments", {}).get("authorizations", [])]
        if not auths:
            return Authorization("", 0, "pending")
        a = auths[0]
        status = {"CREATED": "held", "DENIED": "declined"}.get(a.get("status"), "pending")  # PENDING stays pending
        return Authorization(a["id"], value_to_cents(a["amount"]["value"]), status)

    def capture(self, authorization_id: str, amount_cents: int, request_id: str) -> Capture:
        body = {"amount": {"currency_code": CURRENCY, "value": cents_to_value(amount_cents)}, "final_capture": False}
        r = self._request("POST", f"/v2/payments/authorizations/{authorization_id}/capture",
                          request_id=request_id, json=body)
        if r.status_code not in (200, 201):
            raise PayPalError(f"Could not capture the PayPal hold ({r.status_code})")
        d = r.json()
        return Capture(d["id"], amount_cents, d.get("status") == "COMPLETED")

    def void(self, authorization_id: str, request_id: str) -> str:
        r = self._request("POST", f"/v2/payments/authorizations/{authorization_id}/void", request_id=request_id)
        if r.status_code in (200, 204) or (r.status_code == 422 and "PREVIOUSLY_VOIDED" in r.text):
            return f"void-{authorization_id}"
        raise PayPalError(f"Could not void the PayPal hold ({r.status_code})")

    def verify_webhook(self, headers: dict, body: bytes) -> bool:
        h = {k.lower(): v for k, v in headers.items()}
        fields = {"auth_algo": h.get("paypal-auth-algo"), "cert_url": h.get("paypal-cert-url"),
                  "transmission_id": h.get("paypal-transmission-id"), "transmission_sig": h.get("paypal-transmission-sig"),
                  "transmission_time": h.get("paypal-transmission-time"), "webhook_id": self.webhook_id}
        if not self.webhook_id or not all(fields.values()):
            return False
        # PayPal needs the event exactly as received, so splice the raw body in without re-serialising it.
        payload = (json.dumps(fields)[:-1] + ', "webhook_event": ' + body.decode() + "}").encode()
        try:
            r = self._request("POST", "/v1/notifications/verify-webhook-signature", content=payload)
        except httpx.HTTPError:
            return False
        return r.status_code == 200 and r.json().get("verification_status") == "SUCCESS"

    def parse_webhook(self, body: bytes) -> PaymentEvent | None:
        d = json.loads(body)
        res = d.get("resource", {})
        if d.get("event_type") != "PAYMENT.CAPTURE.COMPLETED":
            return PaymentEvent(event_id=d["id"], kind="other", raw=d)
        order_id = res.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
        amount = res.get("amount", {}).get("value")
        return PaymentEvent(event_id=d["id"], kind="capture_completed", order_id=order_id, capture_id=res.get("id"),
                            amount_cents=value_to_cents(amount) if amount else None, raw=d)
