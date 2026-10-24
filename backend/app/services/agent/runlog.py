"""Run log (specs/agent/06-observability-and-logging.md): one event stream, several readable views.

The loop calls `log.emit(type, level, **fields)` at the points where it already writes trace steps. Sinks turn events into
console lines, JSON Lines, a Markdown transcript or `agent_steps` rows. Logging must never break a turn: every redaction
and every sink call is wrapped, and a failure drops the event.

Redaction (section 9): secrets are scrubbed from every string, dataset rows are cut to 3 rows of 40 characters, prompts are
logged only as a hash plus the state block (full prompts only with `log_prompts`), and user text can be replaced by its
length and hash with LOG_USER_TEXT=false.
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

SCHEMA_VERSION = 1
LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}

# ---------------------------------------------------------------- redaction

_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "[redacted key]"),
    (re.compile(r"Bearer\s+\S+", re.I), "Bearer [redacted]"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{20,}"), "[redacted token]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[redacted aws key]"),
    (re.compile(r"(?<![\w.])\d{13,19}(?![\w.])"), "[redacted number]"),
    (re.compile(r"""(api[_-]?key|secret|password|passwd)(["']?\s*[:=]\s*["']?)[^\s"',}]{6,}""", re.I), r"\1\2[redacted]"),
]
ROW_KEYS = {"preview", "rows", "sample_rows", "records"}
MAX_ROWS, MAX_CELL, MAX_STRING, MAX_RESULT_CHARS = 3, 40, 2000, 2000


def _secret_values() -> list[str]:
    try:
        from ...config import settings
        vals = [settings.openrouter_api_key, settings.paypal_client_secret, settings.hf_token, settings.inngest_event_key,
                settings.inngest_signing_key]
        return [v for v in vals if v and len(v) >= 8]
    except Exception:
        return []


def scrub(text: str) -> str:
    for secret in _secret_values():
        text = text.replace(secret, "[redacted]")
    for rx, repl in _SECRET_PATTERNS:
        text = rx.sub(repl, text)
    return text


def _cut(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n] + "..."


def redact(value, key: str | None = None):
    """Return a copy that is safe to write to a log: secrets scrubbed, long strings cut, dataset rows capped."""
    if isinstance(value, str):
        return _cut(scrub(value), MAX_STRING)
    if isinstance(value, dict):
        if "untrusted_dataset_text" in value:  # a marked block: look inside it, keeping the parent key for the row rule
            inner = redact(value["untrusted_dataset_text"], key)
            return {**{k: redact(v) for k, v in value.items() if k != "untrusted_dataset_text"}, "untrusted_dataset_text": inner}
        out = {}
        for k, v in value.items():
            out[str(k)] = redact(v, str(k))
            if isinstance(v, list) and str(k) in ROW_KEYS and len(v) > MAX_ROWS:
                out["rows_truncated"] = True
        return out
    if isinstance(value, (list, tuple)):
        if key in ROW_KEYS:
            rows = list(value)[:MAX_ROWS]
            return [{str(c): _cut(scrub(str(x)), MAX_CELL) if isinstance(x, str) else redact(x) for c, x in r.items()}
                    if isinstance(r, dict) else redact(r) for r in rows]
        return [redact(v) for v in value]
    return value


def _result_for_log(result):
    r = redact(result)
    text = json.dumps(r, default=str)
    return r if len(text) <= MAX_RESULT_CHARS else text[:MAX_RESULT_CHARS] + "...[cut]"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------- console format

_LABEL = {"turn_start": "START", "user_message": "USER", "context": "CTX", "llm_call": "MODEL", "llm_error": "LLMERR",
          "tool_call": "CALL", "tool_refused": "REFUSE", "gate": "GATE", "approval_card": "CARD", "tool_result": "TOOL",
          "guard": "GUARD", "limit": "LIMIT", "assistant_reply": "REPLY", "turn_end": "END", "run_end": "RUNEND",
          "prompt": "PROMPT", "log_error": "LOGERR"}


def _call_text(name: str, args) -> str:
    if isinstance(args, dict):
        inner = ", ".join(f"{k}={json.dumps(v, default=str)}" for k, v in args.items())
    else:
        inner = str(args)
    return f"{name}({_cut(inner, 90)})"


def format_line(e: dict) -> str:
    """One fixed-column line per event, readable live and easy to grep."""
    t, ts = e.get("type", "?"), e.get("ts", "")
    clock = ts[11:21] if len(ts) >= 21 else ts
    where = f"t{e.get('turn', 0)}" + (f".s{e['step']}" if e.get("step") else "")
    if t == "llm_call":
        calls = ", ".join(_call_text(c["name"], c.get("args")) for c in e.get("tool_calls") or [])
        cost = f"${e['cost_usd']:.4f}" if e.get("cost_usd") is not None else "$?"
        detail = (f"{e.get('model', '?')}  {e.get('prompt_tokens') or 0:,} in / {e.get('completion_tokens') or 0:,} out  {cost}  "
                  f"{e.get('ms', 0) / 1000:.1f}s  -> " + (calls or repr(_cut(e.get("text") or "", 100))))
    elif t == "tool_call":
        detail = _call_text(e.get("name", "?"), e.get("args"))
    elif t == "tool_result":
        detail = f"{e.get('name', '?'):<16} {'ok' if e.get('ok') else 'ERROR'}  {e.get('summary', '')}  {e.get('ms', 0)} ms"
    elif t == "tool_refused":
        detail = f"{e.get('name', '?'):<16} {e.get('why')}: {_cut(str(e.get('detail', '')), 100)}"
    elif t == "gate":
        detail = f"{e.get('action', '?'):<16} {'allowed' if e.get('allowed') else 'refused: ' + str(e.get('reason', ''))}"
    elif t == "approval_card":
        detail = _call_text(e.get("tool", "?"), e.get("args")) + f"  {e.get('what', '')}"
    elif t == "turn_start":
        detail = f"status={e.get('status_before')} message_chars={e.get('message_chars')} approved={e.get('approved')} model={e.get('model')}"
    elif t == "turn_end":
        cost = f"${e['cost_usd']:.4f}" if e.get("cost_usd") is not None else "$?"
        detail = (f"status={e.get('status')}" + (f" reason={e['reason']}" if e.get("reason") else "") +
                  f" tokens {e.get('tokens_used') or 0:,}  {cost}  project now {e.get('status_after')}")
    elif t in ("user_message", "assistant_reply"):
        detail = repr(_cut(str(e.get("text", e.get("text_sha256", ""))), 120))
    elif t == "guard":
        detail = f"{e.get('guard')}  {_cut(str(e.get('detail', '')), 120)}"
    elif t == "limit":
        detail = f"{e.get('reason')}  steps {e.get('steps_used')}, tokens {e.get('tokens_used')}"
    elif t == "llm_error":
        detail = _cut(str(e.get("message", "")), 140)
    elif t == "context":
        detail = f"{len(e.get('tools_offered', []))} tools, {e.get('history_messages')} history messages, prompt {str(e.get('prompt_sha256'))[:10]}"
    else:
        detail = _cut(json.dumps({k: v for k, v in e.items() if k not in ("v", "ts", "n", "log_id", "project_id", "agent_run_id", "turn", "step", "level", "type")},
                                 default=str), 160)
    return f"{clock} {e.get('level', 'INFO'):<5} {where:<6} {_LABEL.get(t, t.upper()):<6} {detail}"


# ---------------------------------------------------------------- transcript

def render_markdown(events: list[dict], header: str | None = None) -> str:
    """A transcript a person can read with no code open: per turn, the user text, then each step."""
    out = [header or f"# Run {events[0]['log_id'] if events else ''}", ""]
    for e in events:
        t = e["type"]
        if t == "turn_start":
            out += [f"## Turn {e['turn']}  (project status: {e.get('status_before')})", ""]
        elif t == "user_message":
            out += [f"**User:** {e.get('text', '(text not logged)')}", ""]
        elif t == "context":
            out += ["**State at this step**", "", *["    " + ln for ln in str(e.get("state_block", "")).splitlines()], ""]
        elif t == "llm_call":
            cost = f"${e['cost_usd']:.4f}" if e.get("cost_usd") is not None else "cost unknown"
            out += [f"**Step {e.get('step')}** model ({e.get('model')}): {e.get('prompt_tokens') or 0:,} in, "
                    f"{e.get('completion_tokens') or 0:,} out, {cost}, {e.get('ms', 0)} ms"]
            if e.get("text"):
                out += [f"- said: {e['text']}"]
            for c in e.get("tool_calls") or []:
                out += [f"- asked for `{_call_text(c['name'], c.get('args'))}`"]
        elif t == "gate":
            out += [f"  - gate: {e.get('action')} -> {'allowed' if e.get('allowed') else 'refused (' + str(e.get('reason')) + ')'}"]
        elif t == "tool_refused":
            out += [f"  - refused `{e.get('name')}`: {e.get('why')} ({e.get('detail')})"]
        elif t == "approval_card":
            out += [f"  - approval card: {e.get('what')} -> `{_call_text(e.get('tool', '?'), e.get('args'))}`"]
        elif t == "tool_result":
            out += [f"  - `{e.get('name')}` {'ok' if e.get('ok') else 'ERROR'} ({e.get('ms')} ms): {e.get('summary')}"]
        elif t == "guard":
            out += [f"  - guard {e.get('guard')}: {e.get('detail')}"]
        elif t == "limit":
            out += [f"  - LIMIT: {e.get('reason')}"]
        elif t == "llm_error":
            out += [f"  - MODEL ERROR: {e.get('message')}"]
        elif t == "assistant_reply":
            out += ["", f"**Agent:** {e.get('text')}", ""]
        elif t == "turn_end":
            out += ["", f"_Turn ended: {e.get('status')}{' (' + e['reason'] + ')' if e.get('reason') else ''}; tokens {e.get('tokens_used') or 0:,}; "
                        f"project is now `{e.get('status_after')}`_", ""]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- sinks

class Sink(Protocol):
    def write(self, event: dict) -> None: ...
    def close(self) -> None: ...


class ConsoleSink:
    def __init__(self, stream=None, level: str = "INFO", show_calls: bool = False):
        self.stream, self.min, self.show_calls = stream, LEVELS[level], show_calls

    def write(self, event: dict) -> None:
        if LEVELS.get(event["level"], 20) < self.min:
            return
        if event["type"] == "tool_call" and not self.show_calls and self.min > LEVELS["DEBUG"]:
            return  # the MODEL line already shows the call
        if event["type"] == "prompt":
            return
        print(format_line(event), file=self.stream or sys.stdout, flush=True)

    def close(self) -> None:
        pass


class JsonlSink:
    """events.jsonl in a folder. Full prompts (only when asked for) go to prompts.jsonl."""

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict) -> None:
        name = "prompts.jsonl" if event["type"] == "prompt" else "events.jsonl"
        with open(self.folder / name, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def close(self) -> None:
        pass


class MarkdownSink:
    """transcript.md, rewritten when a turn ends and when the log closes (cheap at this size)."""

    def __init__(self, folder: str | Path, header: Callable[[], str] | str | None = None):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.header, self.events = header, []

    def _flush(self) -> None:
        h = self.header() if callable(self.header) else self.header
        (self.folder / "transcript.md").write_text(render_markdown(self.events, h), encoding="utf-8")

    def write(self, event: dict) -> None:
        if event["type"] != "prompt":
            self.events.append(event)
        if event["type"] == "turn_end":
            self._flush()

    def close(self) -> None:
        self._flush()


class DbSink:
    """Writes the events that have no other trace row as `agent_steps`. The loop already writes the rest."""
    TYPES = {"approval_card": "approval_card", "tool_refused": "tool_refused"}

    def __init__(self, session):
        self.session = session

    def write(self, event: dict) -> None:
        kind = self.TYPES.get(event["type"])
        if not kind:
            return
        from ...repositories.traces import TraceRepository
        body = {k: v for k, v in event.items() if k not in ("v", "n", "log_id", "project_id", "agent_run_id", "level", "type")}
        TraceRepository(self.session).add(event["project_id"], kind, body, event.get("agent_run_id"))

    def close(self) -> None:
        pass


# ---------------------------------------------------------------- the log

class RunLog:
    """Fan-out of events to sinks. With no sinks it does nothing (the default for run_agent)."""

    def __init__(self, sinks: list | None = None, log_id: str | None = None, log_prompts: bool = False,
                 log_user_text: bool | None = None):
        self.sinks = list(sinks or [])
        self.log_id = log_id or "run"
        self.log_prompts = log_prompts
        if log_user_text is None:
            try:
                from ...config import settings
                log_user_text = settings.log_user_text
            except Exception:
                log_user_text = True
        self.log_user_text = log_user_text
        self.n, self.turn, self.step = 0, 0, None
        self.project_id: str | None = None
        self.agent_run_id: str | None = None
        self.events: list[dict] = []  # kept in memory for tests and the notebook; small per run

    @property
    def active(self) -> bool:
        return bool(self.sinks)

    def begin_turn(self, project_id: str, agent_run_id: str | None) -> None:
        self.turn += 1
        self.step, self.project_id, self.agent_run_id = None, project_id, agent_run_id

    def emit(self, type: str, level: str = "INFO", **fields) -> None:
        if not self.sinks:
            return
        try:
            self.n += 1
            event = {"v": SCHEMA_VERSION, "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                     "n": self.n, "log_id": self.log_id, "project_id": self.project_id, "agent_run_id": self.agent_run_id,
                     "turn": self.turn, "step": self.step, "level": level, "type": type}
            for k, v in fields.items():
                if k == "result":
                    event[k] = _result_for_log(v)
                elif k == "text" and type == "user_message" and not self.log_user_text:
                    event["text_chars"], event["text_sha256"] = len(v or ""), sha(v or "")
                elif k == "messages":
                    event[k] = redact(v)
                else:
                    event[k] = redact(v, k)
            self.events.append(event)
        except Exception:
            return
        for sink in self.sinks:
            try:
                sink.write(event)
            except Exception:
                pass  # a broken sink must never break a turn

    def run_end(self, final_status: str | None = None) -> None:
        """Totals for the whole log (all turns). Called by the eval runner and the notebook, not by the loop."""
        try:
            calls = [e for e in self.events if e["type"] == "llm_call"]
            tools: dict[str, int] = {}
            for e in self.events:
                if e["type"] == "tool_call":
                    tools[e["name"]] = tools.get(e["name"], 0) + 1
            self.emit("run_end", turns=self.turn, final_status=final_status,
                      tokens=sum((e.get("prompt_tokens") or 0) + (e.get("completion_tokens") or 0) for e in calls),
                      cost_usd=sum(e.get("cost_usd") or 0 for e in calls), tools_called=tools)
        except Exception:
            pass

    def close(self) -> None:
        for sink in self.sinks:
            try:
                sink.close()
            except Exception:
                pass


def summarize_result(result) -> tuple[bool, str]:
    """(ok, one-line summary) for a tool result."""
    if isinstance(result, dict):
        if "error" in result:
            return False, _cut(scrub(str(result["error"])), 140)
        bits = []
        for k, v in result.items():
            if isinstance(v, list):
                bits.append(f"{len(v)} {k}")
            elif isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) <= 30):
                bits.append(f"{k}={v}")
            if len(bits) >= 5:
                break
        return True, ", ".join(bits) or "ok"
    return True, _cut(scrub(str(result)), 140)
