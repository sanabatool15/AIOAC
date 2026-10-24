"""Cost accuracy report (specs/testing.md section 2): how often the actual cost lands inside the quoted range."""
from dataclasses import dataclass


@dataclass
class CostRecord:
    estimate_cents: int
    low_cents: int
    high_cents: int
    actual_cents: int


def cost_accuracy_report(records: list[CostRecord]) -> dict:
    n = len(records)
    if n == 0:
        return {"jobs": 0, "inside_range": 0, "inside_share": None, "mean_abs_error_cents": None,
                "mean_signed_error_cents": None, "over_high": 0, "under_low": 0}
    inside = sum(r.low_cents <= r.actual_cents <= r.high_cents for r in records)
    errs = [r.actual_cents - r.estimate_cents for r in records]
    return {
        "jobs": n, "inside_range": inside, "inside_share": inside / n,
        "mean_abs_error_cents": sum(abs(e) for e in errs) / n,
        "mean_signed_error_cents": sum(errs) / n,   # positive = we under-estimated
        "over_high": sum(r.actual_cents > r.high_cents for r in records),
        "under_low": sum(r.actual_cents < r.low_cents for r in records),
    }
