"""A plain-language feed of what happened in a project, built by code (never by the model).

Two sources, merged by time: (1) the agent trace (what the assistant did), (2) the stored rows (readiness reports, free
tests, forecasts, quotes, payments, training runs), so steps done with buttons appear too. A trace line for a step that
a stored row already covers (same step, within two minutes) is dropped, so nothing shows twice.

Raw tool JSON, dataset rows, error text, storage keys and secrets are never copied into the feed: each line is a fixed
sentence with a few safe values (a dataset name, a row count, a grade, a dollar amount). User text is scrubbed and cut.
"""
import re
from datetime import datetime, timedelta, timezone

from ..db import Session
from ..db.tables import Project
from ..repositories import analysis as analysis_repo
from ..repositories import datasets as datasets_repo
from ..repositories import forecasts as forecasts_repo
from ..repositories import payments as payments_repo
from ..repositories import quotes as quotes_repo
from ..repositories import training_runs as runs_repo
from ..repositories.traces import TraceRepository
from .agent.runlog import scrub
from .agent.target import APPROVAL_PREFIX

ACTION_WORDS = {"select_dataset": "choose the dataset", "request_payment": "ask for the payment hold",
                "start_training": "start training", "create_quote": "create a price estimate", "pilot": "run the free pilot",
                "baseline": "run the free test", "analyze": "check the data", "fetch": "download a dataset",
                "search": "search for datasets", "discover": "search for datasets", "clean": "clean the data"}
LEVEL_ONE_TWO = {"select_dataset", "clean", "request_payment", "start_training"}


def _s(v, n=80) -> str:
    return scrub(str(v)).replace("\n", " ").strip()[:n]


def _rows(n) -> str:
    return f"{n:,} rows" if isinstance(n, int) else "some rows"


_TAG = re.compile(r"</?\s*untrusted_dataset_text\s*>", re.I)
# The only reasons discovery may report for a skipped dataset (services/data/discovery.py prefilter). Anything else is ignored,
# so no free text from outside can reach the feed.
DROP_REASONS = ("needs a login or approval", "not a plain table", "not a prediction of a category", "too few rows")
IN_PROGRESS = {"search_datasets": "Searching open datasets", "discover_datasets": "Searching open datasets",
               "look_at_dataset": "Looking at a dataset", "fetch_dataset": "Downloading a dataset",
               "inspect_candidate": "Checking the columns of a dataset", "run_readiness": "Checking data readiness", "profile_data": "Looking at the columns of your data",
               "run_baseline": "Running the free test", "run_pilot": "Running the free pilot",
               "create_quote": "Preparing a price estimate"}
IN_PROGRESS_MAX_AGE = timedelta(minutes=3)  # a call with no result after this long is not shown (a crashed turn must not look busy forever)


def _title(v, n=60) -> str:
    """A dataset name as the user saw it: the untrusted tag removed, scrubbed, cut. Empty string when there is none."""
    return _s(_TAG.sub("", v), n) if isinstance(v, str) else ""


def _queries(args: dict) -> str:
    q = args.get("queries") or args.get("query") or args.get("goal_summary") or ""
    return ", ".join(_s(x, 40) for x in q[:3]) if isinstance(q, list) else _s(q)


