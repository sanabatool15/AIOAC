"""All interfaces (Protocols) and the plain data types that cross them, in one place.

Integrations (app/integrations/*) implement these. Services and routes depend on these, not on a vendor.
Test and eval stand-ins live in backend/doubles/ and implement the same interfaces.
"""
from dataclasses import dataclass, field
from typing import Callable, Protocol


# ---- payments ----

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


# ---- training ----

@dataclass
class TrainingResult:
    accuracy: float
    simple_guess_accuracy: float
    runtime_seconds: float
    cost_cents: int            # actual compute cost of the run, never above the compute cap
    stopped_at_cap: bool = False
    model_bytes: bytes | None = None
    stopped: bool = False      # True when the run ended because should_stop() returned True


class TrainingBackend(Protocol):
    name: str
    instance_type: str | None

    def run(self, dataset_path: str, target: str, cap_cents: int,
            on_progress: Callable[[str, float], None] | None = None,
            should_stop: Callable[[], bool] | None = None, job_key: str | None = None) -> TrainingResult:
        """on_progress(stage, fraction) reports plain-language progress (fraction 0..1).
        should_stop() is polled between stages; when it returns True the backend ends early and returns
        TrainingResult(stopped=True, cost_cents=<used so far>).
        job_key is the training run id. A backend that creates remote jobs must derive the remote job's name from it,
        so that a repeated call for the same run finds the same job instead of starting (and billing) a second one."""
        ...


# ---- datasets ----

class SourceError(Exception):
    """A dataset source problem, phrased so the agent can explain it to the user in plain words."""


@dataclass
class DatasetHit:
    id: str
    description: str
    license: str | None
    downloads: int
    likes: int
    gated: bool
    # optional richer fields; sources fill what they know (None/empty means unknown)
    name: str | None = None
    rows: int | None = None
    target: str | None = None
    columns: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)   # e.g. ["Classification"]
    tabular: bool | None = None


@dataclass
class DatasetInfo:
    id: str
    rows: int | None
    bytes: int | None
    columns: list[dict]            # [{"name":..., "dtype":...}]
    tabular: bool
    gated: bool
    license: str | None
    config: str
    split: str
    notes: list[str] = field(default_factory=list)
    target: str | None = None      # the source's own idea of the answer column, if it states one


@dataclass
class FetchedCsv:
    csv_bytes: bytes
    rows: int
    license: str | None
    truncated: bool
    suggested_target: str | None = None


class DatasetSource(Protocol):
    def search(self, query: str, limit: int = 6) -> list[DatasetHit]: ...
    def info(self, dataset_id: str) -> DatasetInfo: ...
    def fetch_csv(self, dataset_id: str, max_rows: int, max_bytes: int) -> FetchedCsv: ...


# ---- language model ----

class LLMError(Exception):
    """The model service failed. The message is plain language and safe to show the user."""

    def __init__(self, message: str, retryable: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict
    error: str | None = None  # set when the model's arguments could not be read; the loop tells the model


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None  # OpenRouter reports this in usage.cost; None when unknown

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResponse:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage | None = None
    finish_reason: str | None = None


class LLMClient(Protocol):
    def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse: ...


# ---- storage ----

class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def list(self, prefix: str) -> list[str]: ...
    def path(self, key: str) -> str: ...  # local path for tools that need a file


# ---- background jobs ----

class JobRunner(Protocol):
    """Runs a training job (by run id) outside the HTTP request."""

    stale_after_seconds: int  # how long a silent `running` run waits before crash recovery may fail it

    def enqueue(self, run_id: str) -> None:
        """Hand the run to a worker and return at once. Raises if the job could not be queued."""
        ...

    def is_active(self, run_id: str) -> bool:
        """True if this process knows a live worker for the run. Runners that cannot know return False
        and rely on the heartbeat (stale_after_seconds) instead."""
        ...
