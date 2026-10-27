"""UCI source against recorded responses (tests/recordings/uci/, read from the live service on 2026-10-25)."""
import io

import httpx
import pandas as pd
import pytest

from app.ports import SourceError
from app.integrations.datasets.uci import UCISource
from tests.replay import uci_transport


@pytest.fixture
def uci():
    return UCISource(transport=uci_transport())


def test_search_parses_names_size_target_and_license(uci):
    hits = uci.search("credit card", limit=5)
    assert {h.id for h in hits} >= {"144", "350"}
    german = next(h for h in hits if h.id == "144")
    assert german.rows == 1000 and german.target == "class" and german.tabular and "Classification" in german.tasks
    assert german.license == "cc-by-4.0" and german.description


def test_search_with_no_matches_is_empty(uci):
    assert uci.search("zzzz nothing", limit=5) == []


def test_info_for_a_plain_table(uci):
    i = uci.info("222")
    assert i.rows == 45211 and i.target == "y" and i.tabular and not i.gated
    assert any("CC BY 4.0" in n for n in i.notes) and i.columns


def test_text_collection_is_not_a_plain_table(uci):
    i = uci.info("228")
    assert not i.tabular and any("not a plain table" in n for n in i.notes)
    with pytest.raises(SourceError, match="not a plain table"):
        uci.fetch_csv("228", 50_000, 50_000_000)


def test_fetch_converts_to_csv_and_keeps_the_target(uci):
    f = uci.fetch_csv("144", 50_000, 50_000_000)
    df = pd.read_csv(io.BytesIO(f.csv_bytes))
    assert f.rows == 40 and "class" in df.columns and f.suggested_target == "class"
    assert f.truncated is True  # the recording holds 40 of the 1000 rows, and info says 1000


def test_row_limit_truncates():
    f = UCISource(transport=uci_transport()).fetch_csv("144", 10, 50_000_000)
    assert f.rows == 10 and f.truncated


def test_oversized_download_is_refused(uci):
    with pytest.raises(SourceError, match="too large"):
        uci.fetch_csv("144", 50_000, 500)


def test_unknown_and_invalid_ids(uci):
    with pytest.raises(SourceError, match="not found"):
        uci.info("999999")
    for bad in ("../../etc", "12;rm", "", "1e5"):
        with pytest.raises(SourceError, match="valid UCI"):
            uci.info(bad)


def test_network_failure_is_a_plain_error():
    with pytest.raises(SourceError, match="could not reach"):
        UCISource(transport=uci_transport(fail=True)).search("credit")


def test_unreadable_file_is_refused():
    def handler(request):
        return httpx.Response(200, content=b"\x00\x01 not a table") if "data.csv" in request.url.path else uci_transport().handle_request(request)
    src = UCISource(transport=httpx.MockTransport(handler))
    with pytest.raises(SourceError):
        src.fetch_csv("144", 50_000, 50_000_000)
