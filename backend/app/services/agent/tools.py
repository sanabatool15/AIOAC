"""Agent tools (specs/agent.md section 3). Each tool declares the gate action it needs."""
import io
import re
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd
from ...db import Session
from ...repositories import datasets as datasets_repo

from ...db.tables import Project
from ...config import settings
from ...ports import DatasetSource, SourceError
from ...integrations.datasets.registry import SourceRegistry, as_registry
from ...ports import PaymentProvider, Storage, TrainingBackend
from ..data.samples import CATALOG
from ..data import analysis, datasets, discovery, pilot
from ..cost import cost, quotes
from .. import gate, payments, training
from . import clarity, memory, skills
from ..data.insights import analyze
from .context import mark, sanitise_license


@dataclass
class ToolContext:
    session: Session
    project: Project
    storage: Storage
    provider: PaymentProvider
    provider_name: str
    backend: TrainingBackend
    source: DatasetSource | SourceRegistry   # a registry of sources, or a bare Hugging Face-style source (tests)
    approved: set[str] = field(default_factory=set)  # L1 actions the user approved this turn
    log: object | None = None                        # the run log, set by the agent loop; tools may emit events to it

    def emit(self, type: str, level: str = "INFO", **fields) -> None:
        if self.log is not None:
            self.log.emit(type, level, **fields)

    @property
    def registry(self) -> SourceRegistry:
        return as_registry(self.source)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    action: gate.Action
    fn: Callable[[ToolContext, dict], dict]

    def spec(self) -> dict:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


def _obj(**props):
    return {"type": "object", "properties": props, "required": list(props)}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _sample_matches(entry: dict, query: str) -> bool:
    """Whole-word match: 'cat' must not match 'category'. A keyword may be a phrase ('stop buying')."""
    q = _words(query)
    if not q:
        return False
    padded = " " + " ".join(re.findall(r"[a-z0-9]+", query.lower())) + " "
    if any(" " + " ".join(re.findall(r"[a-z0-9]+", k.lower())) + " " in padded for k in entry["keywords"]):
        return True
    return bool(q & (_words(entry["name"]) - {"the", "a", "of", "and", "for", "sample", "synthetic"}))


SAMPLE_IDS = {c["id"] for c in CATALOG}
ID_HINT = "Dataset ids start with their source, for example hf:owner/name, uci:144 or oml:40945. Use an id exactly as search_datasets or discover_datasets returned it."


def _bad_id(did: str) -> dict:
    return {"error": f"unknown dataset id '{did[:80]}'. {ID_HINT}"}


def _needs_clarity(ctx) -> dict | None:
    """Vague goal: ask before searching (see clarity.py)."""
    if clarity.is_clear(memory.user_texts(ctx.session, ctx.project)):
        return None
    ctx.emit("need_clarity", "INFO")
    return {"need_clarity": True, "advice": clarity.QUESTION_HINT}


def search_datasets(ctx, a):
    if (vague := _needs_clarity(ctx)):
        return vague
    out = [{"id": c["id"], "name": c["name"], "source": "bundled sample", "sample_data": True,
            "note": "synthetic sample data made by us, not real customers", "license": sanitise_license(c["license"], trusted=True)}
           for c in CATALOG if _sample_matches(c, a["query"])]
    hf = ctx.registry.get("hf")
    if hf is None:
        return {"results": out}
    try:
        for h in hf.source.search(a["query"], limit=6):
            out.append({"id": f"hf:{h.id}", "name": h.id, "source": hf.label, "about": mark(h.description or ""),
                        "license": sanitise_license(h.license), "downloads": h.downloads, "gated": h.gated})
    except SourceError as exc:
        return {"results": out, "warning": str(exc)}
    return {"results": out[:8]}


