"""Dataset discovery pipeline (specs/agent/11-dataset-discovery.md section 3). Code does the searching and ranking.

The model supplies only a short goal summary and 2 or 3 search phrases. Everything else is deterministic:

  search every source  ->  one record shape  ->  pre-filters  ->  collapse copies  ->  rank  ->  top N with a plain reason

Nothing here talks to the model, and nothing here downloads a dataset.
"""
import logging
import math
import re
import time
from dataclasses import dataclass, field

from ..providers.datasets.base import DatasetHit, SourceError
from ..providers.datasets.curated import CuratedItem, load_curated
from ..providers.datasets.registry import SEARCH_ORDER, SourceRegistry

log = logging.getLogger(__name__)

MIN_ROWS = 300            # below this a dataset is dropped (the dataset-search skill's absolute minimum)
SMALL_ROWS = 1000         # below this it is kept but flagged as small
FIT_THRESHOLD = 0.30      # relevance below this means "nothing fits"
RELATIVE_CUTOFF = 0.6     # and a result must reach 60% of the best result's relevance to be listed
SOURCE_BUDGET_S = 40.0    # total time for all live searches in one call (a free tool is cut off at 60 s)
NOISE = {"raw", "clean", "cleaned", "data", "dataset", "datasets", "csv", "copy", "corrupted", "new", "final", "v", "version",
         "train", "test", "tabular", "kaggle"}
STOP = {"the", "a", "an", "of", "and", "for", "to", "in", "on", "my", "i", "me", "we", "our", "will", "which", "who", "what", "is", "are",
        "be", "can", "that", "this", "with", "from", "by", "or", "do", "does", "predict", "prediction", "predicting", "data", "dataset",
        "model", "want", "know", "whether", "if", "have", "has", "their", "it", "at", "as", "how", "many", "most", "likely", "use"}


# ---------------------------------------------------------------- text helpers

