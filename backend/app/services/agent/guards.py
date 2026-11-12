"""Cheap checks on what the model says and passes in. None of these grant anything; the gate does that.

Money rules live in code (gate.py), not in skills or prompts.
"""
import re

PAID_OR_LATER = {"paid", "training", "done", "voided", "failed", "stopped"}
TRAINED = {"training", "done"}
SETTLED = {"done", "voided", "failed", "stopped"}

# Steps where the agent has tools and may truly run something. Anywhere else a promise to run it is false.
ORDER_WITH_TOOLS = ["described", "data_chosen", "readiness_done", "baseline_done", "quoted", "awaiting_payment", "paid"]

# (pattern, statuses in which the claim could be true, what actually is the case)
_CLAIMS = [
    (re.compile(r"\b(payment|pay(ing)?)\b[^.!?\n]{0,40}\b(was|has been|is|went)\s+(received|confirmed|complete[d]?|successful|through)\b|"
                r"\byou(?:'ve| have) (been charged|paid)\b|\bi(?:'ve| have) (charged|taken) (your|the) (payment|card)", re.I),
     PAID_OR_LATER, "no payment has been confirmed by the server yet"),
    # Paid vocabulary only. "I trained a quick model" / "the model is ready" can be true of the free test, so they are not here.
    (re.compile(r"\b((paid |full )?training|the (paid|full) run)\b[^.!?\n]{0,30}\b(has started|is now running|is running|has finished|is finished|is complete)\b|"
                r"\bi(?:'ve| have) (started|begun|launched) (the )?training\b", re.I),
     TRAINED | SETTLED, "paid training has not started"),
    (re.compile(r"\b(refund(ed)?|released|voided)\b[^.!?\n]{0,30}\b(sent|issued|processed|on its way|complete[d]?)\b|\bi(?:'ve| have) (refunded|released|voided)\b", re.I),
     SETTLED, "nothing has been released yet"),
    # a promise to run something, where this step has no tools (the user must press the button on screen)
    (re.compile(r"\b(i(?:'ll| will| can)|let me|shall i|do you (still )?want (me )?to)\s+(now\s+)?(run|start|launch|test|re-?run|re-?train|train|re-?do|re-?build)\b(?!\s+(with|by|to|off|over)\b)", re.I),
     set(ORDER_WITH_TOOLS), "nothing can be run from this step by chat; the result screen has a 'Try a higher target' button"),
]


# A sentence that sets a condition before the claim ("Once your payment is confirmed, training starts") is a plan, not a claim.
_CONDITION = re.compile(r"\b(once|when|whenever|after|if|until|unless|as soon as)\b", re.I)


def _asserted(rx: re.Pattern, text: str) -> bool:
    """True if the pattern matches somewhere that is not after a condition word in the same sentence."""
    for m in rx.finditer(text):
        start = max(text.rfind(c, 0, m.start()) for c in ".!?\n") + 1
        if not _CONDITION.search(text[start:m.start()]):
            return True
    return False


def false_claims(text: str | None, status: str) -> list[str]:
    """Statements about money or training that the stored project state does not support."""
    if not text:
        return []
    return [reality for rx, ok_in, reality in _CLAIMS if status not in ok_in and _asserted(rx, text)]


def correct_reply(text: str, status: str, problems: list[str]) -> str:
    """Replace a reply that claims something that did not happen with a plain correction."""
    return ("I need to correct myself: " + "; ".join(problems) + f". Nothing was charged or started by me. "
            f"We are at the '{status.replace('_', ' ')}' step.")


_TYPES = {
    "string": (lambda v: isinstance(v, str), "a non-empty text value"),
    "number": (lambda v: isinstance(v, (int, float)) and not isinstance(v, bool), "a number"),
    "integer": (lambda v: isinstance(v, int) and not isinstance(v, bool), "a whole number"),
    "boolean": (lambda v: isinstance(v, bool), "true or false"),
    "array": (lambda v: isinstance(v, list), "a list"),
    "object": (lambda v: isinstance(v, dict), "an object"),
}


def check_args(parameters: dict, args) -> str | None:
    """Return a field-level problem description (sent to the model) if the arguments do not fit the tool's schema, else None."""
    if not isinstance(args, dict):
        return "the arguments must be an object"
    props = parameters.get("properties", {})
    missing = [k for k in parameters.get("required", []) if k not in args]
    if missing:
        return "missing: " + ", ".join(missing)
    for k, spec in props.items():
        if k not in args:
            continue
        v, kind = args[k], spec.get("type")
        if kind in _TYPES and not _TYPES[kind][0](v):
            return f"'{k}' must be {_TYPES[kind][1]}"
        if kind == "string" and not v.strip():
            return f"'{k}' must be a non-empty text value"
        if kind == "array":
            lo, hi = spec.get("minItems"), spec.get("maxItems")
            if (lo is not None and len(v) < lo) or (hi is not None and len(v) > hi):
                return f"'{k}' must have {lo if lo is not None else 0} to {hi if hi is not None else 'any number of'} items"
            item = (spec.get("items") or {}).get("type")
            if item in _TYPES and (bad := next((j for j, x in enumerate(v) if not _TYPES[item][0](x)), None)) is not None:
                return f"'{k}' item {bad + 1} must be {_TYPES[item][1]}"
    return None
