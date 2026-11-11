"""Which slices of specs/ml-tasks are built, and which slice each cell of the audit matrix needs.

The audit matrix (tests/e2e/test_ml_task_types_audit.py) has one cell per task type and stage. A cell whose slice is
not in SLICES_BUILT is SKIPPED with the slice id. When a slice lands, its id is added here IN THE SAME COMMIT, which
turns its SKIP cells into real tests. A built cell that fails fails the suite.
"""
import pytest

TASK_TYPES = ("classification", "regression", "forecast", "grouping", "unusual")
STAGES = tuple(f"A{i}" for i in range(1, 15))

STAGE_TITLES = {
    "A1": "task type stored", "A2": "readiness", "A3": "free test", "A4": "pilot and forecast", "A5": "quote",
    "A6": "hold and gate", "A7": "training and check", "A8": "settle", "A9": "predict", "A10": "agent",
    "A11": "blocks and activity", "A12": "UI", "A13": "tenant isolation", "A14": "limits",
}

SLICES_BUILT: set[str] = {"S0", "S1"}

# The slice that makes each stage real for a type (specs/ml-tasks/07-audit-and-test-plan.md section 3). A tuple means
# every slice in it is needed. "S0" means: it exists today (classification). "UI" is not a slice: browser tests are
# run by `npm run test:e2e`, not by pytest, so those cells are always skipped here.
_REGRESSION = {"A1": "S2", "A2": "S2", "A3": "S2", "A4": "S3", "A5": "S3", "A6": "S4", "A7": "S4", "A8": "S4",
               "A9": "S5", "A10": ("S2", "S6"), "A11": "S5", "A12": "UI", "A13": "S5", "A14": "S5"}


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
STAGE_NEEDS.update({("forecast", s): n for s, n in _later("S7", "S7").items()})
STAGE_NEEDS.update({("grouping", s): n for s, n in _later("S8", "S8").items()})
STAGE_NEEDS.update({("unusual", s): n for s, n in _later("S9", "S9").items()})


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
