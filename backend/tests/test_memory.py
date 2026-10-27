"""Conversation memory (specs/agent/10): the model gets its own earlier calls and results back, inside a budget."""
import json
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.db.tables import AgentRun, Conversation, Message, Project
from app.ports import LLMError, LLMResponse, ToolCall
from doubles.llm import FakeLLM
from doubles.payments import MockPaymentProvider
from app.integrations.storage.local import LocalStorage
from app.integrations.training_local.backend import LocalBackend
from app.services.agent import loop, memory
from app.services.agent.loop import TurnInProgress, run_agent
from app.services.agent.tools import ToolContext
from tests.fakes import FakeSource
from tests.test_agent import call, ctx


class HistoryReader:
    """A 'model' that can only act on what is in the messages it is given (like a real one).

    Turn 1: fetch the dataset, then ask to select it with a target. Turn 2: it must find the candidate id and the target
    in the history and select again WITHOUT fetching. If the history has no tool results it gives up, so the test fails.
    """

    def __init__(self):
        self.seen_inputs: list[list[dict]] = []

    def chat(self, messages, tools):
        self.seen_inputs.append(messages)
        hist = messages[1:]
        fetched = [m for m in hist if m["role"] == "tool" and "candidate_id" in m["content"] and "waiting_for_user" not in m["content"]]
        asked = [c for m in hist if m["role"] == "assistant" for c in m.get("tool_calls", []) if c["function"]["name"] == "select_dataset"]
        selected_ok = any(m["role"] == "tool" and '"target"' in m["content"] and "waiting_for_user" not in m["content"] for m in hist)
        if selected_ok:
            return LLMResponse(text="Your data is chosen. Next I will check how ready it is.")
        if asked:  # turn 2: use what the history says
            if not fetched:
                return LLMResponse(text="I lost track of the dataset.")
            cid = json.loads(fetched[-1]["content"])["candidate_id"]
            target = json.loads(asked[-1]["function"]["arguments"])["target"]
            return LLMResponse(tool_calls=[ToolCall("sel2", "select_dataset", {"candidate_id": cid, "target": target})])
        if fetched:
            cid = json.loads(fetched[-1]["content"])["candidate_id"]
            return LLMResponse(tool_calls=[ToolCall("sel1", "select_dataset", {"candidate_id": cid, "target": "left"})])
        return LLMResponse(tool_calls=[ToolCall("fetch1", "fetch_dataset", {"dataset_id": "hf:good/churn"})])


def names_called(session, conv_id):
    return [c["function"]["name"] for m in session.scalars(select(Message).where(Message.conversation_id == conv_id).order_by(Message.seq))
            for c in (m.tool_calls or [])]


def test_second_turn_reuses_results_from_the_first(session, storage, provider, project):
    model = HistoryReader()
    r1 = run_agent(ctx(session, storage, provider, project), model, "predict churn")
    assert r1.status == "awaiting_approval" and r1.card["args"]["target"] == "left"
    r2 = run_agent(ctx(session, storage, provider, project, {"select_dataset"}), model, None)
    assert r2.status == "reply" and "chosen" in r2.text
    assert project.status == "data_chosen"
    conv = session.scalars(select(Conversation)).one()
    assert names_called(session, conv.id) == ["fetch_dataset", "select_dataset", "select_dataset"]  # no second fetch
    # the approval card is stored as the result of the waiting call, and the state block says what is pending/approved
    card = session.scalars(select(Message).where(Message.kind == "card")).one()
    assert card.tool_call_id == "sel1" and "waiting_for_user" in card.content
    assert "approved just now: select_dataset" in model.seen_inputs[2][0]["content"]


def test_pending_approval_is_in_the_state_block(session, storage, provider, project):
    model = HistoryReader()
    run_agent(ctx(session, storage, provider, project), model, "predict churn")
    conv = session.scalars(select(Conversation)).one()
    built = memory.build(session, project, conv)
    assert "Waiting for the user to approve: select_dataset" in built.state_block and "left" in built.state_block


