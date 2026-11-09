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
from ...integrations.jobs.inline import InlineJobRunner
from ...integrations.datasets.registry import SourceRegistry, as_registry
from ...ports import PaymentProvider, Storage, TrainingBackend
from ..data.samples import CATALOG
from ..data import analysis, datasets, discovery, families, fixes, pilot, profile as data_profile
from ..cost import cost, quotes
from .. import explain, gate, payments, training
from . import clarity, data_choice, memory, skills, target as target_rule
from ...repositories.traces import TraceRepository
from ..data.insights import analyze, summarize
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
    runner: object | None = None                     # JobRunner for paid training; None builds a synchronous one (tests, evals)

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
    """Search only after the user chose it (data_choice.py), and only for a goal that names an outcome (clarity.py)."""
    texts = memory.user_texts(ctx.session, ctx.project)
    if not clarity.is_clear(texts):  # a greeting or a goal with no outcome: ask what to predict before anything else
        ctx.emit("need_clarity", "INFO")
        return {"need_clarity": True, "advice": clarity.QUESTION_HINT}
    if not data_choice.wants_search(texts):
        ctx.emit("waiting_for_choice", "INFO")
        return {"waiting_for_choice": True, "advice": data_choice.WAITING_HINT}
    return None


_TAG = re.compile(r"</?\s*untrusted_dataset_text\s*>", re.I)


def dataset_title(ctx, dataset_id: str) -> str | None:
    """The human title the user was shown for a dataset id (from this project's earlier search or discovery results), else None."""
    for st in reversed(TraceRepository(ctx.session).steps(ctx.project.id, ("tool_result",))):
        c = st.content if isinstance(st.content, dict) else {}
        res = c.get("result")
        if c.get("name") not in ("discover_datasets", "search_datasets") or not isinstance(res, dict):
            continue
        for item in (res.get("candidates") or []) + (res.get("results") or []) + ([res["sample_option"]] if res.get("sample_option") else []):
            if isinstance(item, dict) and item.get("id") == dataset_id and isinstance(item.get("name"), str):
                title = " ".join(_TAG.sub("", item["name"]).split())[:120]
                return title or None
    return None


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
    res = {"candidates": [card(s) for s in d.results], "sources": d.sources, "near_copies_removed": d.collapsed,
           "dropped": d.dropped}  # reason -> count, plain words from discovery.prefilter; also shown in the activity feed
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
    out = {"rows": i.rows, "tabular": i.tabular, "gated": i.gated, "license": sanitise_license(i.license),
           "columns": mark([f"{c['name']} ({c['dtype']})" for c in i.columns[:25]], 80), "notes": i.notes}
    if (title := dataset_title(ctx, did)):
        out["title"] = title
    return out


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
    title = dataset_title(ctx, did)  # the name the user was shown; the source id stays in source_url
    cand = datasets.add_candidate(ctx.session, ctx.storage, ctx.project, title or r.local_id, r.entry.label, f.csv_bytes,
                                  source_url=r.entry.url(r.local_id), license=None if lic == "not stated" else lic)
    out = {"candidate_id": cand.id, "rows": f.rows, "truncated": f.truncated, "license": lic}
    if title:
        out["title"] = title
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
    return {"grade": res["grade"], "findings": res["findings"], "summary": _marked_summary(df, a["target"]),
            "preview": mark(df.iloc[:3, :6].round(3).to_dict("records"), 80)}


def select_dataset(ctx, a):
    v = datasets.select_candidate(ctx.session, ctx.storage, ctx.project, a["candidate_id"], a["target"])
    return {"rows": v.rows, "target": v.target_column, "other_candidates": "deleted"}


