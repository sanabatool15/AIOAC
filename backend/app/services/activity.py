"""A plain-language feed of what the assistant did, built by code from the stored trace (never by the model).

Raw tool JSON, dataset rows, error text and secrets are never copied into the feed: each line is a fixed sentence with
a few safe values (a dataset name, a row count, a grade). User text is scrubbed and cut.
"""
from ..db import Session
from ..db.tables import Project
from ..repositories.traces import TraceRepository
from .agent.runlog import scrub

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
    if result.get("need_clarity"):
        return "question", "Asked what you want to predict before searching"
    if name in ("search_datasets", "discover_datasets"):
        q = args.get("queries") or args.get("query") or args.get("goal_summary") or ""
        q = ", ".join(_s(x, 40) for x in q[:3]) if isinstance(q, list) else _s(q)
        return "search", f"Searched open datasets for {q}" if q else "Searched open datasets"
    if name == "look_at_dataset":
        label = _s(result.get("name") or args.get("dataset_id") or "a dataset", 60)
        return "look", f'Looked at "{label}" ({_rows(result.get("rows"))})'
    if name == "fetch_dataset":
        return "download", f"Downloaded a dataset ({_rows(result.get('rows'))})"
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


def activity(session: Session, project: Project) -> list[dict]:
    feed: list[dict] = []
    last_args: dict[str, dict] = {}
    for st in TraceRepository(session).steps(project.id):
        c = st.content if isinstance(st.content, dict) else {}
        line: tuple[str, str] | None = None
        if st.kind == "user":
            line = ("you", f'You said: "{_s(c.get("text", ""), 100)}"')
        elif st.kind == "assistant":
            line = ("reply", "The assistant replied")
        elif st.kind == "tool_call":
            last_args[c.get("name", "")] = c.get("args") if isinstance(c.get("args"), dict) else {}
        elif st.kind == "tool_result":
            name = c.get("name", "")
            line = _tool_line(name, last_args.pop(name, {}), c.get("result"))
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
        if line:
            feed.append({"when": st.created_at, "kind": line[0], "text": line[1]})
    return feed
