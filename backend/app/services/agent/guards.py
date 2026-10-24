"""Cheap checks on what the model says and passes in. None of these grant anything; the gate does that.

Money rules live in code (gate.py), not in skills or prompts.
"""
import re

PAID_OR_LATER = {"paid", "training", "done", "refunded", "failed", "stopped"}
TRAINED = {"training", "done"}
SETTLED = {"done", "refunded", "failed", "stopped"}

# (pattern, statuses in which the claim could be true, what actually is the case)
_CLAIMS = [
    (re.compile(r"\b(payment|pay(ing)?)\b[^.!?\n]{0,40}\b(was|has been|is|went)\s+(received|confirmed|complete[d]?|successful|through)\b|"
                r"\byou(?:'ve| have) (been charged|paid)\b|\bi(?:'ve| have) (charged|taken) (your|the) (payment|card)", re.I),
     PAID_OR_LATER, "no payment has been confirmed by the server yet"),
    (re.compile(r"\b(training|the model)\b[^.!?\n]{0,30}\b(has started|is now running|is running|has finished|is finished|is complete|is ready|is trained)\b|"
                r"\bi(?:'ve| have) (started|begun|launched) (the )?training\b|\bi(?:'ve| have) trained\b", re.I),
     TRAINED | SETTLED, "paid training has not started"),
    (re.compile(r"\b(refund(ed)?)\b[^.!?\n]{0,30}\b(sent|issued|processed|on its way|complete[d]?)\b|\bi(?:'ve| have) refunded\b", re.I),
     SETTLED, "no refund has been made"),
]


def false_claims(text: str | None, status: str) -> list[str]:
    """Statements about money or training that the stored project state does not support."""
    if not text:
        return []
    return [reality for rx, ok_in, reality in _CLAIMS if rx.search(text) and status not in ok_in]


def correct_reply(text: str, status: str, problems: list[str]) -> str:
    """Replace a reply that claims something that did not happen with a plain correction."""
    return ("I need to correct myself: " + "; ".join(problems) + f". Nothing was charged or started by me. "
            f"We are at the '{status.replace('_', ' ')}' step.")


def check_args(parameters: dict, args) -> str | None:
    """Return a problem description if the model's arguments do not fit the tool, else None."""
    if not isinstance(args, dict):
        return "the arguments must be an object"
    props = parameters.get("properties", {})
    missing = [k for k in parameters.get("required", []) if k not in args]
    if missing:
        return "missing: " + ", ".join(missing)
    for k, spec in props.items():
        if k in args and spec.get("type") == "string" and (not isinstance(args[k], str) or not args[k].strip()):
            return f"'{k}' must be a non-empty text value"
    return None
