"""The browser launcher (tests/browser_server.py) boots the real app on doubles and a whole paid flow works through it."""
import pytest
from fastapi.testclient import TestClient

from tests import browser_server

pytestmark = pytest.mark.real_auth


@pytest.fixture
def server():
    from app.services import auth
    auth.reset_throttle()
    h = browser_server.install("http://localhost:3000", threaded=False)
    yield h
    h.close()


def test_refuses_postgres(tmp_path):
    with pytest.raises(browser_server.RefuseToStart):
        browser_server.prepare_environment("http://localhost:3000", str(tmp_path), env={"DATABASE_URL": "postgresql://u:p@h/db"})


def test_prepare_environment_clears_keys_and_uses_temp_sqlite(tmp_path):
    env = {"AZURE_OPENAI_API_KEY": "real", "PAYPAL_CLIENT_SECRET": "real"}
    browser_server.prepare_environment("http://localhost:3000", str(tmp_path), env=env)
    assert env["AZURE_OPENAI_API_KEY"] == "" and env["PAYPAL_CLIENT_SECRET"] == ""
    assert env["DATABASE_URL"].startswith("sqlite:///" + str(tmp_path)) and len(env["SECRET_KEY"]) >= 32


def test_full_flow_through_the_launcher(server):
    c = TestClient(server.app)
    assert c.get("/health").json()["llm"]["configured"] is True
    r = c.post("/auth/signup", json={"email": "browser@example.test", "password": "correct horse battery"})
    assert r.status_code == 200, r.text
    pid = c.post("/projects", json={"goal": "predict which customers will leave"}).json()["id"]

    r = c.post(f"/projects/{pid}/chat", json={"message": "predict which customers will leave"}).json()
    assert r["status"] == "reply" and r["card"] is None, r  # no search before the user chose "I have no data"
    assert c.get(f"/projects/{pid}/activity").json() == [] or "Searched" not in str(c.get(f"/projects/{pid}/activity").json())
    r = c.post(f"/projects/{pid}/chat", json={"message": "I have no data. Please find a dataset."}).json()
    assert r["status"] == "awaiting_approval", r
    card = r["card"]
    assert card["tool"] == "select_dataset" and card["detail"]["target"] == "left" and card["detail"]["rows"] and "predict the column" in card["what"]
    r = c.post(f"/projects/{pid}/chat", json={"message": "yes, use it", "approve": ["select_dataset"]}).json()
    assert r["status"] == "reply", r
    assert c.get(f"/projects/{pid}").json()["status"] == "data_chosen"

    assert c.post(f"/projects/{pid}/readiness").status_code == 200
    assert c.post(f"/projects/{pid}/baseline").status_code == 200
    pilot = c.post(f"/chats/{pid}/pilot", json={"target": 0.7})
    assert pilot.status_code == 200 and pilot.json()["eligible"], pilot.text
    assert c.post(f"/agreements/{pid}/quote").status_code == 200
    assert c.post(f"/projects/{pid}/quote/approve").status_code == 200
    order = c.post("/payments/orders", json={"project_id": pid}).json()
    assert order["approve_url"].startswith("http://localhost:3000/pay/return?token=")
    assert c.post(f"/payments/{order['payment_id']}/authorize").json()["held"] is True
    assert c.post(f"/projects/{pid}/train").status_code == 200
    run = c.get(f"/projects/{pid}/training").json()
    assert run["status"] == "done", run
    receipt = c.get(f"/payments/{order['payment_id']}").json()
    assert receipt["state"] in ("released", "fee_captured", "fee_skipped", "compute_captured", "voided")
