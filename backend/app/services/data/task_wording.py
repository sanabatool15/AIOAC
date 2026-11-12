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


_REPEAT = {"last": "repeating last {period}", "average": "always the average"}


def _repeat_phrase(extras: dict) -> str:
    kind, period = extras.get("best_simple_repeat", "last"), extras.get("period", "period")
    if kind == "seasonal":
        return "repeating the same time last year" if extras.get("season") == 12 and period == "month" else "repeating the same time last cycle"
    return _REPEAT.get(kind, _REPEAT["last"]).format(period=period)


def plain_forecast_note(extras: dict | None) -> str:
    """A sentence for when no model did clearly better than a simple repeat; empty when one did."""
    extras = extras or {}
    if extras.get("beats_simple_repeat"):
        return ""
    return f"Our models were no better than a simple repeat ({_repeat_phrase(extras)}), so a trained model is not worth paying for here."


def plain_score(task: str, value: float, extras: dict | None = None) -> str:
    extras = extras or {}
    if task == "regression":
        return f"on average off by about {extras.get('unit', '')}{_num(extras.get('error', 0))} (an estimate)"
    if task == "forecast":
        p = extras.get("period", "period")
        return f"typically off by about {extras.get('unit', '')}{_num(extras.get('error', 0))} a {p} over the next {extras.get('horizon', 12)} {p}s (an estimate)"
    return f"about {round(value * 100)} out of 100 predictions were right (an estimate)"


def plain_guess(task: str, extras: dict | None = None) -> str:
    extras = extras or {}
    if task == "regression":
        return f"a simple guess, always the average, is off by about {extras.get('unit', '')}{_num(extras.get('guess_error', 0))}"
    if task == "forecast":
        return f"a simple repeat ({_repeat_phrase(extras)}) is off by about {extras.get('unit', '')}{_num(extras.get('guess_error', 0))}"
    return f"a simple guess would get about {round(extras.get('simple_guess', 0) * 100)} out of 100 right"


def plain_amount(x: float, unit: str = "") -> str:
    return f"{unit}{_num(x)}"


def plain_forecast(predicted: float, band_low: float, band_high: float, target: float, confidence: float,
                   scale: dict, unit: str = "") -> dict:
    """The forecast of a number answer in the answer's own units. `scale["guess_error"]` is the frozen error of always
    guessing the average; a score s means a typical miss of (1 - s) * that. A better score is a smaller miss, so the band
    runs from the best case (band_high) to the worst (band_low). Everything is an estimate."""
    ref = float(scale.get("guess_error") or 0)
    miss = lambda score: plain_amount((1 - score) * ref, unit)
    return {"typical_error_text": f"typically off by about {miss(predicted)} on average (an estimate)",
            "band_text": f"between about {miss(band_high)} and {miss(band_low)} (an estimate)",
            "target_text": f"typically off by no more than {miss(target)}",
            "simple_guess_error_text": f"a simple guess, always the average, is off by about {plain_amount(ref, unit)}",
            "confidence_text": f"about {round(confidence * 100)}% chance (an estimate)"}
