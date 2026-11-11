"""Plain words for scores, per task type. Lives in the app, never shipped to SageMaker. No jargon: no F1, R2, MAE, "split".
Every number is an estimate and says so."""
import re

_MONEY = re.compile(r"(price|cost|amount|revenue|salary|income|sales|fee|rent|wage|spend|charge|payment)", re.I)


def unit_for(column: str) -> str:
    """A currency sign inferred from the answer column's name; empty when there is no sign to guess."""
    return "$" if _MONEY.search(column or "") else ""


def _num(x: float) -> str:
    """Round to about three significant figures so a typical error is not shown with false precision."""
    x = abs(float(x))
    if x >= 100:
        digits = len(str(int(x))) - 3
        x = round(x, -digits) if digits > 0 else round(x)
        return f"{int(x):,}"
    if x >= 10:
        return f"{x:.1f}".rstrip("0").rstrip(".")
    if x >= 1:
        return f"{x:.2f}".rstrip("0").rstrip(".")
    return f"{x:.3f}".rstrip("0").rstrip(".") or "0"


def plain_score(task: str, value: float, extras: dict | None = None) -> str:
    extras = extras or {}
    if task == "regression":
        return f"on average off by about {extras.get('unit', '')}{_num(extras.get('error', 0))} (an estimate)"
    return f"about {round(value * 100)} out of 100 predictions were right (an estimate)"


def plain_guess(task: str, extras: dict | None = None) -> str:
    extras = extras or {}
    if task == "regression":
        return f"a simple guess, always the average, is off by about {extras.get('unit', '')}{_num(extras.get('guess_error', 0))}"
    return f"a simple guess would get about {round(extras.get('simple_guess', 0) * 100)} out of 100 right"
