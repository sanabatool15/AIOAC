"""The agent loop (specs/agent.md section 2): an LLM proposes tool calls, the gate decides, the system executes."""
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from ...config import settings
from ...models import AgentRun, AgentStep
from ...providers.llm.base import LLMClient, LLMError
from ...repositories.traces import TraceRepository
from .. import gate
from . import context, guards
from .tools import TOOLS, ToolContext

REPEAT_LIMIT = 3  # the same call with the same arguments this many times in one turn means the model is going in circles

LIMIT_TEXT = {
    "steps": "I reached my step limit for this turn. Here is where things stand; tell me how to continue.",
    "tokens": "I have used up my thinking budget for this turn, so I am stopping here. Tell me how you would like to continue.",
    "project_tokens": "I have used up my thinking budget for this project, so I have stopped. A person needs to review before I continue.",
    "cost": "I have reached the spending limit for my own running costs on this project, so I have stopped. "
            "This is separate from your training price. A person needs to review before I continue.",
    "repeat": "I seemed to be going in circles, so I stopped. Tell me what you would like me to do next.",
    "timeout": "One of my checks took too long, so I stopped. Please try again in a moment.",
}


@dataclass
class AgentResult:
    status: str            # reply | awaiting_approval | limit | error
    text: str | None = None
    card: dict | None = None
    reason: str | None = None   # for limit: steps | tokens | project_tokens | cost | repeat | timeout


def _history(trace: TraceRepository, project_id: str) -> list[dict]:
    msgs = [{"role": st.kind, "content": st.content["text"]} for st in trace.steps(project_id, ("user", "assistant"))]
    return context.window(msgs)


def _project_usage(session, project_id: str, exclude_run: str) -> tuple[int, int]:
    q = select(func.coalesce(func.sum(AgentRun.tokens_used), 0), func.coalesce(func.sum(AgentRun.llm_cost_micros), 0)).where(
        AgentRun.project_id == project_id, AgentRun.id != exclude_run)
    tokens, micros = session.execute(q).one()
    return int(tokens), int(micros)


