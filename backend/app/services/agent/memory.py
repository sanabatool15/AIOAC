"""Conversation memory (specs/agent/10-memory-and-context-store.md).

Everything is stored as one row per message in `messages`. Each model step rebuilds its input from those rows:
base prompt, live state block (the source of truth for facts), an optional summary, then recent history inside a token
budget. Nothing is ever deleted; only what is SENT is limited.

Rules the builder keeps:
- an assistant message with tool calls always travels with all of its tool results (the API rejects a split pair);
- when over budget, old large tool results shrink to a one-line stub first, then the oldest groups are dropped;
- loaded skills are never shrunk; if their group has to be dropped, the playbook text moves into the system message;
- the newest user turn is always sent in full.

Not built: a summary of the oldest part. The `conversations.summary` column exists and is sent when set, but no code
writes it yet (dropped history is simply not sent; the state block still carries the facts).
"""
import json
from dataclasses import dataclass, field

from ...config import settings
from ...db import Session
from ...db.tables import Conversation, Message, Project
from ...ports import LLMResponse, ToolCall
from ...repositories import conversations, projects
from . import context

SKILL_LIMIT = 8000   # playbooks are kept nearly whole
STUB_PREFIX = "[old result, shortened] "


def estimate_tokens(text: str) -> int:
    return len(text) // 4 + 1


# ---------------------------------------------------------------- writing

def get_conversation(session: Session, project_id: str, source: str = "app", meta: dict | None = None,
                     conversation_id: str | None = None) -> Conversation:
    """The explicit conversation, else the project's newest active one, else a new one."""
    if conversation_id:
        conv = conversations.get(session, conversation_id)
        if conv is not None:
            return conv
    conv = conversations.newest_active(session, project_id)
    if conv is None:
        conv = conversations.create(session, project_id=project_id, source=source, meta=meta)
    return conv


def add_message(session: Session, conv_id: str, role: str, content: str = "", *, run_id: str | None = None,
                tool_calls: list | None = None, tool_call_id: str | None = None, tool_name: str | None = None,
                kind: str = "chat", stub: str | None = None) -> Message:
    """Append one message. seq is max+1; the unique (conversation, seq) key is the backstop if two writers ever race."""
    size = estimate_tokens(content) + (estimate_tokens(json.dumps(tool_calls)) if tool_calls else 0)
    for _ in range(5):
        m = conversations.append_message(session, conv_id, run_id=run_id, role=role, content=content, tool_calls=tool_calls,
                                         tool_call_id=tool_call_id, tool_name=tool_name, kind=kind, stub=stub, tokens=size)
        if m is not None:
            return m
    raise RuntimeError("could not assign a message number")


def stub_for(name: str, result) -> str:
    """One line that says what a big tool result contained, keeping ids and short numbers."""
    if not isinstance(result, dict):
        return f"{name}: {str(result)[:120]}"
    if "error" in result:
        return f"{name}: error, {str(result['error'])[:100]}"
    bits = []
    for k, v in result.items():
        if isinstance(v, list):
            bits.append(f"{len(v)} {k}")
        elif isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) <= 40):
            bits.append(f"{k}={v}")
        if len(bits) >= 6:
            break
    return f"{name}: ok" + (", " + ", ".join(bits) if bits else "")


# ---------------------------------------------------------------- reading

@dataclass
class Group:
    msgs: list[Message]
    sent: list[dict] = field(default_factory=list)
    stubbed: bool = False

    @property
    def is_user(self) -> bool:
        return self.msgs[0].role == "user"

    @property
    def has_skill(self) -> bool:
        return any(m.kind == "skill" for m in self.msgs)


def _tool_text(m: Message, stub: bool) -> str:
    if stub and m.kind != "skill":
        return STUB_PREFIX + (m.stub or m.content[:150])
    try:
        data = json.loads(m.content)
    except ValueError:
        return m.content
    return context.compact(data, SKILL_LIMIT if m.kind == "skill" else 2500)


def _render(group: Group, stub: bool) -> list[dict]:
    out = []
    answered = {m.tool_call_id: m for m in group.msgs if m.role == "tool"}
    for m in group.msgs:
        if m.role == "user":
            out.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            d = {"role": "assistant", "content": m.content}
            if m.tool_calls:
                d["tool_calls"] = m.tool_calls
            out.append(d)
    for c in (group.msgs[0].tool_calls or []) if group.msgs[0].role == "assistant" else []:
        m = answered.get(c["id"])
        text = _tool_text(m, stub) if m else json.dumps({"error": "no result was recorded for this call"})
        out.append({"role": "tool", "tool_call_id": c["id"], "content": text})
    return out


def _groups(msgs: list[Message]) -> list[Group]:
    groups: list[Group] = []
    i = 0
    while i < len(msgs):
        m = msgs[i]
        if m.role == "assistant" and m.tool_calls:
            ids = {c["id"] for c in m.tool_calls}
            grp = [m]
            i += 1
            while i < len(msgs) and msgs[i].role == "tool" and msgs[i].tool_call_id in ids:
                grp.append(msgs[i])
                i += 1
            groups.append(Group(grp))
        elif m.role == "tool":
            i += 1  # a result with no call in front of it cannot be sent; it stays in the database only
        else:
            groups.append(Group([m]))
            i += 1
    return groups


