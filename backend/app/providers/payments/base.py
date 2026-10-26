from dataclasses import dataclass
from typing import Protocol


class ProviderError(RuntimeError):
    """The payment provider failed or refused. Providers raise subclasses of this."""


@dataclass
class Order:
    order_id: str
    approve_url: str | None


@dataclass
class Authorization:
    """Result of asking the provider to place the hold after the buyer approved."""
    authorization_id: str
    amount_cents: int
    status: str  # held | declined | pending. Only 'held' lets paid work be considered.


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
    """Hold, then capture part of the hold, then void the rest. Every call that moves money takes a
    `request_id`; calling again with the same id must return the first result and never move money twice."""

    def create_hold(self, amount_cents: int, project_id: str) -> Order: ...
    def authorize_order(self, order_id: str) -> Authorization: ...
    def capture(self, authorization_id: str, amount_cents: int, request_id: str) -> Capture: ...
    def void(self, authorization_id: str, request_id: str) -> str: ...
    def verify_webhook(self, headers: dict, body: bytes) -> bool: ...
    def parse_webhook(self, body: bytes) -> PaymentEvent | None: ...