def discover_datasets(ctx, a):
    """Find datasets for the goal. The model gives only a short summary and 2 or 3 search phrases; code does the rest."""
    if (vague := _needs_clarity(ctx)):
        return vague
    queries = a.get("queries")
    if not isinstance(queries, list):
        return {"error": "queries must be a list of 2 or 3 short English search phrases"}
    queries = [" ".join(q.split())[:80] for q in queries if isinstance(q, str) and q.strip()][:3]
    if not queries:
        return {"error": "give 2 or 3 short English search phrases in queries"}
    goal = " ".join(str(a.get("goal_summary", "")).split())[:300]
    d = discovery.discover(ctx.registry, goal, queries, CATALOG, emit=ctx.emit)

    def card(s):
        c = s.cand
        trusted = c.curated or c.sample
        out = {"id": c.id, "name": c.name if trusted else mark(c.name, 120), "source": c.source, "reason": s.reason,
               "rows": c.rows, "license": sanitise_license(c.license, trusted=trusted), "notes": s.notes}
        if c.target:
            out["answer_column_hint"] = c.target if trusted else mark(c.target, 60)
        if c.description and not trusted:
            out["about"] = mark(c.description, 200)
        if c.curated:
            out["hand_checked"] = True
        if c.sample:
            out["sample_data"] = True
        return out
    res = {"candidates": [card(s) for s in d.results], "sources": d.sources, "near_copies_removed": d.collapsed}
    if d.nothing_fits:
        res["nothing_fits"] = True
        res["advice"] = ("Nothing found is a good fit for this goal. Say so honestly in one or two sentences. Do not pick a loose match. "
                         "Offer: the user uploads their own file or pastes a link, or (if sample_option is present) the sample data to try the product. "
                         "You may try one more search with different words.")
        if d.sample_option:
            res["sample_option"] = card(d.sample_option)
    else:
        res["next"] = "Check the top 2 or 3 with look_at_dataset, then fetch_dataset. Describe each in one plain sentence and let the user choose."
        if d.sample_option:
            res["sample_option"] = card(d.sample_option)
    return res


def look_at_dataset(ctx, a):
    """Preview a dataset before fetching it: size, columns, whether it is a plain table."""
    did = a["dataset_id"]
    r = ctx.registry.resolve(did, SAMPLE_IDS)
    if r is None:
        return _bad_id(did)
    if r.entry is None:
        entry = next(c for c in CATALOG if c["id"] == r.local_id)
        return {"name": entry["name"], "rows": entry["rows"], "tabular": True, "license": sanitise_license(entry["license"], trusted=True),
                "sample_data": True}
    try:
        i = r.entry.source.info(r.local_id)
    except SourceError as exc:
        return {"error": str(exc)}
    return {"rows": i.rows, "tabular": i.tabular, "gated": i.gated, "license": sanitise_license(i.license),
            "columns": mark([f"{c['name']} ({c['dtype']})" for c in i.columns[:25]], 80), "notes": i.notes}


def fetch_dataset(ctx, a):
    did = a["dataset_id"]
    r = ctx.registry.resolve(did, SAMPLE_IDS)
    if r is None:
        return _bad_id(did)
    if r.entry is None:
        entry = next(c for c in CATALOG if c["id"] == r.local_id)
        cand = datasets.add_candidate(ctx.session, ctx.storage, ctx.project, entry["name"], "bundled", entry["build"](),
                                      license=entry["license"])
        return {"candidate_id": cand.id, "rows": cand.rows, "suggested_target": entry["target"], "sample_data": True}
    try:
        f = r.entry.source.fetch_csv(r.local_id, settings.max_fetch_rows, settings.max_fetch_bytes)
    except SourceError as exc:
        return {"error": str(exc)}
    lic = sanitise_license(f.license)
    cand = datasets.add_candidate(ctx.session, ctx.storage, ctx.project, r.local_id, r.entry.label, f.csv_bytes,
                                  source_url=r.entry.url(r.local_id), license=None if lic == "not stated" else lic)
    out = {"candidate_id": cand.id, "rows": f.rows, "truncated": f.truncated, "license": lic}
    if f.suggested_target:
        out["suggested_target"] = f.suggested_target
    return out


def load_skill(ctx, a):
    body = skills.load(a["name"])
    return {"playbook": body} if body else {"error": f"unknown skill; available: {skills.names()}"}


def inspect_candidate(ctx, a):
    cand = datasets_repo.get_candidate(ctx.session, a["candidate_id"])
    if cand is None or cand.project_id != ctx.project.id or not cand.storage_key:
        return {"error": "unknown candidate"}
    df = pd.read_csv(io.BytesIO(ctx.storage.get(cand.storage_key)))
    if a["target"] not in df.columns:
        return {"error": f"column '{a['target'][:60]}' not found", "columns": mark(list(df.columns), 80)}
    res = analyze(df, a["target"])
    return {"grade": res["grade"], "findings": res["findings"], "preview": mark(df.head(3).to_dict("records"), 80)}


def select_dataset(ctx, a):
    v = datasets.select_candidate(ctx.session, ctx.storage, ctx.project, a["candidate_id"], a["target"])
    return {"rows": v.rows, "target": v.target_column, "other_candidates": "deleted"}


def run_readiness(ctx, a):
    r = analysis.readiness(ctx.session, ctx.storage, ctx.project)
    return {"grade": r.grade, "findings": r.findings}


