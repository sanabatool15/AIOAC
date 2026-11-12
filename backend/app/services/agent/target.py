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


ERROR_QUESTION_HINT = ("Do not choose the number yourself. Ask the user ONE short question in plain words: how far off can the prediction be and still be useful "
                       "(an amount, for example $5,000 or 200 units)? Run the free small test only after they answer with an amount.")


def own_texts(texts: list[str]) -> list[str]:
    return [t for t in texts if t and not t.lstrip().startswith(APPROVAL_PREFIX)]


def stated_targets(texts: list[str], task_type: str = "classification") -> list[float]:
    """Every accuracy the user named, as a number between 0 and 1. A number answer has no 'out of 100': see stated_amounts."""
    if task_type not in (None, "classification"):
        return []
    out: list[float] = []
    for t in own_texts(texts):
        out += [float(m.group(1)) / 100 for m in _PERCENT.finditer(t)]
        out += [float(m.group(1)) / float(m.group(2)) for m in _RATIO.finditer(t)]
        out += [float(m.group(0)) for m in _DECIMAL.finditer(t)]
    return [v for v in out if 0 < v < 1]


def user_named(texts: list[str], target: float) -> bool:
    return any(abs(v - target) <= 0.005 for v in stated_targets(texts))


# ---- a number answer (regression): the goal is an amount in the answer's own units, never "out of 100" -------------
# Same principle as above: only the user's OWN words count (own_texts drops the server's approval text). The caller
# must also leave out the goal text for a number answer, because "houses above $500,000" there is a filter, not a goal.
_AMOUNT_NUM = r"(\d[\d,]*(?:\.\d+)?)"
_SCALE = r"(k|thousand|m|million)"
_MONEY_SIGN = re.compile(r"(?<![\w.])[$€£]\s*" + _AMOUNT_NUM + r"\s*" + _SCALE + r"?(?!\w)", re.I)
_MONEY_WORD = re.compile(r"(?<![\w.])" + _AMOUNT_NUM + r"\s*" + _SCALE + r"?\s*(?:dollars|usd|bucks|euros|pounds)\b", re.I)
_MONEY_SCALED = re.compile(r"(?<![\w.$€£,])(\d+(?:\.\d+)?)\s*(k|thousand|million)\b", re.I)   # no bare 'm': "5 m" is not money
_PERCENT_ERROR = re.compile(r"(?:within\s+(\d{1,3}(?:\.\d+)?)\s*(?:%|percent|per\s*cent)|(?<![\w.])(\d{1,3}(?:\.\d+)?)\s*(?:%|percent|per\s*cent)\s+off)", re.I)
_MULTIPLIER = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6}


def stated_amounts(texts: list[str]) -> list[float]:
    """Every amount the user named for a typical miss ($5,000, 5000 dollars, 5k, 2 million). A bare '80%' is not one."""
    out: list[float] = []
    for t in own_texts(texts):
        for rx in (_MONEY_SIGN, _MONEY_WORD, _MONEY_SCALED):
            for m in rx.finditer(t):
                value = float(m.group(1).replace(",", "")) * _MULTIPLIER.get((m.group(2) or "").lower(), 1.0)
                if value > 0 and value not in out:
                    out.append(value)
    return out


def stated_percent_errors(texts: list[str]) -> list[float]:
    """'within 10%' or '10 percent off', as a share between 0 and 1."""
    out: list[float] = []
    for t in own_texts(texts):
        out += [float(m.group(1) or m.group(2)) / 100 for m in _PERCENT_ERROR.finditer(t)]
    return [v for v in out if 0 < v < 1]


def user_named_error(texts: list[str], amount: float) -> bool:
    return any(abs(v - amount) <= max(0.005 * amount, 0.005) for v in stated_amounts(texts))
