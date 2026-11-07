import pytest

from app.config import settings
from app.integrations.factory import build_registry
from app.services.data import dataset_link, datasets
from doubles.datasets import OfflineSource
from tests.helpers.fakes import FakeSource


class Spy(FakeSource):
    def fetch_csv(self, dataset_id, max_rows, max_bytes):
        self.limits = (max_rows, max_bytes)
        return super().fetch_csv(dataset_id, max_rows, max_bytes)


def test_a_hugging_face_link_becomes_a_candidate_under_the_normal_limits(session, storage, project):
    src = Spy()
    reg = build_registry(hf=src, uci=OfflineSource(), oml=OfflineSource())
    out = dataset_link.add_from_link(session, storage, project, reg, "https://huggingface.co/datasets/good/churn")
    assert out["rows"] == 1500 and out["candidate_id"]
    assert src.fetched == ["good/churn"] and src.limits == (settings.max_fetch_rows, settings.max_fetch_bytes)
    assert (settings.max_fetch_rows, settings.max_fetch_bytes) == (50_000, 50 * 1024 * 1024) or settings.max_fetch_rows <= 50_000
    cand = datasets.repo.get_candidate(session, out["candidate_id"])
    assert cand.source == "Hugging Face" and cand.source_url == "https://huggingface.co/datasets/good/churn" and cand.project_id == project.id


@pytest.mark.parametrize("url", ["http://huggingface.co/datasets/a/b", "https://example.com/data.csv", "https://127.0.0.1/d/1"])
def test_other_addresses_are_refused_and_nothing_is_fetched(session, storage, project, url):
    src = Spy()
    reg = build_registry(hf=src, uci=src, oml=src)
    with pytest.raises(datasets.DatasetError, match="not one we can use"):
        dataset_link.add_from_link(session, storage, project, reg, url)
    assert src.fetched == []


def test_source_problems_come_back_as_plain_errors(session, storage, project):
    reg = build_registry(hf=Spy(), uci=OfflineSource(), oml=OfflineSource())
    with pytest.raises(datasets.DatasetError, match="cannot be used"):
        dataset_link.add_from_link(session, storage, project, reg, "https://huggingface.co/datasets/gated/one")
    with pytest.raises(datasets.DatasetError, match="not found"):
        dataset_link.add_from_link(session, storage, project, reg, "https://huggingface.co/datasets/no/such")
