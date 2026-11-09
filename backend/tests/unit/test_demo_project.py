"""POST /projects/demo: off by default, and when on it leaves a chat at the price step."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_session
from app.routes import projects as projects_routes
from tests.helpers.auth import sign_in


def client(session):
    app = sign_in(FastAPI())
    app.include_router(projects_routes.router)
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_demo_project_is_off_unless_enabled(session, monkeypatch):
    monkeypatch.setattr(settings, "demo_project_enabled", False)
    assert client(session).post("/projects/demo").status_code == 404


def test_demo_project_lands_at_the_price_step(session, storage, monkeypatch):
    monkeypatch.setattr(settings, "demo_project_enabled", True)
    monkeypatch.setattr(projects_routes, "get_storage", lambda: storage)
    r = client(session).post("/projects/demo")
    assert r.status_code == 200 and r.json()["status"] == "quoted"
