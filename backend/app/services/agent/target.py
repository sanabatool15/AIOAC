"""The target accuracy belongs to the user, never to the model (plain code, no model call).

`run_pilot` only runs when a number in the user's OWN words matches the target the model passes: '80 out of 100',
'80%', '8 out of 10', '0.8'. The synthetic text the server adds when a card is approved ('Yes, I approve: ...') and
the model's own words never count. Without a match the tool answers `need_target` and the model asks the user.
"""
import re

APPROVAL_PREFIX = "Yes, I approve:"  # written by the agent loop when the user pressed Approve and typed nothing

_PERCENT = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d+)?)\s*(?:%|percent|per\s*cent)", re.I)
_RATIO = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d+)?)\s*(?:out\s+of|/)\s*(10|100)(?!\d)", re.I)
_DECIMAL = re.compile(r"(?<![\w.])0?\.\d{1,3}(?!\d)")

QUESTION_HINT = ("Do not choose the target yourself. Ask the user ONE short question in plain words: how many out of 100 predictions "
                 "do they need to be right? Mention what the free test got (baseline_percent). Run the free small test only after they answer.")


def own_texts(texts: list[str]) -> list[str]:
    return [t for t in texts if t and not t.lstrip().startswith(APPROVAL_PREFIX)]


def stated_targets(texts: list[str]) -> list[float]:
    """Every accuracy the user named, as a number between 0 and 1."""
    out: list[float] = []
    for t in own_texts(texts):
        out += [float(m.group(1)) / 100 for m in _PERCENT.finditer(t)]
        out += [float(m.group(1)) / float(m.group(2)) for m in _RATIO.finditer(t)]
        out += [float(m.group(0)) for m in _DECIMAL.finditer(t)]
    return [v for v in out if 0 < v < 1]


def user_named(texts: list[str], target: float) -> bool:
    return any(abs(v - target) <= 0.005 for v in stated_targets(texts))
