"""Run log (specs/agent/06): events match what the loop did, secrets never reach a sink, logging never breaks a turn."""
import io
import json

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.tables import AgentStep
from app.ports import LLMResponse, ToolCall, Usage
from doubles.llm import FakeLLM
from app.services.agent.loop import run_agent
from app.services.agent.runlog import ConsoleSink, DbSink, JsonlSink, MarkdownSink, RunLog, format_line, redact
from tests.helpers.builders import call, ctx

FAKE_KEY = "sk-or-v1-abcdefghijklmnopqrstuvwxyz012345"
FAKE_BEARER = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcdefghijklmnop"


def all_sinks(tmp_path, session=None, stream=None, **kw):
    sinks = [ConsoleSink(stream or io.StringIO(), "DEBUG"), JsonlSink(tmp_path), MarkdownSink(tmp_path)]
    if session is not None:
        sinks.append(DbSink(session))
    return RunLog(sinks, log_id="test/run", **kw)


def events_of(tmp_path):
    return [json.loads(l) for l in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_events_match_the_tool_calls_and_every_call_has_an_outcome(session, storage, provider, project, tmp_path):
    llm = FakeLLM([LLMResponse(tool_calls=[ToolCall("c-skill", "load_skill", {"name": "dataset-search"})]), call("search_datasets", query="churn"),
                   call("fetch_dataset", dataset_id="sample-churn"), call("select_dataset", candidate_id="x", target="left")])
    log = all_sinks(tmp_path)
    r = run_agent(ctx(session, storage, provider, project), llm, "predict churn", log=log)
    log.close()
    assert r.status == "awaiting_approval"
    ev = events_of(tmp_path)
    calls = [e for e in ev if e["type"] == "tool_call"]
    stored = [s.content["name"] for s in session.scalars(select(AgentStep).where(AgentStep.kind == "tool_call"))]
    assert [c["name"] for c in calls] == stored == ["load_skill", "search_datasets", "fetch_dataset", "select_dataset"]
    for c in calls:  # a result, or an approval card for the one that waits for the user
        assert any(e["type"] in ("tool_result", "approval_card") and (e.get("call_id") == c["call_id"] or e["type"] == "approval_card" and e["tool"] == c["name"])
                   for e in ev), c
    assert [e["n"] for e in ev] == list(range(1, len(ev) + 1))
    assert {e["v"] for e in ev} == {1} and ev[0]["type"] == "turn_start" and ev[-1]["type"] == "turn_end"
    assert ev[-1]["status"] == "awaiting_approval"
    card = next(e for e in ev if e["type"] == "approval_card")
    assert card["tool"] == "select_dataset" and card["args"]["target"] == "left"
    llm_calls = [e for e in ev if e["type"] == "llm_call"]
    assert len(llm_calls) == 4 and llm_calls[0]["tool_calls"][0]["name"] == "load_skill"
    assert (tmp_path / "transcript.md").read_text(encoding="utf-8").startswith("# ")
    assert "search_datasets" in "\n".join(format_line(e) for e in ev)


def test_refusals_are_logged_with_a_reason(session, storage, provider, project, tmp_path):
    log = all_sinks(tmp_path)
    run_agent(ctx(session, storage, provider, project), FakeLLM([call("start_training"), call("rm_rf"), LLMResponse(text="ok")]), "go", log=log)
    why = [e["why"] for e in log.events if e["type"] == "tool_refused"]
    assert why == ["not_offered", "unknown_tool"]
    assert all(e["ok"] is False for e in log.events if e["type"] == "tool_result")


def test_gate_decisions_and_guards_are_logged(session, storage, provider, project):
    log = RunLog([ConsoleSink(io.StringIO())])
    run_agent(ctx(session, storage, provider, project), FakeLLM([LLMResponse(text="Your payment was received and training has started!")]), "x", log=log)
    g = next(e for e in log.events if e["type"] == "guard")
    assert g["guard"] == "claim" and g["level"] == "WARN"
    assert next(e for e in log.events if e["type"] == "assistant_reply")["corrected"] is True


def test_secrets_never_appear_in_any_sink(session, storage, provider, project, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "my-real-looking-key-123456")
    stream = io.StringIO()
    log = all_sinks(tmp_path, session, stream)
    secret_text = f"my key is {FAKE_KEY} and header was {FAKE_BEARER}, card 4111111111111111, also my-real-looking-key-123456"
    llm = FakeLLM([LLMResponse(text=f"I saw {FAKE_KEY}", tool_calls=[ToolCall("c1", "select_dataset", {"candidate_id": FAKE_KEY, "target": FAKE_BEARER})])])
    run_agent(ctx(session, storage, provider, project), llm, secret_text, log=log)
    log.close()
    blob = "\n".join([(tmp_path / "events.jsonl").read_text(encoding="utf-8"), (tmp_path / "transcript.md").read_text(encoding="utf-8"), stream.getvalue(),
                      json.dumps([s.content for s in session.scalars(select(AgentStep).where(AgentStep.kind == "approval_card"))])])
    for needle in (FAKE_KEY, "eyJhbGciOiJIUzI1NiIs", "4111111111111111", "my-real-looking-key-123456", "abcdefghijklmnop"):
        assert needle not in blob, needle
    assert "[redacted" in blob
    assert session.scalars(select(AgentStep).where(AgentStep.kind == "approval_card")).first() is not None  # DbSink wrote the card


def test_dataset_rows_are_capped_and_prompts_are_not_logged_by_default(session, storage, provider, project, tmp_path):
    rows = [{"name": "x" * 100, "n": i} for i in range(10)]
    out = redact({"preview": rows})
    assert len(out["preview"]) == 3 and out["rows_truncated"] is True and len(out["preview"][0]["name"]) <= 43
    log = all_sinks(tmp_path)
    run_agent(ctx(session, storage, provider, project), FakeLLM([LLMResponse(text="hello")]), "private goal text", log=log)
    assert not (tmp_path / "prompts.jsonl").exists()
    ctx_event = next(e for e in log.events if e["type"] == "context")
    assert "Status: described" in ctx_event["state_block"] and len(ctx_event["prompt_sha256"]) == 64
    assert "messages" not in ctx_event


def test_full_prompts_only_when_asked(session, storage, provider, project, tmp_path):
    log = all_sinks(tmp_path, log_prompts=True)
    run_agent(ctx(session, storage, provider, project), FakeLLM([LLMResponse(text="hello")]), "hi", log=log)
    assert (tmp_path / "prompts.jsonl").exists()


def test_user_text_can_be_turned_off(session, storage, provider, project, tmp_path):
    log = all_sinks(tmp_path, log_user_text=False)
    run_agent(ctx(session, storage, provider, project), FakeLLM([LLMResponse(text="hello")]), "my private goal", log=log)
    u = next(e for e in events_of(tmp_path) if e["type"] == "user_message")
    assert "text" not in u and u["text_chars"] == 15 and len(u["text_sha256"]) == 64
    assert "my private goal" not in (tmp_path / "events.jsonl").read_text(encoding="utf-8")


def test_a_broken_sink_or_redaction_never_breaks_a_turn(session, storage, provider, project, monkeypatch):
    class Boom:
        def write(self, e):
            raise RuntimeError("disk full")

        def close(self):
            raise RuntimeError("disk full")

    log = RunLog([Boom(), ConsoleSink(io.StringIO())])
    r = run_agent(ctx(session, storage, provider, project), FakeLLM([call("search_datasets", query="x"), LLMResponse(text="done")]), "hi", log=log)
    assert r.status == "reply"
    log.close()
    import app.services.agent.runlog as rl
    monkeypatch.setattr(rl, "redact", lambda *a, **k: 1 / 0)
    r2 = run_agent(ctx(session, storage, provider, project), FakeLLM([LLMResponse(text="still fine")]), "again", log=RunLog([ConsoleSink(io.StringIO())]))
    assert r2.status == "reply"


def test_default_log_is_a_no_op(session, storage, provider, project):
    assert run_agent(ctx(session, storage, provider, project), FakeLLM([LLMResponse(text="hi")]), "x").status == "reply"


def test_llm_error_and_limit_are_logged(session, storage, provider, project, monkeypatch):
    from app.ports import LLMError

    class Broken:
        def chat(self, m, t):
            raise LLMError("busy", retryable=True)

    log = RunLog([ConsoleSink(io.StringIO())])
    run_agent(ctx(session, storage, provider, project), Broken(), "hi", log=log)
    e = next(e for e in log.events if e["type"] == "llm_error")
    assert e["level"] == "ERROR" and e["retryable"] is True
    monkeypatch.setattr(settings, "agent_max_steps", 1)
    log2 = RunLog([ConsoleSink(io.StringIO())])
    run_agent(ctx(session, storage, provider, project), FakeLLM([call("search_datasets", query="x")] * 3), "hi", log=log2)
    assert next(e for e in log2.events if e["type"] == "limit")["reason"] == "steps"
    assert log2.events[-1]["type"] == "turn_end" and log2.events[-1]["status"] == "limit"


def test_eval_run_writes_a_folder_per_case_and_show_reads_it(tmp_path, capsys):
    from evals import run as evals_run, show
    code = evals_run.main(["--fake", "--repeats", "1", "--cases", "churn-subscription", "--report-dir", str(tmp_path / "rp"),
                           "--log-dir", str(tmp_path / "logs")])
    assert code == 0
    batch = next((tmp_path / "logs").glob("eval-*"))
    run_dir = batch / "churn-subscription" / "r1"
    assert {p.name for p in run_dir.iterdir()} >= {"events.jsonl", "transcript.md", "conversation.json"}
    index = json.loads((batch / "index.json").read_text(encoding="utf-8"))
    assert index[0]["passed"] is True and index[0]["folder"] == str(run_dir)
    ev = show.load_events(run_dir)
    assert ev[-1]["type"] == "run_end" and ev[-1]["turns"] == 2
    assert "select_dataset" in show.show_run(str(run_dir), tools=True)
    assert "# churn-subscription r1" in show.show_run(str(run_dir), md=True)
    assert show.show_run(str(batch)).startswith("PASS")
    rel = f"{batch.name}/churn-subscription/r1"
    assert show.show_run(rel, log_dir=tmp_path / "logs", raw=True).startswith("{")
    assert show.main([rel, "--log-dir", str(tmp_path / "logs"), "--level", "WARN"]) == 0
    assert show.main(["nope", "--log-dir", str(tmp_path)]) == 2


def test_failed_eval_runs_print_their_folder(tmp_path, capsys, monkeypatch):
    from evals import run as evals_run
    monkeypatch.setattr(evals_run, "JARGON", __import__("re").compile(r"."))  # every reply now counts as jargon
    evals_run.main(["--fake", "--repeats", "1", "--cases", "vague-goal", "--report-dir", str(tmp_path / "rp"), "--log-dir", str(tmp_path / "logs")])
    out = capsys.readouterr().out
    assert "FAILED vague-goal #1: python -m evals.show" in out
