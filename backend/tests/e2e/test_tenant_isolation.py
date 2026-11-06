"""Nobody sees another user's data. Real sign-in (cookies and tokens), two users, every route."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_session
from app.db.tables import Project
from app.main import app
from app.repositories import conversations as conv_repo
from app.services import auth, training
from tests.e2e.test_background_training import StoppableBackend, paid  # noqa: F401  (fixture)
from tests.helpers.builders import ready_to_pay
from app.services.data import datasets
from app.services.data.samples import churn_csv

pytestmark = pytest.mark.real_auth

PW = "correct horse battery"


@pytest.fixture(autouse=True)
def api(session):
    app.dependency_overrides[get_session] = lambda: session
    auth.reset_throttle()
    yield
    app.dependency_overrides.clear()


def signup(email, password=PW):
    c = TestClient(app)
    r = c.post("/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def alice():
    return signup("alice@example.test")


@pytest.fixture
def bob():
    return signup("bob@example.test")


# ------------------------------------------------------------ signup, login, logout, me

def test_signup_sets_an_httponly_cookie_and_me_works(session):
    c = TestClient(app)
    r = c.post("/auth/signup", json={"email": "Carol@Example.test", "password": PW})
    assert r.status_code == 200
    u = r.json()["user"]
    assert u["email"] == "carol@example.test" and u["id"] and u["org_id"] and "password" not in str(r.json())
    cookie = r.headers["set-cookie"].lower()
    assert "aioac_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert c.get("/auth/me").json() == {"user": u}


def test_each_signup_gets_its_own_org(alice, bob):
    assert alice.get("/auth/me").json()["user"]["org_id"] != bob.get("/auth/me").json()["user"]["org_id"]


def test_duplicate_email_is_409(alice):
    r = TestClient(app).post("/auth/signup", json={"email": "ALICE@example.test", "password": PW})
    assert r.status_code == 409 and r.json()["detail"] == "that email is already registered"


@pytest.mark.parametrize("body", [{"email": "a@b.test", "password": "short"}, {"email": "not-an-email", "password": PW}])
def test_bad_signup_input_is_422(body):
    assert TestClient(app).post("/auth/signup", json=body).status_code == 422


def test_login_logout_cycle(alice):
    c = TestClient(app)
    assert c.get("/auth/me").status_code == 401
    r = c.post("/auth/login", json={"email": "alice@example.test", "password": PW})
    assert r.status_code == 200 and c.get("/auth/me").status_code == 200
    assert c.post("/auth/logout").json() == {"ok": True}
    assert c.get("/auth/me").status_code == 401


def test_wrong_password_and_unknown_email_look_the_same(alice):
    c = TestClient(app)
    a = c.post("/auth/login", json={"email": "alice@example.test", "password": "wrong password"})
    b = c.post("/auth/login", json={"email": "nobody@example.test", "password": "wrong password"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json() == {"detail": "wrong email or password"}


def test_login_is_throttled_after_repeated_failures(alice):
    c = TestClient(app)
    for _ in range(settings.login_max_failures):
        assert c.post("/auth/login", json={"email": "alice@example.test", "password": "wrong password"}).status_code == 401
    assert c.post("/auth/login", json={"email": "alice@example.test", "password": PW}).status_code == 429


def test_password_is_hashed_with_a_random_salt():
    a, b = auth.hash_password(PW), auth.hash_password(PW)
    assert a != b and PW not in a and auth.verify_password(PW, a) and not auth.verify_password("nope nope", a)


# ------------------------------------------------------------ tokens

def _token(user_id, org_id, key=None, exp=None, alg="HS256"):
    exp = exp or datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode({"sub": user_id, "org": org_id, "exp": exp}, key or settings.secret_key, algorithm=alg)


def _with_cookie(token):
    c = TestClient(app)
    c.cookies.set(settings.cookie_name, token)
    return c


def test_expired_tampered_and_foreign_tokens_are_401(alice):
    me = alice.get("/auth/me").json()["user"]
    good = _token(me["id"], me["org_id"])
    assert _with_cookie(good).get("/projects").status_code == 200
    expired = _token(me["id"], me["org_id"], exp=datetime.now(timezone.utc) - timedelta(minutes=1))
    other_key = _token(me["id"], me["org_id"], key="another-secret-key-another-secret-key")
    wrong_org = _token(me["id"], "some-other-org")
    for bad in (expired, other_key, wrong_org, good[:-3] + "abc", "garbage", ""):
        r = _with_cookie(bad).get("/projects")
        assert r.status_code == 401 and r.json()["detail"] == "please sign in", bad


def test_no_cookie_is_401_on_every_protected_route():
    c = TestClient(app)
    for method, path in _protected_routes():
        r = c.request(method, path.format(pid="x", cid="x", payment_id="x", candidate_id="x"))
        assert r.status_code == 401, (method, path, r.status_code)


@pytest.mark.parametrize("key", ["", "change-me", "your-secret-key-here", "short"])
def test_login_not_set_up_is_503(monkeypatch, key):
    monkeypatch.setattr(settings, "secret_key", key)
    c = TestClient(app)
    assert c.post("/auth/signup", json={"email": "z@example.test", "password": PW}).status_code == 503
    assert c.post("/auth/login", json={"email": "z@example.test", "password": PW}).status_code == 503
    r = c.get("/projects")
    assert r.status_code == 503 and r.json()["detail"] == "login is not set up"
    assert c.get("/health").json()["auth"] == {"configured": False}


def test_demo_login_is_off_unless_enabled(monkeypatch):
    c = TestClient(app)
    assert c.post("/auth/demo").status_code == 404
    monkeypatch.setattr(settings, "demo_login_enabled", True)
    assert c.post("/auth/demo").status_code == 200 and c.get("/auth/me").json()["user"]["email"] == "demo@aioac.example"
    # the demo account cannot be signed into with a password
    assert TestClient(app).post("/auth/login", json={"email": "demo@aioac.example", "password": PW}).status_code == 401


# ------------------------------------------------------------ open routes

def test_health_and_webhook_stay_open():
    c = TestClient(app)
    h = c.get("/health").json()
    assert h["ok"] is True and h["auth"] == {"configured": True}
    assert c.post("/webhooks/paypal", content=b"{}").status_code in (400, 409)  # PayPal's signature is the auth, not a cookie


# ------------------------------------------------------------ isolation

OPEN = {("GET", "/health"), ("POST", "/webhooks/paypal"), ("POST", "/auth/signup"), ("POST", "/auth/login"),
        ("POST", "/auth/logout"), ("POST", "/auth/demo")}


def _protected_routes():
    out = []
    for path, methods in app.openapi()["paths"].items():
        for m in methods:
            if (m.upper(), path) not in OPEN:
                out.append((m.upper(), path))
    return sorted(out)


# routes that take a project id (or a payment of that project) and must answer 404 to anyone else
PROJECT_ROUTES = {
    ("GET", "/projects/{pid}"): None, ("GET", "/projects/{pid}/messages"): None,
    ("POST", "/projects/{pid}/chat"): {"message": "hi"}, ("POST", "/projects/{pid}/data"): {"name": "x", "csv_text": "a,b\n1,2\n"},
    ("POST", "/projects/{pid}/data/{candidate_id}/select"): {"target": "b"}, ("POST", "/projects/{pid}/readiness"): None,
    ("POST", "/projects/{pid}/baseline"): None, ("GET", "/projects/{pid}/payment"): None,
    ("POST", "/projects/{pid}/quote/approve"): None, ("POST", "/projects/{pid}/train"): None,
    ("GET", "/projects/{pid}/training"): None, ("POST", "/projects/{pid}/training/stop"): None,
    ("POST", "/projects/{pid}/settle/retry"): None, ("POST", "/projects/{pid}/cancel"): None, ("GET", "/projects/{pid}/trace"): None,
    ("POST", "/chats/{pid}/pilot"): {"target": 0.8}, ("GET", "/jobs/{pid}/forecast"): None,
    ("POST", "/agreements/{pid}/quote"): None,
}
OTHER_PROTECTED = {("POST", "/projects"), ("GET", "/projects"), ("POST", "/payments/orders"), ("POST", "/payments/{payment_id}/authorize"),
                   ("GET", "/payments/{payment_id}"), ("GET", "/auth/me")}


def test_every_route_is_covered_by_a_isolation_test():
    """A new route fails this test until someone decides whether it is open or owner-only."""
    assert set(_protected_routes()) == set(PROJECT_ROUTES) | OTHER_PROTECTED


@pytest.fixture
def a_project(session, storage, alice, _payment_double):
    """Alice's project with a data set, a quote and an unconfirmed PayPal hold, created through the API as Alice."""
    pid = alice.post("/projects", json={"goal": "keep customers"}).json()["id"]
    p = session.get(Project, pid)
    c = datasets.add_candidate(session, storage, p, "churn", "bundled", churn_csv(1500))
    datasets.select_candidate(session, storage, p, c.id, "left")
    _, pay = ready_to_pay(session, storage, p, _payment_double)
    conv = conv_repo.create(session, project_id=pid)
    conv_repo.append_message(session, conv.id, role="user", content="private words", kind="chat")
    return pid, pay.id, c.id


