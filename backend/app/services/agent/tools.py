"""Agent tools (specs/agent.md section 3). Each tool declares the gate action it needs."""
import io
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import DatasetCandidate, Project
from ...providers.payments.base import PaymentProvider
from ...providers.storage.base import Storage
from ...providers.training.base import TrainingBackend
from ...samples import CATALOG
from .. import analysis, datasets, gate, payments, quotes, training
from ..insights import analyze


@dataclass
class ToolContext:
    session: Session
    project: Project
    storage: Storage
    provider: PaymentProvider
    provider_name: str
    backend: TrainingBackend
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


def search_datasets(ctx, a):
    q = a["query"].lower()
    hits = [{"id": c["id"], "name": c["name"], "rows": c["rows"], "license": c["license"]}
            for c in CATALOG if any(k in q for k in c["keywords"]) or q in c["name"].lower()]
    return {"results": hits, "note": "web search is not available yet; only bundled datasets are listed"}


def fetch_dataset(ctx, a):
    entry = next((c for c in CATALOG if c["id"] == a["dataset_id"]), None)
    if entry is None:
        return {"error": "unknown dataset id"}
    cand = datasets.add_candidate(ctx.session, ctx.storage, ctx.project, entry["name"], "bundled", entry["build"](),
                                  license=entry["license"])
    return {"candidate_id": cand.id, "rows": cand.rows, "suggested_target": entry["target"]}


def inspect_candidate(ctx, a):
    cand = ctx.session.get(DatasetCandidate, a["candidate_id"])
    if cand is None or cand.project_id != ctx.project.id or not cand.storage_key:
        return {"error": "unknown candidate"}
    df = pd.read_csv(io.BytesIO(ctx.storage.get(cand.storage_key)))
    if a["target"] not in df.columns:
        return {"error": f"column '{a['target']}' not found", "columns": list(df.columns)}
    res = analyze(df, a["target"])
    return {"grade": res["grade"], "findings": res["findings"], "preview": df.head(3).to_dict("records")}


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
    except (quotes.QuoteError, Exception) as exc:  # QuoteTooExpensive etc.
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
    Tool("fetch_dataset", "Download a found dataset into temporary storage.", _obj(dataset_id={"type": "string"}), gate.Action.FETCH, fetch_dataset),
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
