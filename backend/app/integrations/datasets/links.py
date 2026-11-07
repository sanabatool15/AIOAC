"""Turn a pasted web address into a dataset id we already know how to fetch. Pure code: no network, no model.

Only three places are accepted, and only as `https://<exact host>/<known path>`:

  huggingface.co/datasets/<owner>/<name>   ->  hf:<owner>/<name>
  archive.ics.uci.edu/dataset/<number>     ->  uci:<number>   (an optional readable name after the number is ignored)
  openml.org/d/<number>                    ->  oml:<number>   (www.openml.org is the same site)

The address is never fetched. The id goes through the same source classes (fixed hosts, size and row limits) as a dataset
the agent found. A link to any other host, or to a plain CSV file, is refused on purpose: fetching an address chosen by a
user is how a server gets pointed at its own network (SSRF).
"""
import re
from dataclasses import dataclass
from urllib.parse import urlsplit


class LinkError(ValueError):
    """The pasted address is not one we accept. The message is plain words for the user."""


@dataclass(frozen=True)
class DatasetLink:
    dataset_id: str   # hf:owner/name, uci:144 or oml:40945
    prefix: str


MAX_LENGTH = 300
_PART = r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}"
_HF = re.compile(rf"^/datasets/({_PART})/({_PART})/?$")
_UCI = re.compile(r"^/dataset/(\d{1,7})(?:/[A-Za-z0-9._-]{1,120})?/?$")
_OML = re.compile(r"^/d/(\d{1,9})/?$")

REFUSED = ("That link is not one we can use. Paste the page address of a dataset on Hugging Face "
           "(huggingface.co/datasets/owner/name), UCI (archive.ics.uci.edu/dataset/number) or OpenML (openml.org/d/number).")


def parse_dataset_link(text: str) -> DatasetLink:
    raw = (text or "").strip()
    if not raw or len(raw) > MAX_LENGTH or any(ch.isspace() or ord(ch) < 32 or ord(ch) > 126 for ch in raw) or "\\" in raw:
        raise LinkError(REFUSED)
    try:
        u = urlsplit(raw)
        port = u.port
    except ValueError:
        raise LinkError(REFUSED)
    # https only; no user:pass@; the default port only; the host must match exactly (so look-alikes such as
    # huggingface.co.evil.test, evil-huggingface.co, xn-- names, IP addresses and localhost all fail).
    if u.scheme != "https" or u.username is not None or u.password is not None or port not in (None, 443):
        raise LinkError(REFUSED)
    host, path = (u.hostname or "").lower(), u.path
    if "%" in path or ".." in path or "//" in path:
        raise LinkError(REFUSED)
    if host == "huggingface.co" and (m := _HF.match(path)):
        return DatasetLink(f"hf:{m.group(1)}/{m.group(2)}", "hf")
    if host == "archive.ics.uci.edu" and (m := _UCI.match(path)):
        return DatasetLink(f"uci:{int(m.group(1))}", "uci")
    if host in ("openml.org", "www.openml.org") and (m := _OML.match(path)):
        return DatasetLink(f"oml:{int(m.group(1))}", "oml")
    raise LinkError(REFUSED)