def _stem(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def terms(text: str) -> list[str]:
    """Meaningful lowercase word stems, in order, without repeats."""
    out: list[str] = []
    for w in re.findall(r"[a-z0-9]+", (text or "").lower()):
        s = _stem(w)
        if len(s) >= 3 and s not in STOP and not s.isdigit() and s not in out:
            out.append(s)
    return out


def name_key(name: str) -> frozenset[str]:
    """What a dataset is called, without the owner, version digits or words like 'raw' and 'clean'. Copies share a key."""
    base = (name or "").split("/")[-1].lower()
    return frozenset(_stem(w) for w in re.findall(r"[a-z]+", base) if w not in NOISE and len(w) > 1)


# ---------------------------------------------------------------- one record shape

@dataclass
class Candidate:
    id: str
    name: str
    source: str                       # plain label, e.g. "Hugging Face"
    description: str = ""
    license: str | None = None
    rows: int | None = None
    target: str | None = None
    columns: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    downloads: int = 0
    gated: bool = False
    tabular: bool | None = None
    curated: bool = False
    sample: bool = False
    about: str = ""                   # our own one-sentence description (curated and sample entries)
    keywords: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    domain: str = ""


@dataclass
class Scored:
    cand: Candidate
    relevance: float
    score: float
    reason: str
    matched: list[str]
    notes: list[str]


@dataclass
class Discovery:
    results: list[Scored]
    nothing_fits: bool
    sources: dict[str, str]           # "ok, 4 found" / "unavailable: ..." / "not used"
    collapsed: int                    # near-copies removed
    dropped: dict[str, int]           # reason -> count
    sample_option: Scored | None = None


def from_hit(prefix: str, label: str, hit: DatasetHit) -> Candidate:
    return Candidate(id=f"{prefix}:{hit.id}", name=hit.name or hit.id, source=label, description=hit.description or "", license=hit.license,
                     rows=hit.rows, target=hit.target, columns=list(hit.columns), tasks=list(hit.tasks), downloads=hit.downloads or 0,
                     gated=hit.gated, tabular=hit.tabular)


def from_curated(item: CuratedItem, label: str) -> Candidate:
    return Candidate(id=item.id, name=item.name, source=label, description=item.about, license=item.license, rows=item.rows,
                     target=item.target, tasks=["Classification"], tabular=True, curated=True, about=item.about,
                     keywords=item.keywords, aliases=item.aliases, domain=item.domain)


def from_sample(entry: dict) -> Candidate:
    return Candidate(id=entry["id"], name=entry["name"], source="bundled sample", description=entry["name"], license=entry["license"],
                     rows=entry["rows"], target=entry["target"], tasks=["Classification"], tabular=True, sample=True,
                     about="Synthetic sample data made by us, not real customers.", keywords=tuple(entry["keywords"]))


# ---------------------------------------------------------------- pre-filters and copy collapse

def prefilter(c: Candidate) -> str | None:
    """A reason to drop the candidate, or None to keep it."""
    if c.gated:
        return "needs a login or approval"
    if c.tabular is False:
        return "not a plain table"
    if c.tasks and "Classification" not in c.tasks:
        return "not a prediction of a category"
    if c.rows is not None and c.rows < MIN_ROWS:
        return "too few rows"
    return None


def _quality_key(c: Candidate):
    return (c.curated, c.license is not None, c.rows is not None, c.downloads)


def collapse(cands: list[Candidate], curated: list[CuratedItem]) -> tuple[list[Candidate], int]:
    """Remove near-copies. A copy of a hand-checked dataset is dropped in favour of it; other copies keep the best one."""
    alias_keys = {frozenset(_stem(w) for w in re.findall(r"[a-z]+", a.lower()) if w not in NOISE): item.id for item in curated for a in item.aliases}
    kept: dict[object, Candidate] = {}
    seen_ids: set[str] = set()
    removed = 0
    for c in sorted(cands, key=_quality_key, reverse=True):
        if c.id in seen_ids:  # the same dataset found twice (for example by the list and by a search)
            continue
        seen_ids.add(c.id)
        key = name_key(c.name if c.source != "Hugging Face" else c.id)
        owner = alias_keys.get(key)
        if owner and owner != c.id:  # a copy of a hand-checked dataset
            removed += 1
            continue
        group = ("id", c.id) if c.curated else ("name", key or c.id)
        if group in kept:
            removed += 1
            continue
        kept[group] = c
        if c.curated:  # also stops a same-named non-curated twin from sneaking in
            kept[("name", key)] = c
    unique = list({id(v): v for v in kept.values()}.values())
    return unique, removed


# ---------------------------------------------------------------- ranking

def relevance(c: Candidate, primary: list[str], secondary: list[str]) -> tuple[float, list[str]]:
    """0..1. A search word in the name or domain keywords counts 3, in the description or column names counts 1."""
    own_name = c.name.split("/", 1)[-1] if c.name == c.id.split(":", 1)[-1] else c.name  # Hugging Face names are owner/name
    title = set(terms(own_name.replace("-", " ").replace("_", " "))) | {_stem(k) for k in c.keywords} | set(terms(c.domain))
    body = set(terms(c.description)) | {t for col in c.columns for t in terms(re.sub(r"([a-z])([A-Z])", r"\1 \2", col).replace("_", " "))}

    def weight(t: str) -> int:
        return 3 if t in title else 1 if t in body else 0
    prim = sum(weight(t) for t in primary) / (3 * len(primary)) if primary else 0.0
    sec = sum(weight(t) for t in secondary) / (3 * len(secondary)) if secondary else 0.0
    return min(1.0, prim + 0.25 * sec), [t for t in primary if weight(t)]


def _quality(c: Candidate) -> float:
    q = 0.0
    q += 1.0 if (c.rows or 0) >= SMALL_ROWS else 0.3 if c.rows else 0.3
    q += 1.0 if c.target else 0.0
    q += 0.7 if c.license else 0.0
    q += 0.5 if "Classification" in c.tasks else 0.0
    q += 1.5 if c.curated else 0.0
    q += min(0.3, math.log10(c.downloads + 1) / 20)  # popularity: a small tie-breaker only
    return q


def _fmt(n: int) -> str:
    return f"{n:,}"


def explain(c: Candidate, matched: list[str]) -> tuple[str, list[str]]:
    """One plain sentence for the user, and notes. Built from our own words and numbers, never the dataset's text."""
    notes = []
    if c.rows is not None and c.rows < SMALL_ROWS:
        notes.append(f"small: only {_fmt(c.rows)} rows, so any result will be rough")
    if c.rows and c.rows > 50_000:
        notes.append("large: only the first 50,000 rows would be used")
    if not c.license:
        notes.append("the license is not stated")
    if c.sample:
        return "Synthetic sample data made by us, not real records. Fine for trying the product, not for real decisions.", notes
    parts = []
    if c.about:
        parts.append(c.about.rstrip("."))
    else:
        parts.append(f"Matches your goal on {', '.join(repr(t) for t in matched[:3])}" if matched else "Loosely related to your goal")
        if c.rows:
            parts.append(f"{_fmt(c.rows)} rows")
        parts.append("the answer column is known" if c.target else "the answer column needs checking")
    if c.curated:
        parts.append("we checked this one by hand")
    return ". ".join(p[0].upper() + p[1:] for p in parts if p) + ".", notes


def rank(cands: list[Candidate], goal_summary: str, queries: list[str], curated: list[CuratedItem], top_n: int = 3
         ) -> tuple[list[Scored], int, dict[str, int]]:
    """Pre-filter, collapse copies, score. Returns every fit sorted best first (not cut to top_n), copies removed, drop counts."""
    dropped: dict[str, int] = {}
    kept = []
    for c in cands:
        why = prefilter(c)
        if why:
            dropped[why] = dropped.get(why, 0) + 1
        else:
            kept.append(c)
    unique, removed = collapse(kept, curated)
    primary = list(dict.fromkeys(t for q in queries for t in terms(q)))
    secondary = [t for t in terms(goal_summary) if t not in primary]
    scored = []
    for c in unique:
        rel, matched = relevance(c, primary, secondary)
        reason, notes = explain(c, matched)
        scored.append(Scored(c, rel, 10 * rel + _quality(c), reason, matched, notes))
    scored.sort(key=lambda s: (-s.score, s.cand.id))
    return scored, removed, dropped


# ---------------------------------------------------------------- the whole pipeline

def discover(registry: SourceRegistry, goal_summary: str, queries: list[str], samples: list[dict] = (), top_n: int = 3,
             emit=lambda *a, **k: None, budget_s: float = SOURCE_BUDGET_S) -> Discovery:
    """Search the hand-checked list, UCI, OpenML and Hugging Face (that order). One source failing never fails the call."""
    curated = load_curated()
    cands: list[Candidate] = []
    status: dict[str, str] = {"curated list": f"ok, {len(curated)} checked datasets"}
    for item in curated:
        entry = registry.get(item.id.split(":", 1)[0])
        cands.append(from_curated(item, entry.label if entry else "curated list"))
    deadline = time.monotonic() + budget_s
    for prefix in SEARCH_ORDER:
        entry = registry.get(prefix)
        if entry is None:
            continue
        if time.monotonic() > deadline:
            status[entry.label] = "skipped: ran out of time"
            continue
        found, error, t0 = 0, None, time.monotonic()
        for q in queries:
            try:
                for hit in entry.source.search(q, limit=8):
                    cands.append(from_hit(prefix, entry.label, hit))
                    found += 1
            except SourceError as exc:
                error = str(exc)
            except Exception as exc:  # any other failure of one source must not fail the tool
                log.warning("dataset source %s failed: %s", prefix, type(exc).__name__)
                error = "had a problem"
            if error:
                break
        status[entry.label] = f"unavailable: {error}" if error else f"ok, {found} found"
        emit("discover_source", source=prefix, ok=error is None, found=found, error=error, ms=int((time.monotonic() - t0) * 1000))
    real = [c for c in cands if not c.sample]
    scored, removed, dropped = rank(real, goal_summary, queries, curated, top_n)
    best = max((s.relevance for s in scored), default=0.0)
    cutoff = max(FIT_THRESHOLD, RELATIVE_CUTOFF * best)  # a weak match is not shown next to a strong one
    fits = [s for s in scored if s.relevance >= cutoff]
    primary = list(dict.fromkeys(t for q in queries for t in terms(q)))
    sample_option = None
    sample_scored = []
    for entry in samples:
        c = from_sample(entry)
        rel, matched = relevance(c, primary, [])
        if rel >= FIT_THRESHOLD:
            reason, notes = explain(c, matched)
            sample_scored.append(Scored(c, rel, 0.0, reason, matched, notes + ["sample data, not real records"]))
    nothing = not fits
    top = fits[:top_n]
    if sample_scored:
        if nothing or len(top) >= top_n:
            sample_option = sample_scored[0]      # offered separately, never in place of a real fit
        else:
            top = top + sample_scored[: top_n - len(top)]
    emit("discover_ranked", considered=len(real), fits=len(fits), collapsed=removed, dropped=dropped, nothing_fits=nothing,
         top=[s.cand.id for s in top])
    return Discovery(top, nothing, status, removed, dropped, sample_option)
