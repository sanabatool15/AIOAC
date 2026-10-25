"""Replay fakes: recorded responses (tests/recordings/<source>/) served behind httpx.MockTransport. No network."""
import json
from pathlib import Path

import httpx

REC = Path(__file__).parent / "recordings"


def rec(path: str):
    p = REC / path
    return p.read_bytes() if p.suffix in (".parquet", ".csv") else json.loads(p.read_text())


def uci_transport(csv_name: str = "data_144_head.csv", fail: bool = False) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("offline")
        u, q = request.url, dict(request.url.params)
        if u.host != "archive.ics.uci.edu":
            return httpx.Response(500)
        if u.path == "/api/datasets/list":
            name = {"credit": "list_credit.json", "spam": "list_spam.json"}.get(q.get("search"))
            return httpx.Response(200, json=rec(f"uci/{name}") if name else {"status": 200, "statusText": "OK", "data": []})
        if u.path == "/api/dataset":
            f = REC / "uci" / f"dataset_{q.get('id')}.json"
            return httpx.Response(200, json=json.loads(f.read_text())) if f.exists() else httpx.Response(200, json=rec("uci/not_found.json"))
        if u.path == "/static/public/144/data.csv":
            return httpx.Response(200, content=rec(f"uci/{csv_name}"))
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def openml_transport(poisoned: bool = False, fail: bool = False) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("offline")
        u = request.url
        if u.host == "data.openml.org":
            return httpx.Response(200, content=rec("openml/titanic_head.parquet"))
        path = u.path.removeprefix("/api/v1/json/")
        if path.startswith("data/list/data_name/titanic"):
            return httpx.Response(200, json=rec("openml/list_titanic.json"))
        if path.startswith("data/list/"):
            return httpx.Response(412, json=rec("openml/error_372.json"))
        if path == "data/40945":
            return httpx.Response(200, json=rec("openml/data_40945_poisoned.json" if poisoned else "openml/data_40945.json"))
        if path == "data/features/40945":
            return httpx.Response(200, json=rec("openml/features_40945.json"))
        if path == "data/qualities/40945":
            return httpx.Response(200, json=rec("openml/qualities_40945.json"))
        return httpx.Response(412, json=rec("openml/error_111.json"))
    return httpx.MockTransport(handler)


def hf_search_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/datasets":
            tagged = "filter" in dict(request.url.params)
            return httpx.Response(200, json=rec(f"huggingface/search_customer_churn_{'tagged' if tagged else 'untagged'}.json"))
        return httpx.Response(404)
    return httpx.MockTransport(handler)
