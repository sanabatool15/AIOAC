import json
import uuid

from app.ports import Authorization, Capture, Order, PaymentEvent, ProviderError


class MockPaymentProvider:
    """In-memory provider for tests and evals. Never talks to PayPal.

    Mirrors the rules that matter: captures from one hold can never add up to more than the hold, a voided or
    fully captured hold takes no more captures, and repeating a request_id returns the first result."""

    def __init__(self, auto_confirm: bool = True, decline: bool = False):
        self.orders: dict[str, int] = {}
        self.holds: dict[str, int] = {}                 # authorization id -> amount held
        self.captured: dict[str, list[int]] = {}        # authorization id -> capture amounts
        self.voided: set[str] = set()
        self.calls: dict[str, object] = {}              # request_id -> first result (idempotency)
        self.capture_calls: list[tuple[str, int]] = []  # (authorization id, cents) for each NEW capture
        self.void_calls: list[str] = []                 # authorization ids voided (new calls only)
        self.auto_confirm = auto_confirm
        self.decline = decline

    def captured_total(self, authorization_id: str) -> int:
        return sum(self.captured.get(authorization_id, []))

    def create_hold(self, amount_cents: int, project_id: str) -> Order:
        oid = f"MOCK-ORDER-{uuid.uuid4().hex[:8]}"
        self.orders[oid] = amount_cents
        return Order(oid, f"mock://approve/{oid}")

    def authorize_order(self, order_id: str) -> Authorization:
        aid = f"MOCK-AUTH-{order_id}"
        if self.decline:
            return Authorization(aid, self.orders[order_id], "declined")
        if not self.auto_confirm:
            return Authorization(aid, self.orders[order_id], "pending")  # buyer has not approved yet
        self.holds[aid] = self.orders[order_id]
        return Authorization(aid, self.orders[order_id], "held")

    def capture(self, authorization_id: str, amount_cents: int, request_id: str) -> Capture:
        if request_id in self.calls:
            return self.calls[request_id]
        if authorization_id not in self.holds or authorization_id in self.voided:
            raise ProviderError("no active hold")
        if amount_cents <= 0:
            raise ProviderError("capture must be positive")
        if self.captured_total(authorization_id) + amount_cents > self.holds[authorization_id]:
            raise ProviderError("capture exceeds the hold")
        self.captured.setdefault(authorization_id, []).append(amount_cents)
        self.capture_calls.append((authorization_id, amount_cents))
        cap = Capture(f"MOCK-CAP-{request_id}", amount_cents, True)
        self.calls[request_id] = cap
        return cap

    def void(self, authorization_id: str, request_id: str) -> str:
        if request_id in self.calls:
            return self.calls[request_id]
        if authorization_id not in self.holds:
            raise ProviderError("no active hold")
        if self.captured_total(authorization_id) >= self.holds[authorization_id]:
            raise ProviderError("a fully captured hold cannot be voided")
        self.voided.add(authorization_id)
        self.void_calls.append(authorization_id)
        vid = f"MOCK-VOID-{request_id}"
        self.calls[request_id] = vid
        return vid

    def verify_webhook(self, headers: dict, body: bytes) -> bool:
        return headers.get("x-mock-signature") == "valid"

    def parse_webhook(self, body: bytes) -> PaymentEvent | None:
        d = json.loads(body)
        return PaymentEvent(event_id=d["id"], kind=d.get("kind", "other"), order_id=d.get("order_id"),
                            capture_id=d.get("capture_id"), amount_cents=d.get("amount_cents"), raw=d)