def _tool_lines(name: str, args: dict, result: dict, titles: dict[str, str]) -> list[tuple[str, str]]:
    """Plain sentences for one finished tool call. `titles` maps a dataset id to the title discovery showed (ids are never shown)."""
    if not isinstance(result, dict):
        result = {}
    if result.get("error"):
        title = titles.get(str(args.get("dataset_id", ""))) if name in ("look_at_dataset", "fetch_dataset") else None
        if title:
            return [("problem", f'Could not use "{title}", so the assistant tried another way')]
        return [("problem", "One step did not work, so the assistant tried another way")]
    if result.get("waiting_for_choice"):
        return [("question", "Waiting for you to choose how to bring your data")]
    if result.get("need_clarity"):
        return [("question", "Asked what you want to predict before searching")]
    if name in ("search_datasets", "discover_datasets"):
        q = _queries(args)
        lines = [("search", f"Searched open datasets for {q}" if q else "Searched open datasets")]
        items = result.get("candidates") if name == "discover_datasets" else result.get("results")
        items = [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []
        names = [t for t in (_title(i.get("name"), 50) for i in items) if t][:3]
        if result.get("nothing_fits"):
            lines.append(("search", "Nothing found was a good fit for your goal"))
        elif items:
            n = len(items)
            tail = ": " + ", ".join(f'"{t}"' for t in names) if names else ""
            lines.append(("search", f"Found {n} possible dataset{'s' if n != 1 else ''}{tail}"))
        copies = result.get("near_copies_removed")
        if isinstance(copies, int) and copies > 0:
            lines.append(("search", "Left out 1 near-copy of a dataset already in the list" if copies == 1
                          else f"Left out {copies} near-copies of datasets already in the list"))
        dropped = result.get("dropped")
        if isinstance(dropped, dict):
            parts = [f"{r} ({dropped[r]})" for r in DROP_REASONS if isinstance(dropped.get(r), int) and dropped[r] > 0]
            if parts:
                lines.append(("search", "Skipped datasets that cannot be used: " + ", ".join(parts)))
        return lines
    if name == "look_at_dataset":
        title = _title(result.get("title") or result.get("name"), 60) or titles.get(str(args.get("dataset_id", "")), "")
        who = f'"{title}"' if title else "A dataset"
        if result.get("tabular") is False:
            return [("look", f"{who} is not a plain table, skipped")]
        if result.get("gated"):
            return [("look", f"{who} needs a login or approval, skipped")]
        if title:
            return [("look", f'Looked at "{title}" ({_rows(result.get("rows"))})')]
        return [("look", f"Looked at a dataset ({_rows(result.get('rows'))})")]
    if name == "fetch_dataset":
        title = _title(result.get("title"), 60) or titles.get(str(args.get("dataset_id", "")), "")
        lines = [("download", f'Downloaded "{title}" ({_rows(result.get("rows"))})' if title else f"Downloaded a dataset ({_rows(result.get('rows'))})")]
        if result.get("truncated"):
            lines.append(("download", f'Only the first {_rows(result.get("rows"))} of "{title}" were kept because the dataset is large'
                          if title else f"Only the first {_rows(result.get('rows'))} were kept because the dataset is large"))
        return lines
    if name == "inspect_candidate":
        return [("check", "Checked the columns of a dataset")]
    if name == "select_dataset":
        return [("choose", f"Chose the dataset ({_rows(result.get('rows'))}) to predict \"{_s(result.get('target') or '', 40)}\"")]
    if name == "run_readiness":
        return [("check", f"Checked data readiness: grade {_s(result.get('grade') or '?', 3)}")]
    if name == "run_baseline":
        acc = result.get("accuracy")
        return [("test", f"Ran the free test: about {round(acc * 100)} out of 100 right" if isinstance(acc, (int, float)) else "Ran the free test")]
    if name == "run_pilot":
        return [("forecast", "Ran the free pilot on a small part of your data to forecast the full result")]
    if name == "profile_data":
        return [("check", "Looked at the columns of your data")]
    if name == "propose_data_fix":
        return [("check", "Looked at what a data fix could change (nothing was changed)")]
    if name == "apply_data_fix":
        return [("datafix", "Changed your data after you approved it (the original is kept)")]
    if name == "create_quote":
        return [("quote", "Created a price estimate")]
    if name == "request_payment":
        return [("payment", "Prepared the payment hold request")]
    if name == "start_training":
        return [("training", "Started training")]
    return []  # load_skill and anything unknown are not shown


def _remember_titles(result, titles: dict[str, str]) -> None:
    """Keep id -> title from a search or discovery result, so later look/fetch lines can name the dataset (never the id)."""
    if not isinstance(result, dict):
        return
    items: list = []
    for key in ("candidates", "results"):
        if isinstance(result.get(key), list):
            items += result[key]
    if isinstance(result.get("sample_option"), dict):
        items.append(result["sample_option"])
    for i in items:
        if isinstance(i, dict) and isinstance(i.get("id"), str) and (t := _title(i.get("name"), 60)):
            titles[i["id"]] = t


# trace tool name -> the step a stored row also records
TRACE_STEP = {"profile_data": "profile", "apply_data_fix": "datafix", "run_readiness": "readiness", "run_baseline": "baseline", "run_pilot": "pilot", "create_quote": "quote",
              "request_payment": "payment", "start_training": "training"}
DUPLICATE_WINDOW = timedelta(minutes=2)


def _utc(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _usd(cents) -> str:
    return f"${(cents or 0) / 100:,.2f}"


def _stored(session: Session, project: Project) -> list[tuple[datetime, str, str, str]]:
    """(time, step, kind, text) from the stored rows. Fixed sentences only."""
    out: list[tuple[datetime, str, str, str]] = []
    for r in analysis_repo.insight_reports_for_project(session, project.id):
        out.append((r.created_at, "readiness", "check", f"Checked data readiness: grade {_s(r.grade, 3)}"))
    for b in analysis_repo.baseline_runs_for_project(session, project.id):
        out.append((b.created_at, "baseline", "test", f"Ran the free test: about {round(b.accuracy * 100)} out of 100 right"))
    for f in forecasts_repo.all_for_project(session, project.id):
        ok = "can be sold" if f.eligible else "is not eligible to run yet"
        out.append((f.created_at, "pilot", "forecast", f"Forecast ready: about {round(f.confidence * 100)}% chance of reaching "
                    f"{round(f.target * 100)} out of 100 right (an estimate); this run {ok}"))
    for v in datasets_repo.versions_for_project(session, project.id):
        if v.parent_id:
            out.append((v.created_at, "datafix", "datafix", f"Changed your data after you approved it: {_s(v.notes or 'a data fix', 200)} (the original is kept)"))
    for q in quotes_repo.all_for_project(session, project.id):
        out.append((q.created_at, "quote", "quote", f"Price estimate ready: about {_usd(q.estimate_cents)} "
                    f"(an estimate; the most you can be charged is {_usd(q.cap_cents)})"))
        if q.approved_at:
            out.append((q.approved_at, "approve", "approved", "You approved the price estimate"))
    runs = runs_repo.all_for_project(session, project.id)
    settled_at = max((r.finished_at for r in runs if r.finished_at), default=None)
    for r in runs:
        out.append((r.started_at, "training", "training", "Training started"))
        if r.finished_at:
            if r.status == "done":
                out.append((r.finished_at, "run_end", "training", "Training finished and the result was checked on data it had not seen"))
            elif r.status == "stopped":
                out.append((r.finished_at, "run_end", "training", "Training was stopped; you pay only the compute used so far"))
            elif r.status == "failed":
                out.append((r.finished_at, "run_end", "problem", "Training failed on our side, so the whole hold is released and you pay $0"))
    for p in payments_repo.all_for_project(session, project.id):
        out.append((p.created_at, "payment", "payment", f"Payment hold requested: up to {_usd(p.amount_cents)}, nothing charged yet"))
        later = settled_at or p.created_at
        if p.verified or p.state not in ("none", "declined", "expired"):
            out.append((p.created_at + timedelta(microseconds=1), "hold", "payment",
                        "PayPal hold confirmed by the server: nothing is charged until the work is done"))
        if p.compute_captured_cents:
            out.append((later, "settle", "payment", f"Charged {_usd(p.compute_captured_cents)} for the compute used"))
        if p.fee_captured_cents:
            out.append((later, "settle", "payment", f"Charged {_usd(p.fee_captured_cents)} success fee, because the result was verified"))
        if p.state == "fee_skipped":
            out.append((later, "settle", "payment", "No success fee: the target was not verified"))
        if p.state == "voided":
            out.append((later, "settle", "payment", "The hold was released in full; you pay $0"))
        elif p.released_cents:
            out.append((later, "settle", "payment", f"Released {_usd(p.released_cents)} of the hold; it was never charged"))
        if p.state == "expired":
            out.append((p.created_at, "settle", "problem", "The payment hold expired before it was used"))
        if p.state == "declined":
            out.append((p.created_at, "settle", "problem", "PayPal did not confirm the hold, so nothing was charged"))
    return [(_utc(t), step, kind, text) for t, step, kind, text in out]


def activity(session: Session, project: Project) -> list[dict]:
    stored = _stored(session, project)
    covered: dict[str, list[datetime]] = {}
    for t, step, _k, _x in stored:
        covered.setdefault(step, []).append(t)

    def duplicate(step: str | None, when: datetime) -> bool:
        return bool(step) and any(abs(_utc(when) - t) <= DUPLICATE_WINDOW for t in covered.get(step, []))

    feed: list[dict] = []
    pending: dict[str, tuple[dict, datetime]] = {}  # tool calls with no result yet: what the assistant is doing right now
    titles: dict[str, str] = {}
    for st in TraceRepository(session).steps(project.id):
        c = st.content if isinstance(st.content, dict) else {}
        lines: list[tuple[str, str]] = []
        step: str | None = None
        if st.kind == "user":
            if not str(c.get("text", "")).lstrip().startswith(APPROVAL_PREFIX):  # the server's own text for a pressed Approve button
                lines = [("you", f'You said: "{_s(c.get("text", ""), 100)}"')]
        elif st.kind == "assistant":
            lines = [("reply", "The assistant replied")]
        elif st.kind == "tool_call":
            pending[c.get("name", "")] = (c.get("args") if isinstance(c.get("args"), dict) else {}, _utc(st.created_at))
        elif st.kind == "tool_result":
            name = c.get("name", "")
            args, _t = pending.pop(name, ({}, None))
            _remember_titles(c.get("result"), titles)
            lines = _tool_lines(name, args, c.get("result"), titles)
            step = TRACE_STEP.get(name)
        elif st.kind == "gate":
            action = c.get("action", "")
            words = ACTION_WORDS.get(action, "do that")
            if c.get("allowed") is False and c.get("reason") == "needs user approval":
                lines = [("approval", "Waited for your approval")]
            elif c.get("allowed") is False:
                lines = [("blocked", f"Held back a step ({words}): {_s(c.get('reason', 'not allowed yet'), 120)}")]
            elif action in LEVEL_ONE_TWO:
                lines = [("approved", f"Allowed to {words}")]
        elif st.kind == "forecast":
            step = "pilot"
            pct = c.get("confidence")
            ok = "can be sold" if c.get("eligible") else "is not eligible to run yet"
            lines = [("forecast", f"Forecast ready: about {round(pct * 100)}% chance of reaching your target; this run {ok}"
                      if isinstance(pct, (int, float)) else "Forecast ready")]
        elif st.kind == "settle_failed":
            lines = [("payment", "Settling the payment hit a problem; it can be retried safely")]
        elif st.kind == "limit":
            lines = [("limit", "The assistant stopped at a safety limit")]
        elif st.kind == "llm_error":
            lines = [("problem", "The AI service had a problem")]
        elif st.kind == "claim_blocked":
            lines = [("guard", "Corrected a reply that claimed something that had not happened")]
        elif st.kind == "tool_refused":
            lines = [("blocked", "A step was refused because it was not allowed yet")]
        if not duplicate(step, st.created_at):
            feed += [{"when": _utc(st.created_at), "kind": k, "text": x} for k, x in lines]
    now = datetime.now(timezone.utc)
    for name, (args, when) in pending.items():  # calls still running: shown as "...ing" until their result arrives
        if name in IN_PROGRESS and now - when <= IN_PROGRESS_MAX_AGE:
            q = _queries(args) if name in ("search_datasets", "discover_datasets") else ""
            feed.append({"when": when, "kind": "working", "text": f"{IN_PROGRESS[name]} for {q}…" if q else f"{IN_PROGRESS[name]}…"})
    feed += [{"when": t, "kind": kind, "text": text} for t, _step, kind, text in stored]
    feed.sort(key=lambda f: f["when"])  # stable: equal times keep the order they were added in
    return feed