def test_every_message_kind_is_stored(session, storage, provider, project):
    llm = FakeLLM([LLMResponse(text="Let me read the playbook.", tool_calls=[ToolCall("s1", "load_skill", {"name": "dataset-search"})]),
                   LLMResponse(text="All set.")])
    run_agent(ctx(session, storage, provider, project), llm, "hello")
    rows = list(session.scalars(select(Message).order_by(Message.seq)))
    assert [(m.seq, m.role, m.kind) for m in rows] == [(1, "user", "chat"), (2, "assistant", "chat"), (3, "tool", "skill"), (4, "assistant", "chat")]
    assert rows[1].tool_calls[0]["function"]["name"] == "load_skill" and rows[1].content == "Let me read the playbook."
    assert "playbook" in rows[2].content and rows[2].stub.startswith("load_skill: ok")
    assert session.scalars(select(AgentRun)).one().conversation_id == rows[0].conversation_id


def test_replay_rebuilds_the_same_model_input_from_the_database(session, storage, provider, project):
    llm = FakeLLM([call("search_datasets", query="churn"), call("fetch_dataset", dataset_id="sample-churn"), LLMResponse(text="Found the sample.")])
    run_agent(ctx(session, storage, provider, project), llm, "predict churn")
    conv = session.scalars(select(Conversation)).one()
    rebuilt = memory.model_input(session, project, conv)
    assert rebuilt[-1] == {"role": "assistant", "content": "Found the sample."}  # the final reply is stored too
    assert json.dumps(rebuilt[:-1], sort_keys=True) == json.dumps(llm.calls[-1], sort_keys=True)  # the input of the last real call, byte for byte
    # and an export/import round trip into a fresh database gives the same history
    data = memory.export_conversation(session, conv)
    e2 = create_engine("sqlite://")
    Base.metadata.create_all(e2)
    with sessionmaker(e2, expire_on_commit=False)() as s2:
        p2 = Project(goal=project.goal)
        s2.add(p2)
        s2.commit()
        c2 = memory.import_conversation(s2, p2, data)
        assert memory.history(s2, c2)[0] == memory.history(session, conv)[0]
        # replay without a model: the stored assistant messages come back out in order
        replay = memory.ReplayLLM(data)
        assert [c.name for c in replay.chat([], []).tool_calls] == ["search_datasets"]


def test_replay_llm_reproduces_a_run_without_a_model(session, storage, provider, project):
    run_agent(ctx(session, storage, provider, project), FakeLLM([call("search_datasets", query="churn"), LLMResponse(text="Done.")]), "x")
    data = memory.export_conversation(session, session.scalars(select(Conversation)).one())
    e2 = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(e2)
    with sessionmaker(e2, expire_on_commit=False)() as s2:
        p2 = Project(goal="x")
        s2.add(p2)
        s2.commit()
        c = ToolContext(s2, p2, storage, provider, "mock", LocalBackend(), FakeSource(), set())
        r = run_agent(c, memory.ReplayLLM(data), "x")
        assert r.text == "Done."
        assert names_called(s2, s2.scalars(select(Conversation)).one().id) == ["search_datasets"]


def make_group(session, conv, i, big=False, skill=False):
    """user message, assistant call, tool result: one exchange."""
    memory.add_message(session, conv.id, "user", f"message number {i}")
    cid = f"call-{i}"
    name = "load_skill" if skill else "search_datasets"
    memory.add_message(session, conv.id, "assistant", "", tool_calls=[{"id": cid, "type": "function", "function": {"name": name, "arguments": "{}"}}])
    result = {"playbook": f"PLAYBOOK-{i} " + "rules " * 20} if skill else {"results": [{"id": f"d{i}-{n}", "pad": "x" * 200} for n in range(12)], "n": i}
    memory.add_message(session, conv.id, "tool", json.dumps(result), tool_call_id=cid, tool_name=name, kind="skill" if skill else "chat",
                       stub=memory.stub_for(name, result))
    memory.add_message(session, conv.id, "assistant", f"reply {i}")


def valid_pairs(messages):
    """The rules an API enforces: tool results follow their call, every call is answered, nothing dangles."""
    assert messages[0]["role"] == "system"
    i = 1
    while i < len(messages):
        m = messages[i]
        if m["role"] == "assistant" and m.get("tool_calls"):
            ids = [c["id"] for c in m["tool_calls"]]
            got = []
            i += 1
            while i < len(messages) and messages[i]["role"] == "tool":
                got.append(messages[i]["tool_call_id"])
                i += 1
            assert sorted(got) == sorted(ids), (ids, got)
        else:
            assert m["role"] in ("user", "assistant"), m
            i += 1