def select_dataset_card(ctx, a) -> dict:
    """Plain-language parts of the approval card for select_dataset: which dataset, from where, how big, which column.
    Read-only. Anything unknown is None, and then `what` is left out so the gate's generic text stays."""
    cand = datasets_repo.get_candidate(ctx.session, str(a.get("candidate_id", "")))
    if cand is not None and cand.project_id != ctx.project.id:
        cand = None
    target = a.get("target") if isinstance(a.get("target"), str) and a.get("target") else None
    meaning = a.get("target_meaning") if isinstance(a.get("target_meaning"), str) and a.get("target_meaning").strip() else None
    meaning = " ".join(meaning.split())[:120] if meaning else None
    detail = {"name": None, "source": None, "rows": None, "columns": None, "license": None, "target": target, "target_meaning": meaning}
    if cand is None:
        return {"detail": detail}
    columns = None
    if cand.storage_key:
        try:
            columns = len(pd.read_csv(io.BytesIO(ctx.storage.get(cand.storage_key)), nrows=0).columns)
        except Exception:
            columns = None
    detail.update(name=cand.name, source=cand.source, rows=cand.rows, columns=columns, license=cand.license)
    source = "sample data" if cand.source == "bundled" else cand.source
    size = f"{source}, {cand.rows:,} rows" if cand.rows is not None else source
    what = f'Use "{cand.name}" ({size})'
    if target and meaning:
        what += f' and predict "{target}": {meaning}'
    elif target:
        what += f' and predict the column "{target}"'
    return {"what": what, "detail": detail}


def _marked_summary(df, target: str) -> dict:
    """insights.summarize with every dataset-derived string (column names, group labels) wrapped as untrusted data."""
    s = summarize(df, target)
    if s["balance"]:
        b = s["balance"]
        s["balance"] = {"groups": b["groups"], "smallest_group_out_of_100": b["smallest_group_out_of_100"],
                        "text": mark(b["text"], 120)}
    s["missing_columns"] = mark(s["missing_columns"], 60) if s["missing_columns"] else []   # one wrapper per group keeps this small
    s["ignored_columns"] = mark({"row_labels": s.pop("ignored_row_label_columns"), "constant": s.pop("ignored_constant_columns"),
                                 "copy_of_answer": s.pop("ignored_copy_of_answer_columns"),
                                 "numbers_stored_as_text": s.pop("numbers_stored_as_text_columns")}, 60)
    return s


def run_readiness(ctx, a):
    r = analysis.readiness(ctx.session, ctx.storage, ctx.project)
    out = {"grade": r.grade, "findings": r.findings}  # findings are shown to the user as they are (blocks.py)
    version = datasets_repo.get_version(ctx.session, ctx.project.chosen_dataset_version_id)
    out["summary"] = _marked_summary(pd.read_csv(ctx.storage.path(version.storage_key)), version.target_column)
    return out


def profile_data(ctx, a):
    """Free: a column-by-column look at the chosen dataset (kinds, gaps, top values, suspects). Dataset-derived text is marked."""
    if not ctx.project.chosen_dataset_version_id:
        return {"error": "no dataset has been chosen yet"}
    version = datasets_repo.get_version(ctx.session, ctx.project.chosen_dataset_version_id)
    if version is None:
        return {"error": "no dataset has been chosen yet"}
    df = pd.read_csv(ctx.storage.path(version.storage_key))
    wanted = a.get("columns")
    if wanted:
        bad = [c for c in wanted if c not in df.columns]
        if bad:
            return {"error": "no such column: " + ", ".join(repr(c[:40]) for c in bad[:3]), "columns": mark(list(df.columns)[:40], 60)}
    p = data_profile.profile(df, version.target_column, wanted or None)
    return {"rows": p["rows"], "columns_total": p["columns_total"], "target": mark(p["target"], 120),
            "columns": mark(p["columns"], 60), "suspects": mark(p["suspects"], 140),
            "next": "explain the one or two things that matter most in plain words; suspects are clues to check with the user, not proof"}


def explain_result(ctx, a):
    """Free and read-only: facts about the latest finished run, from stored rows. Nothing is run, nothing is paid."""
    return explain.result_facts(ctx.session, ctx.project)


