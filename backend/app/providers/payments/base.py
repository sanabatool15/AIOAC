from dataclasses import dataclass
from typing import Protocol


@dataclass
class Order:
    order_id: str
    approve_url: str | None


@dataclass
class Capture:
    capture_id: str
    amount_cents: int
    confirmed: bool  # True only when the provider reports the money was really captured


@dataclass
class PaymentEvent:
    """Provider-neutral webhook event. Each provider maps its own event names to these."""
    event_id: str
    kind: str  # capture_completed | other
    order_id: str | None = None
    capture_id: str | None = None
    amount_cents: int | None = None
    raw: dict | None = None


class PaymentProvider(Protocol):
    def create_order(self, amount_cents: int, project_id: str) -> Order: ...
    def capture_order(self, order_id: str) -> Capture: ...
    def refund(self, capture_id: str, amount_cents: int) -> str: ...
    def verify_webhook(self, headers: dict, body: bytes) -> bool: ...
    def parse_webhook(self, body: bytes) -> PaymentEvent | None: ...
