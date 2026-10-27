import json
import uuid

from app.ports import Capture, Order, PaymentEvent


class MockPaymentProvider:
    """In-memory provider for tests and local demos. Never talks to PayPal."""

    def __init__(self, auto_confirm: bool = True):
        self.orders: dict[str, int] = {}
        self.captured: dict[str, int] = {}
        self.refunds: list[tuple[str, int]] = []
        self.auto_confirm = auto_confirm

    def create_order(self, amount_cents: int, project_id: str) -> Order:
        oid = f"MOCK-ORDER-{uuid.uuid4().hex[:8]}"
        self.orders[oid] = amount_cents
        return Order(oid, f"mock://approve/{oid}")

    def capture_order(self, order_id: str) -> Capture:
        cid = f"MOCK-CAP-{order_id}"
        if self.auto_confirm:
            self.captured[cid] = self.orders[order_id]
        return Capture(cid, self.orders[order_id], self.auto_confirm)

    def refund(self, capture_id: str, amount_cents: int) -> str:
        assert amount_cents <= self.captured[capture_id], "refund exceeds capture"
        self.refunds.append((capture_id, amount_cents))
        return f"MOCK-REFUND-{len(self.refunds)}"

    def verify_webhook(self, headers: dict, body: bytes) -> bool:
        return headers.get("x-mock-signature") == "valid"

    def parse_webhook(self, body: bytes) -> PaymentEvent | None:
        d = json.loads(body)
        return PaymentEvent(event_id=d["id"], kind=d.get("kind", "other"), order_id=d.get("order_id"),
                            capture_id=d.get("capture_id"), amount_cents=d.get("amount_cents"), raw=d)