def _call_with_timeout(fn, timeout: float):
    """Run a free tool with a time limit. A tool that hangs is abandoned (threads cannot be killed) and the turn ends."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(fn).result(timeout=timeout)
    finally:
        pool.shutdown(wait=False)


def run_agent(ctx: ToolContext, llm: LLMClient, user_message: str | None) -> AgentResult:
    session = ctx.session
    run = AgentRun(project_id=ctx.project.id)
    session.add(run)
    session.commit()
    result: AgentResult | None = None
    try:
        result = _turn(ctx, llm, user_message, run)
        return result
    finally:
        run.status = result.status if result else "failed"
        run.stop_reason = result.reason if result else "crashed"
        run.ended_at = datetime.now(timezone.utc)
        # gate decisions are written by gate.py without a run id; stamp them so the whole turn shares one id
        session.execute(update(AgentStep).where(AgentStep.project_id == ctx.project.id, AgentStep.run_id.is_(None)).values(run_id=run.id))
        session.commit()


def _turn(ctx: ToolContext, llm: LLMClient, user_message: str | None, run: AgentRun) -> AgentResult:
    trace = TraceRepository(ctx.session)
    pid = ctx.project.id
    if user_message:
        trace.add(pid, "user", {"text": user_message}, run.id)
    convo = _history(trace, pid)
    seen: dict[str, int] = {}

    def stop(reason: str) -> AgentResult:
        trace.add(pid, "limit", {"reason": reason}, run.id)
        return AgentResult("limit", text=LIMIT_TEXT[reason], reason=reason)

    prior_tokens, prior_micros = _project_usage(ctx.session, pid, run.id)

    for _ in range(settings.agent_max_steps):
        # limits are checked before every model call, using usage the service reported
        if run.tokens_used >= settings.agent_max_tokens_per_turn:
            return stop("tokens")
        if prior_tokens + run.tokens_used >= settings.agent_max_tokens_per_project:
            return stop("project_tokens")
        if (prior_micros + run.llm_cost_micros) / 1e6 >= settings.agent_llm_cost_ceiling_usd:
            return stop("cost")

        # state and the offered tools are rebuilt every step: the project's status can change mid-turn
        system = {"role": "system", "content": context.build_system(ctx.session, ctx.project)}
        specs = [TOOLS[n].spec() for n in context.tool_names(ctx.project.status)]
        try:
            resp = llm.chat([system] + convo, specs)
        except LLMError as exc:
            trace.add(pid, "llm_error", {"message": str(exc)}, run.id)
            return AgentResult("error", text=f"I could not get an answer from my AI service just now. {exc}", reason="llm")
        run.steps_used += 1
        if resp.usage:
            run.tokens_used += resp.usage.total_tokens
            run.llm_cost_micros += int(round((resp.usage.cost_usd or 0.0) * 1e6))
            trace.add(pid, "llm", {"tokens": resp.usage.total_tokens, "cost_usd": resp.usage.cost_usd,
                                   "finish_reason": resp.finish_reason}, run.id)
        ctx.session.commit()

        if not resp.tool_calls:
            text = resp.text or ""
            problems = guards.false_claims(text, ctx.project.status)
            if problems:
                trace.add(pid, "claim_blocked", {"text": text, "problems": problems}, run.id)
                text = guards.correct_reply(text, ctx.project.status, problems)
            elif not text.strip():
                text = "I do not have anything to add yet. What would you like to do next?"
            trace.add(pid, "assistant", {"text": text}, run.id)
            return AgentResult("reply", text=text)

        convo.append({"role": "assistant", "content": resp.text or "", "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.args)}}
            for c in resp.tool_calls]})
        for call in resp.tool_calls:
            sig = f"{call.name}:{json.dumps(call.args, sort_keys=True, default=str)}"
            seen[sig] = seen.get(sig, 0) + 1
            if seen[sig] > REPEAT_LIMIT:
                return stop("repeat")
            tool = TOOLS.get(call.name)
            trace.add(pid, "tool_call", {"name": call.name, "args": call.args}, run.id)
            offered = context.tool_names(ctx.project.status)
            if call.error:
                result = {"error": f"I could not read the arguments for {call.name or 'the call'}: {call.error}. Send a JSON object."}
            elif tool is None:
                result = {"error": f"unknown tool {call.name}", "available": offered}
            elif call.name not in offered:
                result = {"error": f"{call.name} is not available at this step ({ctx.project.status})", "available": offered}
            elif (problem := guards.check_args(tool.parameters, call.args)):
                result = {"error": f"bad arguments for {call.name}: {problem}"}
            else:
                try:
                    gate.authorize(ctx.session, ctx.project, tool.action, user_approved=tool.action.value in ctx.approved)
                    if gate.LEVEL[tool.action] == 0 and settings.agent_tool_timeout_s > 0:
                        result = _call_with_timeout(lambda: tool.fn(ctx, call.args), settings.agent_tool_timeout_s)
                    else:
                        result = tool.fn(ctx, call.args)
                except gate.NeedsApproval as need:
                    card = {**need.card, "tool": call.name, "args": call.args}
                    return AgentResult("awaiting_approval", card=card)
                except gate.GateDenied as denied:
                    result = {"error": f"not allowed: {denied}"}
                except FutureTimeout:
                    trace.add(pid, "tool_result", {"name": call.name, "result": {"error": "timed out"}}, run.id)
                    return stop("timeout")
                except Exception as exc:  # tool failed: tell the model, which tells the user in plain words
                    ctx.session.rollback()
                    result = {"error": f"{type(exc).__name__}: {exc}"}
            trace.add(pid, "tool_result", {"name": call.name, "result": result}, run.id)
            convo.append({"role": "tool", "tool_call_id": call.id, "content": context.compact(result)})
    return stop("steps")
