from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app


def test_api_basics(session):
    app.dependency_overrides[get_session] = lambda: session
    c = TestClient(app)
    assert c.get("/health").json() == {"ok": True}
    pid = c.post("/projects", json={"goal": "predict churn"}).json()["id"]
    assert c.get(f"/projects/{pid}").json()["status"] == "described"
    # paying or training before a quote exists is refused
    assert c.post("/payments/orders", json={"project_id": pid}).status_code == 403
    assert c.post(f"/projects/{pid}/train").status_code == 403
    assert c.post("/webhooks/paypal", content=b"{}").status_code in (400, 500)
    app.dependency_overrides.clear()