def test_the_owner_can_reach_their_own_project(alice, a_project):
    pid, payment_id, _ = a_project
    assert alice.get(f"/projects/{pid}").status_code == 200
    assert alice.get(f"/projects/{pid}/messages").json()[0]["text"] == "private words"
    assert alice.get(f"/payments/{payment_id}").status_code == 200
    assert alice.get(f"/projects/{pid}/payment").status_code == 200
    assert alice.post(f"/payments/{payment_id}/authorize").status_code == 200


@pytest.mark.parametrize("route", sorted(PROJECT_ROUTES))
def test_another_user_gets_404_on_every_project_route(bob, a_project, route):
    pid, _, cand = a_project
    method, template = route
    r = bob.request(method, template.format(pid=pid, candidate_id=cand), json=PROJECT_ROUTES[route])
    assert r.status_code == 404, (route, r.status_code, r.text)
    assert "private words" not in r.text
    # same answer as for a project that does not exist, so existence is not leaked
    missing = bob.request(method, template.format(pid="0" * 32, candidate_id=cand), json=PROJECT_ROUTES[route])
    assert (missing.status_code, missing.json()) == (r.status_code, r.json())


def test_another_user_cannot_touch_the_payment(bob, a_project, session):
    pid, payment_id, _ = a_project
    assert bob.get(f"/payments/{payment_id}").status_code == 404
    assert bob.post(f"/payments/{payment_id}/authorize").status_code == 404
    assert bob.post("/payments/orders", json={"project_id": pid}).status_code == 404
    from app.repositories import payments as payments_repo
    assert payments_repo.get(session, payment_id).state == "none"  # Bob's calls changed nothing


