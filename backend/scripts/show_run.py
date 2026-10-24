"""Print what the agent did, from the app database: python scripts/show_run.py <agent_run_id or project_id> [--db URL] [--tools]

Reads `agent_steps` (the audit log) and prints the same console format as the live log and `python -m evals.show`.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import build_engine  # noqa: E402
from app.models import AgentRun, AgentStep  # noqa: E402
from app.services.agent.runlog import format_line, redact, summarize_result  # noqa: E402

KIND_TO_TYPE = {"user": "user_message", "assistant": "assistant_reply", "llm": "llm_call", "llm_error": "llm_error",
                "tool_call": "tool_call", "tool_result": "tool_result", "gate": "gate", "claim_blocked": "guard", "limit": "limit",
                "approval_card": "approval_card", "tool_refused": "tool_refused"}


def step_to_event(st: AgentStep) -> dict:
    c = redact(st.content)
    e = {"ts": st.created_at.isoformat(timespec="milliseconds") if st.created_at else "", "level": "INFO", "turn": 0,
         "step": c.get("step") if isinstance(c, dict) else None, "type": KIND_TO_TYPE.get(st.kind, st.kind)}
    if st.kind in ("user", "assistant"):
        e["text"] = c["text"]
    elif st.kind == "llm":
        e.update(prompt_tokens=c.get("tokens"), completion_tokens=0, cost_usd=c.get("cost_usd"), ms=c.get("ms", 0), model="?")
    elif st.kind == "tool_result":
        ok, summary = summarize_result(st.content["result"])
        e.update(name=c["name"], ok=ok, summary=summary, ms=0)
    elif st.kind == "gate":
        e.update(action=c["action"], allowed=c["allowed"], reason=c.get("reason"), level="INFO" if c["allowed"] else "WARN")
    elif st.kind == "claim_blocked":
        e.update(guard="claim", detail="; ".join(c["problems"]), level="WARN")
    elif st.kind == "limit":
        e.update(reason=c["reason"], steps_used="?", tokens_used="?", level="WARN")
    else:
        e.update(**c) if isinstance(c, dict) else None
    return e


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("id", help="agent_run_id or project_id")
    ap.add_argument("--db", default=settings.database_url)
    ap.add_argument("--tools", action="store_true", help="only tool calls, gate decisions and results")
    a = ap.parse_args(argv)
    with sessionmaker(build_engine(a.db))() as s:
        run = s.get(AgentRun, a.id)
        q = select(AgentStep).order_by(AgentStep.seq)
        q = q.where(AgentStep.run_id == run.id, AgentStep.project_id == run.project_id) if run else q.where(AgentStep.project_id == a.id)
        steps = list(s.scalars(q))
        if not steps:
            print("nothing found for that id", file=sys.stderr)
            return 2
        for st in steps:
            e = step_to_event(st)
            if a.tools and e["type"] not in ("tool_call", "tool_result", "gate", "approval_card", "tool_refused"):
                continue
            print(format_line(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
