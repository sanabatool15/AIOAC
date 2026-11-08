"""POST /projects/{id}/data/link: a pasted Hugging Face, UCI or OpenML page address becomes a candidate (nothing else is fetched)."""
import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.integrations.factory import build_registry
from app.main import app
from app.routes import projects
from doubles.datasets import OfflineSource
from tests.helpers.fakes import FakeSource


@pytest.fixture
def api(session, storage, monkeypatch):
    app.dependency_overrides[get_session] = lambda: session
    monkeypatch.setattr(projects, "get_storage", lambda: storage)
    src = FakeSource()
    monkeypatch.setattr(projects, "get_dataset_source", lambda: build_registry(hf=src, uci=OfflineSource(), oml=OfflineSource()))
    c = TestClient(app)
    c.source = src
    yield c
    app.dependency_overrides.pop(get_session, None)


def test_a_good_link_gives_a_candidate_that_can_then_be_selected(api, project):
    r = api.post(f"/projects/{project.id}/data/link", json={"url": "https://huggingface.co/datasets/good/churn"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows"] == 1500 and body["candidate_id"] and "left" in body["columns"]
    assert api.source.fetched == ["good/churn"]
    s = api.post(f"/projects/{project.id}/data/{body['candidate_id']}/select", json={"target": "left"})
    assert s.status_code == 200 and s.json()["status"] == "data_chosen"


@pytest.mark.parametrize("url", ["https://example.com/data.csv", "http://huggingface.co/datasets/a/b", "https://127.0.0.1/d/1",
                                 "file:///etc/passwd", "https://user:pw@huggingface.co/datasets/a/b"])
def test_bad_links_are_400_and_nothing_is_fetched(api, project, url):
    r = api.post(f"/projects/{project.id}/data/link", json={"url": url})
    assert r.status_code == 400 and "not one we can use" in r.json()["detail"]
    assert api.source.fetched == []


def test_source_failures_are_plain_400s(api, project):
    r = api.post(f"/projects/{project.id}/data/link", json={"url": "https://huggingface.co/datasets/gated/one"})
    assert r.status_code == 400 and "cannot be used" in r.json()["detail"]


def test_empty_or_missing_url_is_422(api, project):
    assert api.post(f"/projects/{project.id}/data/link", json={"url": ""}).status_code == 422
    assert api.post(f"/projects/{project.id}/data/link", json={}).status_code == 422


def test_someone_elses_project_is_404(api, project):
    assert api.post("/projects/nope/data/link", json={"url": "https://huggingface.co/datasets/good/churn"}).status_code == 404