def test_long_conversation_with_a_small_budget_keeps_valid_pairs_and_the_state(session, project):
    conv = memory.get_conversation(session, project.id, "eval")
    for i in range(50):  # 200 messages
        make_group(session, conv, i, skill=(i == 3))
    memory.add_message(session, conv.id, "user", "the newest question")
    assert session.scalar(select(Message.seq).order_by(Message.seq.desc())) == 201
    built = memory.build(session, project, conv, budget=1500)
    msgs = built.messages
    valid_pairs(msgs)
    assert "Status: described" in msgs[0]["content"] and "Goal:" in msgs[0]["content"]  # state block is always there
    assert msgs[1]["role"] == "user" and msgs[-1] == {"role": "user", "content": "the newest question"}
    assert built.dropped_groups > 0 and built.history_messages < 201
    assert "PLAYBOOK-3" in msgs[0]["content"]  # a dropped playbook moves into the system message, not lost
    assert memory.estimate_tokens(json.dumps(msgs[1:])) < 3000
    # a generous budget sends everything, and old big results are shrunk to stubs before anything is dropped
    mid = memory.build(session, project, conv, budget=12_000)
    valid_pairs(mid.messages)
    assert mid.stubbed > 0 and mid.dropped_groups == 0 or mid.dropped_groups < built.dropped_groups
    assert any(m["role"] == "tool" and m["content"].startswith(memory.STUB_PREFIX + "search_datasets: ok") for m in mid.messages)
    # nothing was deleted
    assert session.scalar(select(func_count())) == 201


def func_count():
    from sqlalchemy import func
    return func.count(Message.id)


def test_loaded_skill_stays_in_history_when_it_fits(session, project):
    conv = memory.get_conversation(session, project.id)
    make_group(session, conv, 0, skill=True)
    for i in range(1, 12):
        make_group(session, conv, i)
    out = memory.build(session, project, conv, budget=2500)
    valid_pairs(out.messages)
    assert out.stubbed > 0
    assert any("PLAYBOOK-0" in m["content"] for m in out.messages if m["role"] in ("tool", "system"))  # never replaced by a stub text


def test_missing_results_are_repaired_so_the_request_stays_valid(session, project):
    conv = memory.get_conversation(session, project.id)
    memory.add_message(session, conv.id, "user", "hi")
    memory.add_message(session, conv.id, "assistant", "", tool_calls=[{"id": "a", "type": "function", "function": {"name": "x", "arguments": "{}"}},
                                                                    {"id": "b", "type": "function", "function": {"name": "y", "arguments": "{}"}}])
    memory.add_message(session, conv.id, "tool", "{}", tool_call_id="a", tool_name="x")  # crash before "b" was answered
    memory.add_message(session, conv.id, "tool", "{}", tool_call_id="orphan", tool_name="z")
    valid_pairs(memory.model_input(session, project, conv))


def test_a_card_in_the_middle_of_several_calls_answers_the_rest(session, storage, provider, project):
    two = LLMResponse(tool_calls=[ToolCall("a", "select_dataset", {"candidate_id": "x", "target": "t"}), ToolCall("b", "search_datasets", {"query": "q"})])
    r = run_agent(ctx(session, storage, provider, project), FakeLLM([two]), "go")
    assert r.status == "awaiting_approval"
    conv = session.scalars(select(Conversation)).one()
    valid_pairs(memory.model_input(session, project, conv))
    kinds = [m.kind for m in session.scalars(select(Message).where(Message.role == "tool").order_by(Message.seq))]
    assert kinds == ["card", "note"]


def test_limit_and_error_endings_are_saved_as_assistant_messages(session, storage, provider, project, monkeypatch):
    class Broken:
        def chat(self, m, t):
            raise LLMError("The AI service is busy right now.")

    assert run_agent(ctx(session, storage, provider, project), Broken(), "hi").status == "error"
    monkeypatch.setattr(settings, "agent_max_steps", 1)
    assert run_agent(ctx(session, storage, provider, project), FakeLLM([call("search_datasets", query="a")] * 3), "again").status == "limit"
    rows = list(session.scalars(select(Message).where(Message.role == "assistant", Message.kind == "note").order_by(Message.seq)))
    assert "busy" in rows[0].content and "step limit" in rows[1].content
    valid_pairs(memory.model_input(session, project, session.scalars(select(Conversation)).one()))


