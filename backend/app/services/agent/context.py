"""Context engineering (specs/agent.md): small prompt, live state, trimmed results, windowed history, status-based tools."""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import DatasetCandidate, DatasetVersion, Project
from .. import gate
from . import skills

BASE = (
    "You are AI on a Click. You help a non-technical user turn a plain-language goal into a trained prediction model.\n"
    "Rules:\n"
    "- Plain words only. No jargon. One short question at a time.\n"
    "- Numbers come from tools. Never invent or round them.\n"
    "- Never promise accuracy. Every price is an ESTIMATE.\n"
    "- You cannot spend money or start paid work yourself; the user approves and pays, and the server checks.\n"
    "- Load a skill with load_skill before doing something it covers.\n"
)

NEXT_STEP = {
    "described": "Find or receive a dataset, inspect it, and ask the user to approve one.",
    "data_chosen": "Run the readiness check.",
    "readiness_done": "Run the free baseline test.",
    "baseline_done": "Create the quote and explain estimate, range, cap and refund.",
    "quoted": "Wait for the user to approve the quote on screen.",
    "awaiting_payment": "Request the payment, then wait for the user to pay.",
    "paid": "Start training.",
    "training": "Training is running. Report progress in plain words.",
    "done": "Help the user use the result.",
}

TOOLS_BY_STATUS = {
    "described": ["load_skill", "search_datasets", "look_at_dataset", "fetch_dataset", "inspect_candidate", "select_dataset"],
    "data_chosen": ["load_skill", "run_readiness"],
    "readiness_done": ["load_skill", "run_baseline"],
    "baseline_done": ["load_skill", "create_quote"],
    "quoted": ["load_skill", "create_quote"],
    "awaiting_payment": ["load_skill", "request_payment"],
    "paid": ["load_skill", "start_training"],
}
DEFAULT_TOOLS = ["load_skill"]


def tool_names(status: str) -> list[str]:
    return TOOLS_BY_STATUS.get(status, DEFAULT_TOOLS)


def state_block(session: Session, project: Project) -> str:
    lines = [f"Goal: {project.goal}", f"Status: {project.status}"]
    if project.chosen_dataset_version_id:
        v = session.get(DatasetVersion, project.chosen_dataset_version_id)
        lines.append(f"Dataset: {v.source}, {v.rows:,} rows, answer column '{v.target_column}', license {v.license or 'not stated'}")
    else:
        # tool results are not kept between turns, so the model needs the candidate ids here (e.g. to propose select_dataset again after approval)
        cands = session.scalars(select(DatasetCandidate).where(DatasetCandidate.project_id == project.id, DatasetCandidate.status == "candidate")).all()
        for c in cands[:5]:
            lines.append(f"Fetched candidate: id {c.id}, {c.name}, {c.rows or '?'} rows, license {c.license or 'not stated'}")
    if project.readiness_grade:
        lines.append(f"Readiness grade: {project.readiness_grade}")
    if project.baseline_result:
        b = project.baseline_result
        lines.append(f"Free test: {b['accuracy']:.2f} right vs {b['simple_guess_accuracy']:.2f} for a simple guess; trust {project.trust_level}")
    q = gate.latest_quote(session, project.id)
    if q:
        lines.append(f"Quote (estimate): {q.estimate_cents}c, range {q.low_cents}-{q.high_cents}c, cap {q.cap_cents}c, "
                     f"{'approved' if q.approved_at else 'not approved yet'}")
    lines.append(f"Next: {NEXT_STEP.get(project.status, 'Reply helpfully.')}")
    return "\n".join(lines)


def build_system(session: Session, project: Project) -> str:
    return f"{BASE}\nCurrent state:\n{state_block(session, project)}\n\nSkills (use load_skill):\n{skills.index()}"


def compact(result, limit: int = 2500) -> str:
    """Keep tool results small: trim long lists first, then cut the text."""
    text = json.dumps(result, default=str)
    if len(text) <= limit:
        return text
    if isinstance(result, dict):
        trimmed = {k: (v[:5] if isinstance(v, list) else v) for k, v in result.items()}
        trimmed["_trimmed"] = "long lists were cut to 5 items"
        text = json.dumps(trimmed, default=str)
        if len(text) <= limit:
            return text
    return text[:limit] + '..."[cut]'


def window(history: list[dict], keep: int = 20) -> list[dict]:
    """Last `keep` messages, starting on a user turn. State lives in the system prompt, so old turns can go."""
    h = history[-keep:]
    while h and h[0]["role"] != "user":
        h = h[1:]
    return h