def run_baseline_tool(ctx, a):
    r, o = analysis.baseline_detailed(ctx.session, ctx.storage, ctx.project)
    out = {"accuracy": round(r.accuracy, 3), "simple_guess_accuracy": round(r.simple_guess_accuracy, 3),
           "right_out_of_100": round(r.accuracy * 100), "simple_guess_out_of_100": round(r.simple_guess_accuracy * 100),
           "trust_level": ctx.project.trust_level, "train_rows": o.train_rows, "test_rows": o.test_rows}
    if o.rare_group_caught is not None:  # only when the smallest group is under 20% of the rows
        out["rare_group_caught_out_of_100"] = round(o.rare_group_caught * 100)
    return out


def _fix_view(prop: "fixes.FixProposal") -> dict:
    return {"available": prop.available, "message": prop.message, "version_id": prop.version_id,
            "rows_before": prop.rows_before, "rows_after": prop.rows_after, "rows_removed": prop.rows_removed,
            "columns_before": prop.columns_before, "columns_after": prop.columns_after, "columns_dropped": prop.columns_dropped,
            "steps": [{"what": s["what"], "why": s["why"]} for s in prop.steps], "fixes_left": prop.fixes_left, "note": prop.note}


def propose_data_fix(ctx, a):
    """Free and read-only: what a data fix would change. Nothing is changed until the user approves apply_data_fix."""
    try:
        prop = fixes.propose_fix(ctx.session, ctx.storage, ctx.project)
    except fixes.FixError as exc:
        return {"error": str(exc)}
    out = _fix_view(prop)
    out["next"] = ("tell the user plainly what would change and why; say we will test whether it changes the estimate and that it may not; "
                   "if they want it call apply_data_fix") if prop.available else "tell the user plainly that there is nothing safe to change"
    return out


def apply_data_fix(ctx, a):
    """Runs only after the user approved the card (level 1). Makes a new version of the data and re-runs the free steps."""
    try:
        child, prop = fixes.apply_fix(ctx.session, ctx.storage, ctx.project, expected_version_id=a.get("version_id") or None)
    except fixes.FixError as exc:
        return {"error": str(exc)}
    out = _fix_view(prop)
    out.update(version_id=child.id, fixes_left=max(0, prop.fixes_left - 1),
               next="the data is changed and the free data check and free test were re-run; now run the free small test again with the user's target and explain "
                    "whether the estimate moved, as an estimate, never as a promise")
    return out


def data_fix_card(ctx, a) -> dict:
    """Plain-language parts of the approval card for apply_data_fix: rows removed, columns dropped, before and after. Read-only."""
    try:
        prop = fixes.propose_fix(ctx.session, ctx.storage, ctx.project)
    except fixes.FixError:
        return {}
    if not prop.available:
        return {}
    change = prop.message[len("We can "):] if prop.message.startswith("We can ") else prop.message
    what = (f"Change your data: {change.rstrip('.')} ({prop.rows_before:,} rows to {prop.rows_after:,}, "
            f"{prop.columns_before} columns to {prop.columns_after}). The original stays saved.")
    detail = {"rows_before": prop.rows_before, "rows_after": prop.rows_after, "rows_removed": prop.rows_removed,
              "columns_before": prop.columns_before, "columns_after": prop.columns_after, "columns_dropped": prop.columns_dropped,
              "steps": [s["what"] for s in prop.steps], "version_id": prop.version_id, "note": prop.note}
    return {"what": what, "detail": detail, "args": {"version_id": prop.version_id}}


