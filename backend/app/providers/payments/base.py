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
    confirmed: bool


class PaymentProvider(Protocol):
    def create_order(self, amount_cents: int, job_id: str) -> Order: ...
    def capture_order(self, order_id: str) -> Capture: ...
    def refund(self, capture_id: str, amount_cents: int) -> str: ...
    def verify_webhook(self, headers: dict, body: bytes) -> bool: ...