def test_restart_continues_with_the_full_context(tmp_path):
    url = f"sqlite:///{tmp_path}/restart.db"
    store = LocalStorage(str(tmp_path / "store"))

    def open_session():
        e = create_engine(url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(e)
        return e, sessionmaker(e, expire_on_commit=False)()

    e1, s1 = open_session()
    p = Project(goal="predict churn")
    s1.add(p)
    s1.commit()
    pid = p.id
    model = HistoryReader()
    c1 = ToolContext(s1, p, store, MockPaymentProvider(), "mock", LocalBackend(), FakeSource(), set())
    assert run_agent(c1, model, "predict churn").status == "awaiting_approval"
    s1.close()
    e1.dispose()  # the "process" ends
    e2, s2 = open_session()  # a new process, same database file
    p2 = s2.get(Project, pid)
    c2 = ToolContext(s2, p2, store, MockPaymentProvider(), "mock", LocalBackend(), FakeSource(), {"select_dataset"})
    r = run_agent(c2, HistoryReader(), None)
    assert r.status == "reply" and p2.status == "data_chosen"
    assert s2.scalar(select(__import__("sqlalchemy").func.count(Conversation.id))) == 1  # same conversation continued


def test_seq_is_strictly_increasing_and_unique(session, project):
    conv = memory.get_conversation(session, project.id)
    seqs = [memory.add_message(session, conv.id, "user", str(i)).seq for i in range(5)]
    assert seqs == [1, 2, 3, 4, 5]
    from sqlalchemy.exc import IntegrityError
    session.add(Message(conversation_id=conv.id, seq=3, role="user", content="dup"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_conversations_can_be_marked_eval_or_notebook(session, storage, provider, project):
    run_agent(ctx(session, storage, provider, project), FakeLLM([LLMResponse(text="hi")]), "x", source="eval", meta={"case_id": "c1"})
    conv = session.scalars(select(Conversation)).one()
    assert conv.source == "eval" and conv.meta == {"case_id": "c1"}


# ---------------------------------------------------------------- turn lock (W8)

def test_second_turn_for_the_same_project_is_refused_while_one_runs(session, storage, provider, project):
    started, release = threading.Event(), threading.Event()

    class Slow:
        def chat(self, m, t):
            started.set()
            release.wait(5)
            return LLMResponse(text="done")

    out = {}
    t = threading.Thread(target=lambda: out.setdefault("r", run_agent(ctx(session, storage, provider, project), Slow(), "first")))
    t.start()
    assert started.wait(5)
    with pytest.raises(TurnInProgress):
        run_agent(ctx(session, storage, provider, project), FakeLLM([LLMResponse(text="x")]), "second")
    release.set()
    t.join(5)
    assert out["r"].status == "reply"
    assert run_agent(ctx(session, storage, provider, project), FakeLLM([LLMResponse(text="ok")]), "third").status == "reply"  # lock released


def test_chat_route_answers_409_while_a_turn_runs(session, project, monkeypatch):
    app.dependency_overrides[get_session] = lambda: session
    monkeypatch.setattr("app.routes.projects.get_llm", lambda: FakeLLM([LLMResponse(text="hello")]))
    loop._active.add(project.id)
    try:
        r = TestClient(app).post(f"/projects/{project.id}/chat", json={"message": "hi"})
        assert r.status_code == 409 and "still working" in r.json()["detail"]
    finally:
        loop._active.discard(project.id)
        app.dependency_overrides.clear()


def test_lock_is_released_after_a_crash(session, storage, provider, project):
    class Crash:
        def chat(self, m, t):
            raise ValueError("boom")

    with pytest.raises(ValueError):
        run_agent(ctx(session, storage, provider, project), Crash(), "x")
    assert project.id not in loop._active


def test_two_projects_can_run_at_once(session, storage, provider, project):
    other = Project(goal="other")
    session.add(other)
    session.commit()
    loop._active.add(other.id)
    try:
        assert run_agent(ctx(session, storage, provider, project), FakeLLM([LLMResponse(text="ok")]), "x").status == "reply"
    finally:
        loop._active.discard(other.id)
