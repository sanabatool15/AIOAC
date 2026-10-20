import uuid

from .base import Capture, Order


class MockPaymentProvider:
    """In-memory provider for tests and local demos. Never talks to PayPal."""

    def __init__(self):
        self.orders: dict[str, int] = {}
        self.refunds: list[tuple[str, int]] = []

    def create_order(self, amount_cents: int, job_id: str) -> Order:
        oid = f"MOCK-ORDER-{uuid.uuid4().hex[:8]}"
        self.orders[oid] = amount_cents
        return Order(oid, None)

    def capture_order(self, order_id: str) -> Capture:
        return Capture(f"MOCK-CAP-{order_id}", self.orders[order_id], True)

    def refund(self, capture_id: str, amount_cents: int) -> str:
        self.refunds.append((capture_id, amount_cents))
        return f"MOCK-REFUND-{len(self.refunds)}"

    def verify_webhook(self, headers: dict, body: bytes) -> bool:
        return True
