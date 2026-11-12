"""Has the user chosen to let the agent look for data? (plain code, no model call)

At status `described` the screen shows three choices: upload a CSV, paste a link, or "I have no data". The dataset search
tools run only after the user's own words say they have no data or ask for a search. This is checked from stored user
messages, never from what the model says, so a prompt-only rule cannot be argued past. Same style as clarity.py.
"""
import re

# English, Roman Urdu and Urdu. Kept short on purpose: the picker sends the exact sentence in PICKER_MESSAGE.
PICKER_MESSAGE = "I have no data. Please find a dataset."

_NO_DATA = re.compile(
    r"""(?ix)
    \b(?:i\s+)?(?:have|got)\s+no\s+(?:data|dataset|file|csv)\w?\b
  | \b(?:no|without)\s+(?:data|dataset|csv)\w?\b
  | \b(?:don'?t|do\s+not|dont)\s+have\s+(?:any\s+|a\s+|my\s+own\s+)?(?:data|dataset|file|csv)\w?\b
  | \b(?:find|search|look)\s+(?:for\s+)?(?:me\s+)?(?:an?\s+|some\s+|the\s+)?(?:open\s+|free\s+|public\s+)?(?:data|dataset|datasets)\b
  | \b(?:data|dataset|ڈیٹا)\s+(?:nahi|nahin|nhi)\b
  | \b(?:mere|meray|mray)\s+(?:pas|paas)\s+(?:data|dataset)\s+(?:nahi|nahin|nhi)\b
  | ڈیٹا\s+نہیں | ڈیٹا\s+ڈھونڈ | ڈیٹا\s+تلاش
    """
)

WAITING_HINT = (
    "The user has not chosen how to bring data yet, so do not search. In one or two plain sentences tell them to pick one "
    "of the three choices on screen: upload their own CSV file, paste a link to an open dataset, or say they have no data "
    "so you can find one. Do not list the three choices as bullets and do not ask which one: they are already shown as cards on screen. Do not call any dataset tool until they choose."
)


def wants_search(texts: list[str]) -> bool:
    return any(_NO_DATA.search(t or "") for t in texts)
