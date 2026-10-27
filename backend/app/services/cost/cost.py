"""Cost estimate (specs/cost.md). Always an ESTIMATE.

hours = (projected_time * speed_factor + startup) / 3600
compute = hours * hourly price;  total = compute + storage + platform fee
"""
import math
from dataclasses import dataclass

import numpy as np

from .prices import DEFAULT_INSTANCE, INSTANCES, PLATFORM_FEE_CENTS, PRICES_VERSION, STORAGE_CENTS

MIN_MARGIN = 0.30   # the range is never tighter than this
SLOPE_RANGE = (1.0, 2.0)  # training time grows at least linearly; cap wild fits


class QuoteTooExpensive(Exception):
    pass


@dataclass
class CostEstimate:
    estimate_cents: int
    low_cents: int
    high_cents: int
    cap_cents: int
    breakdown: dict
    instance_type: str
    prices_version: str
    projected_seconds: float


def project_seconds(samples: list[tuple[int, float]], full_rows: int) -> tuple[float, float]:
    """Fit time vs rows on a log-log scale and project to full_rows. Returns (seconds, relative_error)."""
    pts = [(n, max(t, 1e-3)) for n, t in samples if n > 0]
    if not pts:
        raise ValueError("no timing samples")
    ns = np.log([n for n, _ in pts])
    ts = np.log([t for _, t in pts])
    if len(set(ns)) < 2:
        slope, resid = 1.0, 0.0
        intercept = float(ts.mean() - slope * ns.mean())
    else:
        slope = float(np.clip(np.polyfit(ns, ts, 1)[0], *SLOPE_RANGE))
        intercept = float(ts.mean() - slope * ns.mean())
        resid = float(np.std(ts - (intercept + slope * ns)))
    secs = math.exp(intercept + slope * math.log(max(full_rows, 1)))
    return secs, 2 * resid


def estimate_quote(samples: list[tuple[int, float]], full_rows: int, max_cap_cents: int,
                   instance: str = DEFAULT_INSTANCE) -> CostEstimate:
    spec = INSTANCES[instance]
    secs, err = project_seconds(samples, full_rows)
    margin = max(MIN_MARGIN, err)

    def total(sec: float) -> float:
        hours = (sec * spec.speed_factor + spec.startup_seconds) / 3600
        return hours * spec.hourly_cents + STORAGE_CENTS + PLATFORM_FEE_CENTS

    est, low, high = total(secs), total(secs * (1 - margin / 2)), total(secs * (1 + margin))
    high_c = math.ceil(high)
    if high_c > max_cap_cents:
        raise QuoteTooExpensive(f"worst case {high_c} cents is above the per-job maximum of {max_cap_cents}")
    compute = (est - STORAGE_CENTS - PLATFORM_FEE_CENTS)
    return CostEstimate(
        estimate_cents=round(est), low_cents=math.floor(low), high_cents=high_c, cap_cents=high_c,
        breakdown={"compute_cents": round(compute, 2), "storage_cents": STORAGE_CENTS, "platform_fee_cents": PLATFORM_FEE_CENTS},
        instance_type=instance, prices_version=PRICES_VERSION, projected_seconds=secs,
    )
