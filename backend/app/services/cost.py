"""Cost estimate = measured baseline time scaled to full data x hourly price
+ storage + platform fee. Always an ESTIMATE. Prices live in prices.py."""
from .prices import INSTANCE_HOURLY_CENTS, PLATFORM_FEE_CENTS, STORAGE_CENTS


def estimate_cost_cents(baseline_seconds: float, baseline_rows: int, full_rows: int,
                        instance_type: str) -> int:
    scaled_seconds = baseline_seconds * (full_rows / max(baseline_rows, 1))
    compute = scaled_seconds / 3600 * INSTANCE_HOURLY_CENTS[instance_type]
    return round(compute + STORAGE_CENTS + PLATFORM_FEE_CENTS)
