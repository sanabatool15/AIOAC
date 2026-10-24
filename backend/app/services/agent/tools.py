"""Agent tools (specs/agent.md section 3). Each tool declares the gate action it needs."""
import io
import re
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import DatasetCandidate, Project
from ...config import settings
from ...providers.datasets.base import DatasetSource, SourceError
from ...providers.payments.base import PaymentProvider
from ...providers.storage.base import Storage
from ...providers.training.base import TrainingBackend
from ...samples import CATALOG
from .. import analysis, cost, datasets, gate, payments, quotes, training
from . import skills
from ..insights import analyze
from .context import mark, sanitise_license


@dataclass
class ToolContext:
    session: Session
    project: Project
    storage: Storage
    provider: PaymentProvider
    provider_name: str
    backend: TrainingBackend
    source: DatasetSource
    approved: set[str] = field(default_factory=set)  # L1 actions the user approved this turn


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


HF_HINT = "Hugging Face dataset ids start with 'hf:', for example hf:owner/name. Use an id exactly as search_datasets returned it."


def _bad_id(did: str) -> dict:
    hint = f" {HF_HINT}" if "/" in did else f" Use an id exactly as search_datasets returned it."
    return {"error": f"unknown dataset id '{did[:80]}'.{hint}"}


def search_datasets(ctx, a):
    out = [{"id": c["id"], "name": c["name"], "source": "bundled sample", "sample_data": True,
            "note": "synthetic sample data made by us, not real customers", "license": sanitise_license(c["license"], trusted=True)}
           for c in CATALOG if _sample_matches(c, a["query"])]
    try:
        for h in ctx.source.search(a["query"], limit=6):
            out.append({"id": f"hf:{h.id}", "name": h.id, "source": "Hugging Face", "about": mark(h.description or ""),
                        "license": sanitise_license(h.license), "downloads": h.downloads, "gated": h.gated})
    except SourceError as exc:
        return {"results": out, "warning": str(exc)}
    return {"results": out[:8]}


def look_at_dataset(ctx, a):
    """Preview a dataset before fetching it: size, columns, whether it is a plain table."""
    did = a["dataset_id"]
    if not did.startswith("hf:"):
        entry = next((c for c in CATALOG if c["id"] == did), None)
        return ({"name": entry["name"], "rows": entry["rows"], "tabular": True, "license": sanitise_license(entry["license"], trusted=True),
                 "sample_data": True} if entry else _bad_id(did))
    try:
        i = ctx.source.info(did[3:])
    except SourceError as exc:
        return {"error": str(exc)}
    return {"rows": i.rows, "tabular": i.tabular, "gated": i.gated, "license": sanitise_license(i.license),
            "columns": mark([f"{c['name']} ({c['dtype']})" for c in i.columns[:25]], 80), "notes": i.notes}


def fetch_dataset(ctx, a):
    did = a["dataset_id"]
    if did.startswith("hf:"):
        try:
            f = ctx.source.fetch_csv(did[3:], settings.max_fetch_rows, settings.max_fetch_bytes)
        except SourceError as exc:
            return {"error": str(exc)}
        lic = sanitise_license(f.license)
        cand = datasets.add_candidate(ctx.session, ctx.storage, ctx.project, did[3:], "Hugging Face", f.csv_bytes,
                                      source_url=f"https://huggingface.co/datasets/{did[3:]}", license=None if lic == "not stated" else lic)
        return {"candidate_id": cand.id, "rows": f.rows, "truncated": f.truncated, "license": lic}
    entry = next((c for c in CATALOG if c["id"] == did), None)
    if entry is None:
        return _bad_id(did)
    cand = datasets.add_candidate(ctx.session, ctx.storage, ctx.project, entry["name"], "bundled", entry["build"](),
                                  license=entry["license"])
    return {"candidate_id": cand.id, "rows": cand.rows, "suggested_target": entry["target"], "sample_data": True}


def load_skill(ctx, a):
    body = skills.load(a["name"])
    return {"playbook": body} if body else {"error": f"unknown skill; available: {skills.names()}"}


def inspect_candidate(ctx, a):
    cand = ctx.session.get(DatasetCandidate, a["candidate_id"])
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


def create_quote(ctx, a):
    try:
        q = quotes.create_quote(ctx.session, ctx.project)
    except (quotes.QuoteError, cost.QuoteTooExpensive) as exc:  # plain-language messages (too expensive, wrong step). Anything else reaches the loop's generic handler.
        return {"error": str(exc)}
    return {"quote_id": q.id, "estimate_cents": q.estimate_cents, "range_cents": [q.low_cents, q.high_cents],
            "cap_cents": q.cap_cents, "label": "estimate", "next": "the user must approve this quote"}


def request_payment(ctx, a):
    pay, url = payments.create_order(ctx.session, ctx.provider, ctx.provider_name, ctx.project)
    return {"payment_id": pay.id, "amount_cents": pay.amount_cents, "approve_url": url, "next": "the user pays; the server confirms"}


def start_training(ctx, a):
    run = training.run_training(ctx.session, ctx.project, ctx.backend, ctx.storage, ctx.provider)
    return {"status": run.status, "cost_cents": run.cost_cents, "result": run.result}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("search_datasets", "Find datasets that fit the user's goal.", _obj(query={"type": "string"}), gate.Action.SEARCH, search_datasets),
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
    Tool("create_quote", "Estimate the training cost: estimate, range and spending cap.", _obj(), gate.Action.CREATE_QUOTE, create_quote),
    Tool("request_payment", "Create the payment request for the approved quote.", _obj(), gate.Action.REQUEST_PAYMENT, request_payment),
    Tool("start_training", "Start paid training. Only works after the server verified payment.", _obj(), gate.Action.START_TRAINING, start_training),
]}
