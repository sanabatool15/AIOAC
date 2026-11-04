"""A missing or placeholder model key gives a clear 503 on /chat, and /health says whether chat can work (never the key)."""
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_session
from app.deps import get_llm_client
from app.main import app
from app.ports import LLMResponse
from doubles.llm import FakeLLM


@pytest.fixture
def api(session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("key", ["", "your-openrouter-key", "  "])
def test_chat_without_a_real_key_is_503(api, project, monkeypatch, key):
    monkeypatch.setattr(settings, "openrouter_api_key", key)
    r = api.post(f"/projects/{project.id}/chat", json={"message": "hi"})
    assert r.status_code == 503 and "not set up" in r.json()["detail"]
    h = api.get("/health").json()
    assert h["ok"] is True and h["llm"] == {"configured": False}


def test_health_reports_configured_without_leaking_the_key(api, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-real-looking-1234")
    r = api.get("/health")
    assert r.json()["llm"] == {"configured": True} and "sk-or" not in r.text


def test_chat_works_when_a_client_is_provided(api, project):
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM([LLMResponse(text="hello")])
    r = api.post(f"/projects/{project.id}/chat", json={"message": "hi"})
    assert r.status_code == 200 and r.json()["text"] == "hello"
