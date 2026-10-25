"""OpenML source against recorded responses (tests/recordings/openml/, read from the live service on 2026-10-25)."""
import io

import httpx
import pandas as pd
import pytest

from app.providers.datasets.base import SourceError
from app.providers.datasets.openml import OpenMLSource
from tests.replay import openml_transport, rec


@pytest.fixture
def oml():
    return OpenMLSource(transport=openml_transport())


def test_search_by_name_parses_rows_and_task(oml):
    hits = oml.search("titanic", limit=5)
    ids = {h.id: h for h in hits}
    assert "40945" in ids and ids["40945"].rows == 1309 and ids["40945"].tasks == ["Classification"]
    assert ids["40945"].name == "Titanic"


def test_search_with_no_results_is_empty_not_an_error(oml):
    assert oml.search("zzzz unknown thing", limit=5) == []


def test_info_gives_target_license_and_columns(oml):
    i = oml.info("40945")
    assert i.rows == 1309 and i.target == "survived" and i.tabular and i.license == "Public"
    assert {"pclass", "survived"} <= {c["name"] for c in i.columns}


def test_fetch_converts_parquet_to_csv(oml):
    f = oml.fetch_csv("40945", 50_000, 50_000_000)
    df = pd.read_csv(io.BytesIO(f.csv_bytes))
    assert f.rows == 30 and "survived" in df.columns and f.suggested_target == "survived" and not f.truncated


def test_row_limit_and_size_limit(oml):
    assert oml.fetch_csv("40945", 5, 50_000_000).rows == 5
    with pytest.raises(SourceError, match="too large"):
        oml.fetch_csv("40945", 50_000, 100)


def test_inactive_dataset_is_refused():
    data = rec("openml/data_40945.json")
    data["data_set_description"]["status"] = "deactivated"

    def handler(request):
        return httpx.Response(200, json=data) if request.url.path.endswith("/data/40945") else openml_transport().handle_request(request)
    src = OpenMLSource(transport=httpx.MockTransport(handler))
    assert not src.info("40945").tabular
    with pytest.raises(SourceError, match="not a plain table"):
        src.fetch_csv("40945", 50_000, 50_000_000)


def test_sparse_or_non_table_features_are_refused():
    feats = rec("openml/features_40945.json")
    feats["data_features"]["feature"][0]["data_type"] = "image"

    def handler(request):
        return httpx.Response(200, json=feats) if "features" in request.url.path else openml_transport().handle_request(request)
    assert not OpenMLSource(transport=httpx.MockTransport(handler)).info("40945").tabular


def test_download_address_must_be_on_the_openml_data_host():
    data = rec("openml/data_40945.json")
    data["data_set_description"]["parquet_url"] = "https://evil.example.com/x.pq"

    def handler(request):
        return httpx.Response(200, json=data) if request.url.path.endswith("/data/40945") else openml_transport().handle_request(request)
    with pytest.raises(SourceError, match="do not trust"):
        OpenMLSource(transport=httpx.MockTransport(handler)).fetch_csv("40945", 50_000, 50_000_000)


def test_unknown_and_invalid_ids(oml):
    with pytest.raises(SourceError, match="not found"):
        oml.info("123456")
    for bad in ("../x", "4;5", "", "abc"):
        with pytest.raises(SourceError, match="valid OpenML"):
            oml.info(bad)


def test_network_failure_is_a_plain_error():
    with pytest.raises(SourceError, match="could not reach"):
        OpenMLSource(transport=openml_transport(fail=True)).search("titanic")
