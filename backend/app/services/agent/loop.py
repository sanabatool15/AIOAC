"""The agent loop (specs/agent.md section 2): an LLM proposes tool calls, the gate decides, the system executes."""
import json
from dataclasses import dataclass

from ...config import settings
from ...providers.llm.base import LLMClient
from ...repositories.traces import TraceRepository
from .. import gate
from .tools import TOOLS, ToolContext

SYSTEM = (
    "You are AI on a Click. Help the user turn a plain-language goal into a trained prediction model. "
    "Use plain words only: no technical jargon. Ask at most one short question at a time. "
    "Never promise accuracy: report a readiness grade, the free test result, and cost as an ESTIMATE. "
    "You cannot spend money; the user approves quotes and pays. Use the tools; do not invent numbers."
)


@dataclass
class AgentResult:
    status: str            # reply | awaiting_approval | limit
    text: str | None = None
    card: dict | None = None


def _history(trace: TraceRepository, project_id: str) -> list[dict]:
    out = [{"role": "system", "content": SYSTEM}]
    for s in trace.steps(project_id, ("user", "assistant")):
        out.append({"role": s.kind, "content": s.content["text"]})
    return out


def run_agent(ctx: ToolContext, llm: LLMClient, user_message: str | None) -> AgentResult:
    trace = TraceRepository(ctx.session)
    pid = ctx.project.id
    if user_message:
        trace.add(pid, "user", {"text": user_message})
    msgs = _history(trace, pid)
    specs = [t.spec() for t in TOOLS.values()]

    for _ in range(settings.agent_max_steps):
        resp = llm.chat(msgs, specs)
        if not resp.tool_calls:
            trace.add(pid, "assistant", {"text": resp.text or ""})
            return AgentResult("reply", text=resp.text)
        msgs.append({"role": "assistant", "content": resp.text or "", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.args)}}
            for c in resp.tool_calls]})
        for call in resp.tool_calls:
            tool = TOOLS.get(call.name)
            trace.add(pid, "tool_call", {"name": call.name, "args": call.args})
            if tool is None:
                result = {"error": f"unknown tool {call.name}"}
            else:
                try:
                    gate.authorize(ctx.session, ctx.project, tool.action, user_approved=tool.action.value in ctx.approved)
                    result = tool.fn(ctx, call.args)
                except gate.NeedsApproval as need:
                    card = {**need.card, "tool": call.name, "args": call.args}
                    return AgentResult("awaiting_approval", card=card)
                except gate.GateDenied as denied:
                    result = {"error": f"not allowed: {denied}"}
                except Exception as exc:  # tool failed: tell the model, which tells the user in plain words
                    result = {"error": f"{type(exc).__name__}: {exc}"}
            trace.add(pid, "tool_result", {"name": call.name, "result": result})
            msgs.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, default=str)})
    return AgentResult("limit", text="I reached my step limit for this turn. Here is where things stand; tell me how to continue.")