def run_baseline_tool(ctx, a):
    r = analysis.baseline(ctx.session, ctx.storage, ctx.project)
    return {"accuracy": round(r.accuracy, 3), "simple_guess_accuracy": round(r.simple_guess_accuracy, 3),
            "trust_level": ctx.project.trust_level}


def run_pilot(ctx, a):
    try:
        f = pilot.run_pilot(ctx.session, ctx.storage, ctx.project, float(a["target"]))
    except pilot.ForecastError as exc:
        return {"error": str(exc)}
    out = {"label": "estimate", "target": f.target, "predicted": round(f.predicted_metric, 3),
           "band": [round(f.band_low, 3), round(f.band_high, 3)], "confidence": f.confidence, "eligible": f.eligible,
           "pilot_rows": (f.pilot or {}).get("rows_used"),
           "suggested_target": (f.pilot or {}).get("suggested_target"), "issues": (f.pilot or {}).get("issues", [])}
    out["next"] = "create the quote" if f.eligible else "explain honestly why we cannot sell this run: " + (f.reason or "")
    return out


def create_quote(ctx, a):
    try:
        q = quotes.create_quote(ctx.session, ctx.project)
    except (quotes.QuoteError, cost.QuoteTooExpensive) as exc:  # plain-language messages (not eligible, too expensive, wrong step). Anything else reaches the loop's generic handler.
        return {"error": str(exc)}
    return {"quote_id": q.id, "estimate_cents": q.estimate_cents, "range_cents": [q.low_cents, q.high_cents],
            "cap_cents": q.cap_cents, "success_fee_cents": q.fee_cents, "label": "estimate",
            "next": "the user must approve this quote"}


def request_payment(ctx, a):
    pay, url = payments.create_order(ctx.session, ctx.provider, ctx.provider_name, ctx.project)
    return {"payment_id": pay.id, "hold_cents": pay.amount_cents, "approve_url": url,
            "next": "the user approves the hold in PayPal; nothing is charged yet; the server confirms the hold"}


def start_training(ctx, a):
    run = training.run_training(ctx.session, ctx.project, ctx.backend, ctx.storage, ctx.provider)
    return {"status": run.status, "cost_cents": run.cost_cents, "result": run.result}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("search_datasets", "Find datasets that fit the user's goal.", _obj(query={"type": "string"}), gate.Action.SEARCH, search_datasets),
    Tool("discover_datasets", "Find datasets that fit the goal when the user has no data. Give a short goal summary and 2 or 3 short English search phrases.",
         {"type": "object", "properties": {"goal_summary": {"type": "string"}, "queries": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3}},
          "required": ["goal_summary", "queries"]}, gate.Action.DISCOVER, discover_datasets),
    Tool("look_at_dataset", "Preview a found dataset (size, columns, plain table or not) before fetching it.",
         _obj(dataset_id={"type": "string"}), gate.Action.SEARCH, look_at_dataset),
    Tool("fetch_dataset", "Download a found dataset into temporary storage.", _obj(dataset_id={"type": "string"}), gate.Action.FETCH, fetch_dataset),
    Tool("load_skill", "Load a playbook before doing what it covers.", _obj(name={"type": "string"}), gate.Action.SEARCH, load_skill),
    Tool("inspect_candidate", "Check a candidate dataset: grade, findings, preview.",
         _obj(candidate_id={"type": "string"}, target={"type": "string"}), gate.Action.ANALYZE, inspect_candidate),
    Tool("select_dataset", "Choose the dataset to use (user must approve). Deletes the other candidates.",
         _obj(candidate_id={"type": "string"}, target={"type": "string"}), gate.Action.SELECT_DATASET, select_dataset),
    Tool("run_readiness", "Readiness grade and findings for the chosen dataset.", _obj(), gate.Action.ANALYZE, run_readiness),
    Tool("run_baseline", "Free test on held-out data; also measures timings for the quote.", _obj(), gate.Action.BASELINE, run_baseline_tool),
    Tool("run_pilot", "Free small test on about 5-10% of the data, then forecast the full-run result against the user's target (0 to 1, e.g. 0.8).",
         {"type": "object", "properties": {"target": {"type": "number"}}, "required": ["target"]}, gate.Action.PILOT, run_pilot),
    Tool("create_quote", "One fixed price for the full run (estimated compute + success fee) and a hard cap. Only after an eligible forecast.", _obj(), gate.Action.CREATE_QUOTE, create_quote),
    Tool("request_payment", "Create the PayPal hold for the approved quote (nothing is charged yet).", _obj(), gate.Action.REQUEST_PAYMENT, request_payment),
    Tool("start_training", "Start paid training. Only works after the server confirmed the hold.", _obj(), gate.Action.START_TRAINING, start_training),
]}
