"""Hugging Face client against canned responses shaped like the live API (verified by hand on 2026-10)."""
import io

import httpx
import pandas as pd
import pytest

from app.ports import SourceError
from app.integrations.datasets.huggingface import HuggingFaceSource

TABULAR = {"id": "o/tab", "description": "x" * 500, "downloads": 9, "likes": 1, "gated": False, "private": False,
           "cardData": {"license": "cc-by-4.0"}}
UNTAGGED = {"id": "o/untagged", "downloads": 100, "likes": 5, "gated": False, "private": False}
PRIVATE = {"id": "o/private", "private": True}


def parquet_bytes():
    buf = io.BytesIO()
    pd.DataFrame({"a": [1, 2, 3], "left": [0, 1, 0]}).to_parquet(buf)
    return buf.getvalue()


def handler(request: httpx.Request) -> httpx.Response:
    u, q = request.url, dict(request.url.params)
    if u.path == "/api/datasets" and "filter" in q:
        return httpx.Response(200, json=[TABULAR])
    if u.path == "/api/datasets":
        return httpx.Response(200, json=[TABULAR, UNTAGGED, PRIVATE])
    if u.path == "/api/datasets/o/tab":
        return httpx.Response(200, json={"gated": False, "cardData": {"license": "cc-by-4.0"}})
    if u.path == "/api/datasets/o/gated":
        return httpx.Response(200, json={"gated": "auto"})
    if u.path == "/api/datasets/o/missing":
        return httpx.Response(404)
    if u.path == "/api/datasets/o/limited":
        return httpx.Response(429)
    if u.host == "datasets-server.huggingface.co":
        if u.path == "/splits":
            return httpx.Response(200, json={"splits": [{"dataset": "o/tab", "config": "default", "split": "test"},
                                                        {"dataset": "o/tab", "config": "default", "split": "train"}]})
        if u.path == "/size":
            return httpx.Response(200, json={"size": {"dataset": {"num_rows": 3}, "configs": [
                {"config": "default", "num_rows": 3, "num_bytes_parquet_files": 2000}]}})
        if u.path == "/first-rows":
            return httpx.Response(200, json={"features": [
                {"name": "a", "type": {"dtype": "int64", "_type": "Value"}},
                {"name": "left", "type": {"names": ["No", "Yes"], "_type": "ClassLabel"}}]})
        if u.path == "/parquet":
            return httpx.Response(200, json={"parquet_files": [
                {"config": "default", "split": "train", "url": "https://huggingface.co/files/0.parquet", "size": 2000}]})
    if u.path == "/files/0.parquet":
        return httpx.Response(200, content=parquet_bytes())
    return httpx.Response(500)


@pytest.fixture
def hf():
    return HuggingFaceSource(transport=httpx.MockTransport(handler))


def test_search_merges_tagged_and_untagged_and_drops_private(hf):
    ids = [h.id for h in hf.search("churn")]
    assert ids == ["o/tab", "o/untagged"]


def test_search_trims_description_and_reports_missing_license(hf):
    hits = {h.id: h for h in hf.search("churn")}
    assert len(hits["o/tab"].description) == 200 and hits["o/untagged"].license is None


def test_info_picks_train_split_and_reads_columns(hf):
    i = hf.info("o/tab")
    assert (i.split, i.rows, i.tabular, i.license) == ("train", 3, True, "cc-by-4.0")
    assert [c["name"] for c in i.columns] == ["a", "left"]


def test_gated_dataset_is_flagged_and_not_fetched(hf):
    assert hf.info("o/gated").gated
    with pytest.raises(SourceError, match="gated"):
        hf.fetch_csv("o/gated", 100, 10**6)


def test_fetch_converts_class_labels_to_names(hf):
    f = hf.fetch_csv("o/tab", 100, 10**6)
    df = pd.read_csv(io.BytesIO(f.csv_bytes))
    assert list(df["left"]) == ["No", "Yes", "No"] and f.rows == 3 and not f.truncated


def test_fetch_respects_size_limit(hf):
    with pytest.raises(SourceError, match="too large"):
        hf.fetch_csv("o/tab", 100, 1000)


def test_fetch_truncates_rows(hf):
    f = hf.fetch_csv("o/tab", 2, 10**6)
    assert f.rows == 2 and f.truncated


@pytest.mark.parametrize("bad", ["../etc/passwd", "a/b/c", "", "o/x?y=1", "o/x#z"])
def test_rejects_unsafe_dataset_ids(hf, bad):
    with pytest.raises(SourceError, match="valid"):
        hf.info(bad)


def test_http_problems_become_plain_errors(hf):
    with pytest.raises(SourceError, match="not found"):
        hf.info("o/missing")
    with pytest.raises(SourceError, match="rate-limiting"):
        hf.info("o/limited")


def test_network_failure_is_plain():
    def boom(request):
        raise httpx.ConnectError("down")
    with pytest.raises(SourceError, match="could not reach"):
        HuggingFaceSource(transport=httpx.MockTransport(boom)).search("x")