def run_pilot(ctx, a):
    """The target is the user's choice: it must match a number in their own words (see target.py)."""
    if not target_rule.user_named(memory.user_texts(ctx.session, ctx.project), float(a["target"])):
        ctx.emit("need_target", "INFO")
        b = ctx.project.baseline_result or {}
        return {"need_target": True, "baseline_percent": round(b["accuracy"] * 100) if b.get("accuracy") is not None else None,
                "hint": target_rule.QUESTION_HINT}
    try:
        f = pilot.run_pilot(ctx.session, ctx.storage, ctx.project, float(a["target"]))
    except pilot.ForecastError as exc:
        return {"error": str(exc)}
    out = {"label": "estimate", "target": f.target, "target_out_of_100": round(f.target * 100),
           "predicted": round(f.predicted_metric, 3), "predicted_out_of_100": round(f.predicted_metric * 100),
           "band": [round(f.band_low, 3), round(f.band_high, 3)], "band_out_of_100": [round(f.band_low * 100), round(f.band_high * 100)], "confidence": f.confidence, "eligible": f.eligible,
           "pilot_rows": (f.pilot or {}).get("rows_used"),
           "suggested_target": (f.pilot or {}).get("suggested_target"), "issues": (f.pilot or {}).get("issues", []),
           "model_type": families.plain_name(f.family) if f.family else None}
    p = f.pilot or {}
    if p.get("dropped"):
        out["models_dropped"] = [d["model"] for d in p["dropped"]][:3]
    if p.get("learning_curve"):
        out["learning_curve_out_of_100"] = [{"rows": c["training_rows"], "right_out_of_100": round(c["accuracy"] * 100)}
                                            for c in p["learning_curve"]][:5]
    if p.get("full_run_training_rows"):
        out["full_run_rows"] = p["full_run_training_rows"]
    out["next"] = "create the quote" if f.eligible else "explain honestly why we cannot sell this run: " + (f.reason or "")
    return out


def create_quote(ctx, a):
    try:
        q = quotes.create_quote(ctx.session, ctx.project)
    except (quotes.QuoteError, cost.QuoteTooExpensive) as exc:  # plain-language messages (not eligible, too expensive, wrong step). Anything else reaches the loop's generic handler.
        return {"error": str(exc)}
    bd = q.breakdown or {}
    breakdown = {"compute_estimate_cents": bd.get("compute_estimate_cents"), "compute_cap_cents": q.compute_cap_cents,
                 "storage_cents": bd.get("storage_cents"), "platform_fee_cents": bd.get("platform_fee_cents"),
                 "success_fee_estimate_cents": bd.get("success_fee_estimate_cents"), "success_fee_max_cents": q.fee_cents}

    def usd(c):
        return f"${(c or 0) / 100:,.2f}"
    return {"quote_id": q.id, "estimate_cents": q.estimate_cents, "range_cents": [q.low_cents, q.high_cents],
            "cap_cents": q.cap_cents, "success_fee_cents": q.fee_cents, "breakdown": breakdown,
            "in_dollars": {"estimate": usd(q.estimate_cents), "range": f"{usd(q.low_cents)} to {usd(q.high_cents)}", "most_you_can_be_charged": usd(q.cap_cents),
                           "platform_fee": usd(breakdown["platform_fee_cents"]), "storage": usd(breakdown["storage_cents"]),
                           "compute": usd(breakdown["compute_estimate_cents"]), "success_fee_max": usd(q.fee_cents)},
            "label": "estimate", "model_type": families.plain_name(q.family),
            "next": "the user must approve this quote"}


def request_payment(ctx, a):
    pay, url = payments.create_order(ctx.session, ctx.provider, ctx.provider_name, ctx.project)
    return {"payment_id": pay.id, "hold_cents": pay.amount_cents, "approve_url": url,
            "next": "the user approves the hold in PayPal; nothing is charged yet; the server confirms the hold"}


