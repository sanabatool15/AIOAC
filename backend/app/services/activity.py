"""A plain-language feed of what happened in a project, built by code (never by the model).

Two sources, merged by time: (1) the agent trace (what the assistant did), (2) the stored rows (readiness reports, free
tests, forecasts, quotes, payments, training runs), so steps done with buttons appear too. A trace line for a step that
a stored row already covers (same step, within two minutes) is dropped, so nothing shows twice.

Raw tool JSON, dataset rows, error text, storage keys and secrets are never copied into the feed: each line is a fixed
sentence with a few safe values (a dataset name, a row count, a grade, a dollar amount). User text is scrubbed and cut.
"""
from datetime import datetime, timedelta, timezone

from ..db import Session
from ..db.tables import Project
from ..repositories import analysis as analysis_repo
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
LEVEL_ONE_TWO = {"select_dataset", "request_payment", "start_training"}


def _s(v, n=80) -> str:
    return scrub(str(v)).replace("\n", " ").strip()[:n]


def _rows(n) -> str:
    return f"{n:,} rows" if isinstance(n, int) else "some rows"


def _tool_line(name: str, args: dict, result: dict) -> tuple[str, str] | None:
    if not isinstance(result, dict):
        result = {}
    if result.get("error"):
        return "problem", "One step did not work, so the assistant tried another way"
    if result.get("waiting_for_choice"):
        return "question", "Waiting for you to choose how to bring your data"
    if result.get("need_clarity"):
        return "question", "Asked what you want to predict before searching"
    if name in ("search_datasets", "discover_datasets"):
        q = args.get("queries") or args.get("query") or args.get("goal_summary") or ""
        q = ", ".join(_s(x, 40) for x in q[:3]) if isinstance(q, list) else _s(q)
        return "search", f"Searched open datasets for {q}" if q else "Searched open datasets"
    if name == "look_at_dataset":
        title = result.get("title") or result.get("name")  # never the raw id ("uci:144"): the user knows datasets by title
        return "look", f'Looked at "{_s(title, 60)}" ({_rows(result.get("rows"))})' if title else f"Looked at a dataset ({_rows(result.get('rows'))})"
    if name == "fetch_dataset":
        title = result.get("title")
        return "download", f'Downloaded "{_s(title, 60)}" ({_rows(result.get("rows"))})' if title else f"Downloaded a dataset ({_rows(result.get('rows'))})"
    if name == "inspect_candidate":
        return "check", "Checked the columns of a dataset"
    if name == "select_dataset":
        return "choose", f"Chose the dataset ({_rows(result.get('rows'))}) to predict \"{_s(result.get('target') or '', 40)}\""
    if name == "run_readiness":
        return "check", f"Checked data readiness: grade {_s(result.get('grade') or '?', 3)}"
    if name == "run_baseline":
        acc = result.get("accuracy")
        text = f"Ran the free test: about {round(acc * 100)} out of 100 right" if isinstance(acc, (int, float)) else "Ran the free test"
        return "test", text
    if name == "run_pilot":
        return "forecast", "Ran the free pilot on a small part of your data to forecast the full result"
    if name == "create_quote":
        return "quote", "Created a price estimate"
    if name == "request_payment":
        return "payment", "Prepared the payment hold request"
    if name == "start_training":
        return "training", "Started training"
    return None  # load_skill and anything unknown are not shown


# trace tool name -> the step a stored row also records
TRACE_STEP = {"run_readiness": "readiness", "run_baseline": "baseline", "run_pilot": "pilot", "create_quote": "quote",
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
    last_args: dict[str, dict] = {}
    for st in TraceRepository(session).steps(project.id):
        c = st.content if isinstance(st.content, dict) else {}
        line: tuple[str, str] | None = None
        step: str | None = None
        if st.kind == "user":
            if not str(c.get("text", "")).lstrip().startswith(APPROVAL_PREFIX):  # the server's own text for a pressed Approve button
                line = ("you", f'You said: "{_s(c.get("text", ""), 100)}"')
        elif st.kind == "assistant":
            line = ("reply", "The assistant replied")
        elif st.kind == "tool_call":
            last_args[c.get("name", "")] = c.get("args") if isinstance(c.get("args"), dict) else {}
        elif st.kind == "tool_result":
            name = c.get("name", "")
            line = _tool_line(name, last_args.pop(name, {}), c.get("result"))
            step = TRACE_STEP.get(name)
        elif st.kind == "gate":
            action = c.get("action", "")
            words = ACTION_WORDS.get(action, "do that")
            if c.get("allowed") is False and c.get("reason") == "needs user approval":
                line = ("approval", "Waited for your approval")
            elif c.get("allowed") is False:
                line = ("blocked", f"Held back a step ({words}): {_s(c.get('reason', 'not allowed yet'), 120)}")
            elif action in LEVEL_ONE_TWO:
                line = ("approved", f"Allowed to {words}")
        elif st.kind == "forecast":
            step = "pilot"
            pct = c.get("confidence")
            ok = "can be sold" if c.get("eligible") else "is not eligible to run yet"
            line = ("forecast", f"Forecast ready: about {round(pct * 100)}% chance of reaching your target; this run {ok}"
                    if isinstance(pct, (int, float)) else "Forecast ready")
        elif st.kind == "settle_failed":
            line = ("payment", "Settling the payment hit a problem; it can be retried safely")
        elif st.kind == "limit":
            line = ("limit", "The assistant stopped at a safety limit")
        elif st.kind == "llm_error":
            line = ("problem", "The AI service had a problem")
        elif st.kind == "claim_blocked":
            line = ("guard", "Corrected a reply that claimed something that had not happened")
        elif st.kind == "tool_refused":
            line = ("blocked", "A step was refused because it was not allowed yet")
        if line and not duplicate(step, st.created_at):
            feed.append({"when": _utc(st.created_at), "kind": line[0], "text": line[1]})
    feed += [{"when": t, "kind": kind, "text": text} for t, _step, kind, text in stored]
    feed.sort(key=lambda f: f["when"])  # stable: equal times keep the order they were added in
    return feed
