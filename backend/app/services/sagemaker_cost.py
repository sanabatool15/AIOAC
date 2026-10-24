"""Cap and cost math for the SageMaker backend (specs/cost.md section 4). Prices come from services/prices.py only.

REVIEW: spend-cap code. Small on purpose.
"""
import math

from .prices import INSTANCES, PLATFORM_FEE_CENTS, STORAGE_CENTS

GRACE_SECONDS = 120          # SageMaker waits up to this long after SIGTERM; it may be billed
SAFETY_SECONDS = 60          # extra margin on top of the grace period
MIN_RUNTIME_SECONDS = 60     # below this a job is not worth starting


class CapTooSmall(ValueError):
    """The cap cannot pay for fixed fees plus a useful minimum of training time."""


def fixed_fees_cents() -> int:
    return STORAGE_CENTS + PLATFORM_FEE_CENTS


def max_runtime_seconds(cap_cents: int, instance_type: str) -> int:
    """MaxRuntimeInSeconds: (cap - fixed fees) / hourly price, minus grace and safety. Raises CapTooSmall."""
    hourly = INSTANCES[instance_type].hourly_cents
    available = cap_cents - fixed_fees_cents()
    if available <= 0:
        raise CapTooSmall(f"cap of {cap_cents} cents does not cover fixed fees of {fixed_fees_cents()} cents")
    seconds = math.floor(available / hourly * 3600) - GRACE_SECONDS - SAFETY_SECONDS
    if seconds < MIN_RUNTIME_SECONDS:
        raise CapTooSmall(f"cap of {cap_cents} cents leaves only {max(seconds, 0)} seconds of training")
    return seconds


def actual_cost_cents(billable_seconds: float, instance_type: str, cap_cents: int) -> int:
    """Billable seconds x hourly price + fixed fees, rounded up, never above the cap."""
    hourly = INSTANCES[instance_type].hourly_cents
    cents = math.ceil(max(billable_seconds, 0) / 3600 * hourly) + fixed_fees_cents()
    return min(cents, cap_cents)