def start_training(ctx, a):
    """Same path as POST /train: the gate, then the run is queued and this returns at once (the turn lock is not held)."""
    runner = ctx.runner or InlineJobRunner(
        lambda rid: training.execute_run(ctx.session, rid, ctx.backend, ctx.storage, ctx.provider), threaded=False)
    try:
        run = training.start_and_enqueue(ctx.session, ctx.project, ctx.backend, ctx.provider, runner)
    except training.EnqueueFailed:
        return {"error": "the training job could not be queued; nothing was charged and the hold is being released"}
    return {"run_id": run.id, "status": run.status,
            "next": "training runs in the background; tell the user it has started and that progress and the final cost appear on the training screen"}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("search_datasets", "Find datasets that fit the user's goal.", _obj(query={"type": "string"}), gate.Action.SEARCH, search_datasets),
    Tool("discover_datasets", "Find datasets that fit the goal when the user has no data. Give a short goal summary and 2 or 3 short English search phrases.",
         {"type": "object", "properties": {"goal_summary": {"type": "string"}, "queries": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3}},
          "required": ["goal_summary", "queries"]}, gate.Action.DISCOVER, discover_datasets),
    Tool("look_at_dataset", "Preview a found dataset (size, columns, plain table or not) before fetching it.",
         _obj(dataset_id={"type": "string"}), gate.Action.SEARCH, look_at_dataset),
    Tool("fetch_dataset", "Download a found dataset into temporary storage.", _obj(dataset_id={"type": "string"}), gate.Action.FETCH, fetch_dataset),
    Tool("load_skill", "Load a playbook only when the situation in its one-line description is in front of you. Load each one once.", _obj(name={"type": "string"}), gate.Action.SEARCH, load_skill),
    Tool("inspect_candidate", "Check a candidate dataset: grade, findings, preview.",
         _obj(candidate_id={"type": "string"}, target={"type": "string"}), gate.Action.ANALYZE, inspect_candidate),
    Tool("select_dataset", "Choose the dataset to use (user must approve). Deletes the other candidates. Always fill target_meaning: "
         "what the answer column means in plain words, for example 'whether the next payment was missed'.",
         {"type": "object", "properties": {"candidate_id": {"type": "string"}, "target": {"type": "string"},
                                           "target_meaning": {"type": "string"}}, "required": ["candidate_id", "target"]},
         gate.Action.SELECT_DATASET, select_dataset),
    Tool("run_readiness", "Readiness grade and findings for the chosen dataset.", _obj(), gate.Action.ANALYZE, run_readiness),
    Tool("profile_data", "Free: look at the chosen data column by column (kind, gaps, common values, ranges) and flag suspects such as a column that gives the answer away. "
         "Use when the user asks about a column or you saw a suspect. Optionally name up to 8 columns.",
         {"type": "object", "properties": {"columns": {"type": "array", "items": {"type": "string"}, "maxItems": 8}}, "required": []},
         gate.Action.ANALYZE, profile_data),
    Tool("explain_result", "Free, read-only: plain facts about the finished run (final score against the target and the simple guess, model type, rows, data fixes, "
         "what was charged and released, what could help). Use when the user asks what the result means, why it missed, or what was charged.", _obj(),
         gate.Action.ANALYZE, explain_result),
    Tool("run_baseline", "Free test on held-out data; also measures timings for the quote.", _obj(), gate.Action.BASELINE, run_baseline_tool),
    Tool("propose_data_fix", "Free, changes nothing: what removing repeated rows or mostly empty columns would change. Use when the forecast is too low and the findings mention repeats or gaps. "
         "Never say it will raise the estimate: say we will test whether it changes the estimate.", _obj(), gate.Action.ANALYZE, propose_data_fix),
    Tool("apply_data_fix", "Apply the proposed data fix (the user must approve a card showing rows removed and columns dropped). Then run the free small test again.",
         {"type": "object", "properties": {"version_id": {"type": "string"}}, "required": []}, gate.Action.CLEAN, apply_data_fix),
    Tool("run_pilot", "Free small test on about 5-10% of the data, then forecast the full-run result against the target the USER named in their own words (0 to 1, e.g. 0.8). Never pick the target yourself: if they have not said it, ask.",
         {"type": "object", "properties": {"target": {"type": "number"}}, "required": ["target"]}, gate.Action.PILOT, run_pilot),
    Tool("create_quote", "One fixed price for the full run (estimated compute + success fee) and the most the user can be charged. Only after an eligible forecast.", _obj(), gate.Action.CREATE_QUOTE, create_quote),
    Tool("request_payment", "Create the PayPal hold for the approved quote (nothing is charged yet).", _obj(), gate.Action.REQUEST_PAYMENT, request_payment),
    Tool("start_training", "Start paid training. Only works after the server confirmed the hold.", _obj(), gate.Action.START_TRAINING, start_training),
]}
