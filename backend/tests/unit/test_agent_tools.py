from app.db.tables import DatasetCandidate
from app.ports import DatasetHit
from app.services.agent import tools
from tests.helpers.fakes import FakeSource
from tests.helpers.builders import ctx


def run(tool, c, **args):
    return tools.TOOLS[tool].fn(c, args)


def test_search_lists_bundled_and_hugging_face(session, storage, provider, project):
    r = run("search_datasets", ctx(session, storage, provider, project), query="customer churn")
    sources = [x["source"] for x in r["results"]]
    assert "bundled sample" in sources and "Hugging Face" in sources
    assert any(x["id"] == "hf:good/churn" for x in r["results"])


def test_search_failure_still_returns_bundled_with_a_warning(session, storage, provider, project):
    r = run("search_datasets", ctx(session, storage, provider, project, source=FakeSource(fail_search=True)), query="churn")
    assert r["results"] and "could not reach" in r["warning"]


def test_missing_license_is_reported(session, storage, provider, project):
    src = FakeSource([DatasetHit("a/b", "d", None, 1, 0, False)])
    r = run("search_datasets", ctx(session, storage, provider, project, source=src), query="zzz")
    assert r["results"][0]["license"] == "not stated"


def test_look_at_and_fetch_hf_dataset(session, storage, provider, project):
    c = ctx(session, storage, provider, project)
    look = run("look_at_dataset", c, dataset_id="hf:good/churn")
    assert look["tabular"] and look["rows"] == 1500 and look["license"] == "not stated"
    got = run("fetch_dataset", c, dataset_id="hf:good/churn")
    cand = session.get(DatasetCandidate, got["candidate_id"])
    assert cand.source == "Hugging Face" and cand.source_url.endswith("good/churn") and storage.exists(cand.storage_key)


def test_non_table_and_gated_datasets_are_refused_in_plain_words(session, storage, provider, project):
    c = ctx(session, storage, provider, project)
    assert "error" in run("fetch_dataset", c, dataset_id="hf:bad/images")
    assert "error" in run("fetch_dataset", c, dataset_id="hf:gated/one")
    assert session.query(DatasetCandidate).count() == 0


def test_unknown_ids_are_errors(session, storage, provider, project):
    c = ctx(session, storage, provider, project)
    assert "error" in run("fetch_dataset", c, dataset_id="nope")
    assert "error" in run("look_at_dataset", c, dataset_id="nope")


def test_load_skill_tool(session, storage, provider, project):
    c = ctx(session, storage, provider, project)
    assert "playbook" in run("load_skill", c, name="dataset-search")
    assert "error" in run("load_skill", c, name="missing")


def test_inspect_candidate_gives_grade_and_preview(session, storage, provider, project):
    c = ctx(session, storage, provider, project)
    cid = run("fetch_dataset", c, dataset_id="hf:good/churn")["candidate_id"]
    r = run("inspect_candidate", c, candidate_id=cid, target="left")
    assert r["grade"] and r["findings"] and len(r["preview"]["untrusted_dataset_text"]) == 3  # rows now arrive inside a marked data block (T4)