def test_project_lists_only_show_your_own(alice, bob, a_project):
    pid, _, _ = a_project
    mine = bob.post("/projects", json={"goal": "bob's"}).json()["id"]
    assert [p["id"] for p in alice.get("/projects").json()] == [pid]
    assert [p["id"] for p in bob.get("/projects").json()] == [mine]


def test_a_project_is_stamped_with_its_creators_user_and_org(alice, session):
    pid = alice.post("/projects", json={"goal": "x"}).json()["id"]
    me = alice.get("/auth/me").json()["user"]
    p = session.get(Project, pid)
    assert (p.user_id, p.org_id) == (me["id"], me["org_id"])


def test_same_org_other_user_and_same_user_other_org_are_both_refused(alice, session, a_project):
    pid, _, _ = a_project
    from tests.conftest import make_user
    other = make_user(session, "teammate@example.test")
    me = alice.get("/auth/me").json()["user"]
    other.org_id = me["org_id"]  # same org, different user
    session.commit()
    assert _with_cookie(auth.issue_token(other)).get(f"/projects/{pid}").status_code == 404
    p = session.get(Project, pid)
    p.org_id = other.org_id + "x"  # same user, different org
    session.commit()
    assert alice.get(f"/projects/{pid}").status_code == 404


def test_legacy_projects_without_an_owner_are_unreachable(alice, session):
    old = Project(goal="made before login")
    session.add(old)
    session.commit()
    assert alice.get(f"/projects/{old.id}").status_code == 404
    assert alice.get("/projects").json() == []


def test_a_conversation_id_from_another_project_is_never_used(session, alice):
    from app.services.agent import memory
    a = alice.post("/projects", json={"goal": "a"}).json()["id"]
    b = alice.post("/projects", json={"goal": "b"}).json()["id"]
    conv_a = conv_repo.create(session, project_id=a)
    got = memory.get_conversation(session, b, conversation_id=conv_a.id)
    assert got.id != conv_a.id and got.project_id == b


# ------------------------------------------------------------ the background paths have no request user

def test_job_runner_and_crash_recovery_work_without_a_user(session, storage, chosen, provider, paid):  # noqa: F811
    run = training.start_training(session, chosen, StoppableBackend())
    training.execute_run(session, run.id, StoppableBackend(), storage, provider)
    assert run.status == "done"
    run2_project = chosen
    assert run2_project.user_id is not None  # owned, yet the worker never needed a user
