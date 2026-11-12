"""Which slices of specs/ml-tasks are built, and which slice each cell of the audit matrix needs.

The audit matrix (tests/e2e/test_ml_task_types_audit.py) has one cell per task type and stage. A cell whose slice is
not in SLICES_BUILT is SKIPPED with the slice id. When a slice lands, its id is added here IN THE SAME COMMIT, which
turns its SKIP cells into real tests. A built cell that fails fails the suite.
"""
import io

import numpy as np
import pandas as pd
import pytest

TASK_TYPES = ("classification", "regression", "forecast", "grouping", "unusual")
STAGES = tuple(f"A{i}" for i in range(1, 15))

STAGE_TITLES = {
    "A1": "task type stored", "A2": "readiness", "A3": "free test", "A4": "pilot and forecast", "A5": "quote",
    "A6": "hold and gate", "A7": "training and check", "A8": "settle", "A9": "predict", "A10": "agent",
    "A11": "blocks and activity", "A12": "UI", "A13": "tenant isolation", "A14": "limits",
}

SLICES_BUILT: set[str] = {"S0", "S1", "S2", "S8"}

# The slice that makes each stage real for a type (specs/ml-tasks/07-audit-and-test-plan.md section 3). A tuple means
# every slice in it is needed. "S0" means: it exists today (classification). "UI" is not a slice: browser tests are
# run by `npm run test:e2e`, not by pytest, so those cells are always skipped here.
_REGRESSION = {"A1": "S2", "A2": "S2", "A3": "S2", "A4": "S3", "A5": "S3", "A6": "S4", "A7": "S4", "A8": "S4",
               "A9": "S5", "A10": ("S2", "S6"), "A11": "S5", "A12": "UI", "A13": "S5", "A14": "S5"}


# Forecast numbering follows 01-backend-ml-core.md section 6: S8 features, naive baselines and free test (A1 to A3);
# S9 pilot, forecast, verification, training; S10 predict.
_FORECAST = {"A1": "S8", "A2": "S8", "A3": "S8", "A4": "S9", "A5": "S9", "A6": "S9", "A7": "S9", "A8": "S9", "A9": "S10",
             "A10": ("S8", "S6"), "A11": "S10", "A12": "UI", "A13": "S10", "A14": "S10"}


def _later(first: str, last: str) -> dict:
    """forecast, grouping, unusual: stages A2 to A9, A11, A13, A14 arrive with the type's own slice."""
    needs = {s: first for s in STAGES}
    needs["A9"] = last
    needs["A10"] = (first, "S6")
    needs["A12"] = "UI"
    return needs


STAGE_NEEDS: dict[tuple[str, str], str | tuple[str, ...]] = {}
STAGE_NEEDS.update({("classification", s): "S0" for s in STAGES})
STAGE_NEEDS[("classification", "A1")] = "S1"
STAGE_NEEDS[("classification", "A12")] = "UI"
STAGE_NEEDS.update({("regression", s): n for s, n in _REGRESSION.items()})
STAGE_NEEDS.update({("forecast", s): n for s, n in _FORECAST.items()})
STAGE_NEEDS.update({("grouping", s): n for s, n in _later("S11", "S11").items()})
STAGE_NEEDS.update({("unusual", s): n for s, n in _later("S12", "S12").items()})


def missing_slice(task: str, stage: str) -> str | None:
    """The first needed slice that is not built, or None when the cell can run."""
    needs = STAGE_NEEDS[(task, stage)]
    for n in ((needs,) if isinstance(needs, str) else needs):
        if n not in SLICES_BUILT:
            return n
    return None


def skip_unless_built(task: str, stage: str) -> None:
    n = missing_slice(task, stage)
    if n == "UI":
        pytest.skip("slice UI: browser tests run with `npm run test:e2e`, not in this offline matrix")
    if n:
        pytest.skip(f"slice {n} not built")


def house_csv(n: int = 1500, seed: int = 0) -> bytes:
    """Synthetic house prices: a strong-signal regression dataset (linear terms, one interaction, noise). Seeded."""
    rng = np.random.default_rng(seed)
    sqft = rng.integers(500, 4000, n)
    beds = rng.integers(1, 6, n)
    age = rng.integers(0, 80, n)
    hood = rng.choice(["north", "south", "east", "west"], n)
    garage = rng.integers(0, 2, n)
    bump = pd.Series(hood).map({"north": 40000, "south": 0, "east": 20000, "west": -20000}).to_numpy()
    price = 50000 + 120 * sqft + 8000 * beds - 600 * age + bump + 15000 * garage + 0.02 * sqft * garage * 100 + rng.normal(0, 25000, n)
    df = pd.DataFrame({"sqft": sqft, "bedrooms": beds, "age_years": age, "neighborhood": hood, "has_garage": garage,
                       "price": price.round(0)})
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()


def sales_frame(kind: str = "seasonal", n: int = 96, seed: int = 0) -> pd.DataFrame:
    """A synthetic monthly series: columns `month` (first of each month, as text) and `units`. kind: "seasonal" (a yearly
    pattern plus a slow rise), "trend" (a straight rise plus noise) or "walk" (a random walk: nothing beats a repeat of last month)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    if kind == "seasonal":
        y = 200 + 0.5 * t + 50 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 4, n)
    elif kind == "trend":
        y = 100 + 3.0 * t + rng.normal(0, 5, n)
    elif kind == "walk":
        y = 500 + np.cumsum(rng.normal(0, 10, n))
    else:
        raise ValueError(kind)
    months = pd.date_range("2016-01-01", periods=n, freq="MS")
    return pd.DataFrame({"month": months.strftime("%Y-%m-%d"), "units": y.round(2)})


def sales_csv(kind: str = "seasonal", n: int = 96, seed: int = 0) -> bytes:
    buf = io.StringIO()
    sales_frame(kind, n, seed).to_csv(buf, index=False)
    return buf.getvalue().encode()
