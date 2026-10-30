"""The agent loop (specs/agent.md section 2): an LLM proposes tool calls, the gate decides, the system executes."""
import hashlib
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import datetime, timezone

from ...config import settings
from ...db.tables import AgentRun
from ...ports import LLMClient, LLMError
from ...repositories import agent_runs, transactions
from ...repositories.traces import TraceRepository
from .. import gate
from . import context, guards, memory
from .runlog import RunLog, summarize_result
from .tools import TOOLS, ToolContext

GENERIC_TOOL_ERROR = "That tool failed unexpectedly. Do not retry the same call; tell the user plainly that this step could not be done right now."
logger = logging.getLogger("aioac.agent")

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


def _project_usage(session, project_id: str, exclude_run: str) -> tuple[int, int]:
    return agent_runs.project_usage(session, project_id, exclude_run)


def _call_with_timeout(fn, timeout: float):
    """Run a free tool with a time limit. A tool that hangs is abandoned (threads cannot be killed) and the turn ends."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(fn).result(timeout=timeout)
    finally:
        pool.shutdown(wait=False)


class TurnInProgress(Exception):
    """A second turn for the same project started while one is still running."""


_active: set[str] = set()
_active_lock = threading.Lock()


def _acquire(project_id: str) -> None:
    with _active_lock:
        if project_id in _active:
            raise TurnInProgress("The assistant is still working on your last message. Please wait a moment.")
        _active.add(project_id)


def _release(project_id: str) -> None:
    with _active_lock:
        _active.discard(project_id)


def run_agent(ctx: ToolContext, llm: LLMClient, user_message: str | None, log: RunLog | None = None,
              conversation_id: str | None = None, source: str = "app", meta: dict | None = None) -> AgentResult:
    """One user turn. Only one turn per project can run at a time (TurnInProgress otherwise, mapped to HTTP 409)."""
    log = log or RunLog()  # no sinks: does nothing
    session = ctx.session
    _acquire(ctx.project.id)
    try:
        conv = memory.get_conversation(session, ctx.project.id, source, meta, conversation_id)
        run = agent_runs.create(session, ctx.project.id, conv.id)
        log.begin_turn(ctx.project.id, run.id)
        t0 = time.monotonic()
        status_before = ctx.project.status
        log.emit("turn_start", status_before=status_before, message_chars=len(user_message or ""), approved=sorted(ctx.approved),
                 model=getattr(llm, "model", type(llm).__name__), conversation_id=conv.id)
        result: AgentResult | None = None
        try:
            result = _turn(ctx, llm, user_message, run, conv, log)
            return result
        finally:
            run.status = result.status if result else "failed"
            run.stop_reason = result.reason if result else "crashed"
            run.ended_at = datetime.now(timezone.utc)
            # gate decisions are written by gate.py without a run id; stamp them so the whole turn shares one id
            agent_runs.stamp_unowned_steps(session, ctx.project.id, run.id)
            log.emit("turn_end", "INFO" if result else "ERROR", status=run.status, reason=run.stop_reason, steps_used=run.steps_used,
                     tokens_used=run.tokens_used, cost_usd=run.llm_cost_micros / 1e6, status_after=ctx.project.status,
                     ms=int((time.monotonic() - t0) * 1000))
    finally:
        _release(ctx.project.id)


def _turn(ctx: ToolContext, llm: LLMClient, user_message: str | None, run: AgentRun, conv, log: RunLog) -> AgentResult:
    trace = TraceRepository(ctx.session)
    pid = ctx.project.id
    ctx.log = log  # lets tools write their own events to the same run log
    if not user_message and ctx.approved:
        # The user pressed "approve" on a card and typed nothing. Without a user turn, models read the stored
        # "waiting for approval" result as still waiting and ask again. The gate trusts ctx.approved, not this text.
        user_message = f"Yes, I approve: {', '.join(a.replace('_', ' ') for a in sorted(ctx.approved))}. Please carry it out."
    if user_message:
        trace.add(pid, "user", {"text": user_message}, run.id)
        memory.add_message(ctx.session, conv.id, "user", user_message, run_id=run.id)
        log.emit("user_message", text=user_message)
    seen: dict[str, int] = {}

    def say(text: str, kind: str = "chat") -> None:
        memory.add_message(ctx.session, conv.id, "assistant", text, run_id=run.id, kind=kind)

    def stop(reason: str) -> AgentResult:
        trace.add(pid, "limit", {"reason": reason}, run.id)
        log.emit("limit", "WARN", reason=reason, steps_used=run.steps_used, tokens_used=run.tokens_used, cost_usd=run.llm_cost_micros / 1e6)
        say(LIMIT_TEXT[reason], "note")
        return AgentResult("limit", text=LIMIT_TEXT[reason], reason=reason)

    prior_tokens, prior_micros = _project_usage(ctx.session, pid, run.id)

    for step in range(1, settings.agent_max_steps + 1):
        log.step = step
        # limits are checked before every model call, using usage the service reported
        if run.tokens_used >= settings.agent_max_tokens_per_turn:
            return stop("tokens")
        if prior_tokens + run.tokens_used >= settings.agent_max_tokens_per_project:
            return stop("project_tokens")
        if (prior_micros + run.llm_cost_micros) / 1e6 >= settings.agent_llm_cost_ceiling_usd:
            return stop("cost")

        # state, history and the offered tools are rebuilt every step: the project's status can change mid-turn
        built = memory.build(ctx.session, ctx.project, conv, ctx.approved)
        offered = context.tool_names(ctx.project.status)
        specs = [TOOLS[n].spec() for n in offered]
        if log.active:
            prompt_hash = hashlib.sha256(json.dumps(built.messages, sort_keys=True, default=str).encode()).hexdigest()
            log.emit("context", "DEBUG", state_block=built.state_block, tools_offered=offered, history_messages=built.history_messages,
                     stubbed_results=built.stubbed, dropped_groups=built.dropped_groups, prompt_sha256=prompt_hash)
            if log.log_prompts:
                log.emit("prompt", "DEBUG", messages=built.messages)
        t_llm = time.monotonic()
        try:
            resp = llm.chat(built.messages, specs)
        except LLMError as exc:
            trace.add(pid, "llm_error", {"message": str(exc)}, run.id)
            log.emit("llm_error", "ERROR", message=str(exc), retryable=bool(getattr(exc, "retryable", False)))
            text = f"I could not get an answer from my AI service just now. {exc}"
            say(text, "note")
            return AgentResult("error", text=text, reason="llm")
        ms = int((time.monotonic() - t_llm) * 1000)
        run.steps_used += 1
        usage = resp.usage
        if usage:
            run.tokens_used += usage.total_tokens
            run.llm_cost_micros += int(round((usage.cost_usd or 0.0) * 1e6))
            trace.add(pid, "llm", {"tokens": usage.total_tokens, "cost_usd": usage.cost_usd, "finish_reason": resp.finish_reason,
                                   "step": step, "ms": ms}, run.id)
        transactions.commit(ctx.session)
        log.emit("llm_call", model=getattr(llm, "model", type(llm).__name__), ms=ms, prompt_tokens=usage.prompt_tokens if usage else None,
                 completion_tokens=usage.completion_tokens if usage else None, cost_usd=usage.cost_usd if usage else None,
                 finish_reason=resp.finish_reason, text=resp.text,
                 tool_calls=[{"id": c.id, "name": c.name, "args": c.args} for c in resp.tool_calls])

        if not resp.tool_calls:
            text = resp.text or ""
            problems = guards.false_claims(text, ctx.project.status)
            corrected = bool(problems)
            if problems:
                trace.add(pid, "claim_blocked", {"text": text, "problems": problems}, run.id)
                log.emit("guard", "WARN", guard="claim", detail="; ".join(problems), original_text=text)
                text = guards.correct_reply(text, ctx.project.status, problems)
            elif not text.strip():
                text = "I do not have anything to add yet. What would you like to do next?"
            trace.add(pid, "assistant", {"text": text}, run.id)
            say(text)
            log.emit("assistant_reply", text=text, corrected=corrected)
            return AgentResult("reply", text=text)

        calls_json = [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.args, default=str)}}
                      for c in resp.tool_calls]
        memory.add_message(ctx.session, conv.id, "assistant", resp.text or "", run_id=run.id, tool_calls=calls_json)
        unanswered = [c.id for c in resp.tool_calls]

        def close_group(note: str) -> None:
            """Every call needs a result in the stored history, or the next request would be rejected."""
            for cid in unanswered:
                name = next((c.name for c in resp.tool_calls if c.id == cid), None)
                memory.add_message(ctx.session, conv.id, "tool", json.dumps({"not_run": note}), run_id=run.id, tool_call_id=cid,
                                   tool_name=name, kind="note", stub=f"{name}: not run, {note}")
            unanswered.clear()

        for call in resp.tool_calls:
            sig = f"{call.name}:{json.dumps(call.args, sort_keys=True, default=str)}"
            seen[sig] = seen.get(sig, 0) + 1
            if seen[sig] > REPEAT_LIMIT:
                close_group("the turn was stopped")
                return stop("repeat")
            tool = TOOLS.get(call.name)
            trace.add(pid, "tool_call", {"name": call.name, "args": call.args}, run.id)
            log.emit("tool_call", call_id=call.id, name=call.name, args=call.args)
            offered = context.tool_names(ctx.project.status)
            t_tool = time.monotonic()
            detail = None  # full exception text: goes to the log only, never to the model or the stored trace
            refused = None
            if call.error:
                refused = ("unreadable_args", call.error)
                result = {"error": f"I could not read the arguments for {call.name or 'the call'}: {call.error}. Send a JSON object."}
            elif tool is None:
                refused = ("unknown_tool", call.name)
                result = {"error": f"unknown tool {call.name}", "available": offered}
            elif call.name not in offered:
                refused = ("not_offered", ctx.project.status)
                result = {"error": f"{call.name} is not available at this step ({ctx.project.status})", "available": offered}
            elif (problem := guards.check_args(tool.parameters, call.args)):
                refused = ("bad_args", problem)
                result = {"error": f"bad arguments for {call.name}: {problem}"}
            else:
                level_num = gate.LEVEL[tool.action]
                try:
                    gate.authorize(ctx.session, ctx.project, tool.action, user_approved=tool.action.value in ctx.approved)
                    log.emit("gate", action=tool.action.value, level_num=level_num, allowed=True, reason=None)
                    t_tool = time.monotonic()
                    if level_num == 0 and settings.agent_tool_timeout_s > 0:
                        result = _call_with_timeout(lambda: tool.fn(ctx, call.args), settings.agent_tool_timeout_s)
                    else:
                        result = tool.fn(ctx, call.args)
                except gate.NeedsApproval as need:
                    card = {**need.card, "tool": call.name, "args": call.args}
                    log.emit("gate", "WARN", action=tool.action.value, level_num=level_num, allowed=False, reason="needs user approval")
                    log.emit("approval_card", "WARN", tool=call.name, args=call.args, what=need.card.get("what"))
                    memory.add_message(ctx.session, conv.id, "tool", json.dumps({"waiting_for_user": "approval", **card}, default=str),
                                       run_id=run.id, tool_call_id=call.id, tool_name=call.name, kind="card",
                                       stub=f"{call.name}: waiting for the user to approve")
                    unanswered.remove(call.id)
                    close_group("waiting for the user to approve an earlier call")
                    return AgentResult("awaiting_approval", card=card)
                except gate.GateDenied as denied:
                    log.emit("gate", "WARN", action=tool.action.value, level_num=level_num, allowed=False, reason=str(denied))
                    result = {"error": f"not allowed: {denied}"}
                except FutureTimeout:
                    result = {"error": "timed out"}
                    trace.add(pid, "tool_result", {"name": call.name, "result": result}, run.id)
                    log.emit("tool_result", "ERROR", call_id=call.id, name=call.name, ms=int((time.monotonic() - t_tool) * 1000), ok=False,
                             summary="timed out", result=result)
                    close_group("the check took too long")
                    return stop("timeout")
                except Exception as exc:  # tool failed: the model gets a generic message; the detail stays in the log
                    transactions.rollback(ctx.session)
                    detail = f"{type(exc).__name__}: {exc}"
                    logger.warning("tool %s failed: %s", call.name, detail, exc_info=True)
                    result = {"error": GENERIC_TOOL_ERROR}
            if refused:
                log.emit("tool_refused", "WARN", call_id=call.id, name=call.name, why=refused[0], detail=str(refused[1])[:200])
            trace.add(pid, "tool_result", {"name": call.name, "result": result}, run.id)
            ok, summary = summarize_result(result)
            log.emit("tool_result", "INFO" if ok else "WARN", call_id=call.id, name=call.name,
                     ms=int((time.monotonic() - t_tool) * 1000), ok=ok, summary=summary, result=result,
                     **({"error_detail": detail} if detail else {}))
            is_skill = call.name == "load_skill" and isinstance(result, dict) and "playbook" in result
            memory.add_message(ctx.session, conv.id, "tool", json.dumps(result, default=str), run_id=run.id, tool_call_id=call.id,
                               tool_name=call.name, kind="skill" if is_skill else "chat", stub=memory.stub_for(call.name, result))
            unanswered.remove(call.id)
    return stop("steps")
