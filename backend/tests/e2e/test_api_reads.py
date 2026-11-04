"""Read routes: project list, fuller project view, message history, CORS."""
from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app
from app.repositories import conversations as conv_repo


def test_list_and_detail_are_nullable_before_anything_exists(session):
    app.dependency_overrides[get_session] = lambda: session
    c = TestClient(app)
    a = c.post("/projects", json={"goal": "first"}).json()["id"]
    b = c.post("/projects", json={"goal": "second"}).json()["id"]
    assert [p["id"] for p in c.get("/projects").json()] == [b, a]
    assert {"goal", "status", "created_at"} <= set(c.get("/projects").json()[0])
    d = c.get(f"/projects/{a}").json()
    assert all(d[k] is None for k in ("dataset", "readiness", "forecast", "payment", "run", "quote"))
    assert c.get("/projects/nope/messages").status_code == 404
    assert c.get("/projects/nope/payment").status_code == 404
    app.dependency_overrides.clear()


def test_messages_return_chat_and_cards_but_not_tool_results(session, project):
    app.dependency_overrides[get_session] = lambda: session
    conv = conv_repo.create(session, project_id=project.id)
    conv_repo.append_message(session, conv.id, role="user", content="hello", kind="chat")
    conv_repo.append_message(session, conv.id, role="assistant", content="", tool_calls=[{"id": "1"}], kind="chat")
    conv_repo.append_message(session, conv.id, role="tool", content='{"secret": 1}', tool_name="x", kind="chat")
    conv_repo.append_message(session, conv.id, role="tool", content='{"what": "Use this data", "tool": "select_dataset", "args": {}}',
                             tool_name="select_dataset", kind="card")
    conv_repo.append_message(session, conv.id, role="assistant", content="Done", kind="chat")
    msgs = TestClient(app).get(f"/projects/{project.id}/messages").json()
    assert [(m["role"], m["kind"], m["text"]) for m in msgs] == [("user", "chat", "hello"), ("assistant", "card", "Use this data"),
                                                                 ("assistant", "chat", "Done")]
    assert msgs[1]["card"]["tool"] == "select_dataset"
    app.dependency_overrides.clear()


def test_cors_preflight_allows_the_frontend_origin():
    c = TestClient(app)
    r = c.options("/projects", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                                        "Access-Control-Request-Headers": "content-type"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert r.headers["access-control-allow-credentials"] == "true"
    other = c.options("/projects", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in other.headers