def _size(groups: list[Group]) -> int:
    return sum(estimate_tokens(json.dumps(g.sent, default=str)) for g in groups)


@dataclass
class Built:
    messages: list[dict]
    state_block: str
    history_messages: int
    stubbed: int = 0
    dropped_groups: int = 0


def pending_card(session: Session, conv: Conversation) -> dict | None:
    """The approval card the user has not answered yet: the newest message is a card result."""
    last = conversations.last_message(session, conv.id)
    if last is not None and last.kind == "card":
        try:
            return json.loads(last.content)
        except ValueError:
            return None
    return None


def history(session: Session, conv: Conversation, budget: int | None = None, upto_seq: int | None = None) -> tuple[list[dict], list[tuple[str, str]], int, int]:
    """(messages, skills moved to the system message, stubbed count, dropped group count)."""
    budget = budget if budget is not None else settings.agent_history_token_budget
    msgs = conversations.messages_after_summary(session, conv, upto_seq if upto_seq is not None else 10**12)
    groups = _groups(msgs)
    for g in groups:
        g.sent = _render(g, stub=False)
    # the newest user turn (from the last user message on) is protected
    last_user = max((i for i, g in enumerate(groups) if g.is_user), default=max(len(groups) - 1, 0))
    stubbed = dropped = 0
    if _size(groups) > budget:
        for g in groups[:last_user]:  # oldest first: shrink big old tool results
            if any(m.role == "tool" and m.kind != "skill" for m in g.msgs):
                g.sent, g.stubbed = _render(g, stub=True), True
                stubbed += 1
                if _size(groups) <= budget:
                    break
    skills: list[tuple[str, str]] = []
    if _size(groups) > budget:
        while last_user > 0 and _size(groups) > budget:
            g = groups.pop(0)
            last_user -= 1
            dropped += 1
            skills += [(m.tool_name or "skill", json.loads(m.content).get("playbook", "")) for m in g.msgs if m.kind == "skill"]
        while last_user > 0 and not groups[0].is_user:  # history must open on a user message
            g = groups.pop(0)
            last_user -= 1
            dropped += 1
            skills += [(m.tool_name or "skill", json.loads(m.content).get("playbook", "")) for m in g.msgs if m.kind == "skill"]
    out = [m for g in groups for m in g.sent]
    return out, skills, stubbed, dropped


def build(session: Session, project: Project, conv: Conversation, approved=(), budget: int | None = None) -> Built:
    """The full model input for one step."""
    msgs, skills, stubbed, dropped = history(session, conv, budget)
    extra = ""
    if conv.summary:
        extra += f"\n\nEarlier in this conversation (summary; the state above wins if they disagree):\n{conv.summary}"
    for name, body in skills:
        if body:
            extra += f"\n\nPlaybook '{name}' (loaded earlier, still applies):\n{body}"
    pend = pending_card(session, conv)
    state = context.state_block(session, project, approved=approved, pending=pend)
    system = {"role": "system", "content": context.build_system(session, project, approved=approved, pending=pend) + extra}
    return Built([system] + msgs, state, len(msgs), stubbed, dropped)


def model_input(session: Session, project: Project, conv: Conversation, approved=(), budget: int | None = None) -> list[dict]:
    return build(session, project, conv, approved, budget).messages


# ---------------------------------------------------------------- export, import, replay

def export_conversation(session: Session, conv: Conversation) -> dict:
    rows = conversations.all_messages(session, conv.id)
    return {"source": conv.source, "meta": conv.meta, "goal": projects.get(session, conv.project_id).goal if conv.project_id else None,
            "messages": [{"seq": m.seq, "run_id": m.run_id, "role": m.role, "content": m.content, "tool_calls": m.tool_calls,
                          "tool_call_id": m.tool_call_id, "tool_name": m.tool_name, "kind": m.kind, "stub": m.stub} for m in rows]}


def import_conversation(session: Session, project: Project, data: dict) -> Conversation:
    conv = conversations.create(session, project_id=project.id, source=data.get("source", "replay"), meta=data.get("meta"))
    for m in data["messages"]:
        add_message(session, conv.id, m["role"], m["content"], run_id=m.get("run_id"), tool_calls=m.get("tool_calls"),
                    tool_call_id=m.get("tool_call_id"), tool_name=m.get("tool_name"), kind=m.get("kind", "chat"), stub=m.get("stub"))
    return conv


class ReplayLLM:
    """Plays back the assistant messages of a stored conversation, so a run can be repeated without a model."""

    def __init__(self, data: dict):
        self.script = [m for m in data["messages"] if m["role"] == "assistant" and m.get("kind") != "note"]
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools):
        self.calls.append(messages)
        if not self.script:
            return LLMResponse(text="(replay finished)")
        m = self.script.pop(0)
        calls = [ToolCall(c["id"], c["function"]["name"], json.loads(c["function"]["arguments"])) for c in m["tool_calls"] or []]
        return LLMResponse(text=m["content"] or None, tool_calls=calls)
