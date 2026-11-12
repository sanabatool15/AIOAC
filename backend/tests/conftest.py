import os
import sys
import tempfile

# Isolate from the developer's real .env, database and keys. This must run before `app` is imported,
# because app.config reads the environment once at import time and app.db builds its engine from it.
# The one exception: `RUN_REAL=1 pytest tests/integration ...` (every path argument under tests/integration) keeps the real
# environment and .env, because those tests exist to talk to the real services. Any other run, even with
# RUN_REAL=1 set, stays isolated and the integration tests skip themselves.
_PATH_ARGS = [a for a in sys.argv[1:] if not a.startswith("-") and ("/" in a or "\\" in a or a.endswith(".py"))]
REAL_MODE = (os.environ.get("RUN_INTEGRATION") == "1" or os.environ.get("RUN_REAL") == "1") and bool(_PATH_ARGS) and all(
    a.replace("\\", "/").split("::")[0].rstrip("/").split("tests/")[-1].startswith(("integration", "real")) for a in _PATH_ARGS)

if REAL_MODE:
    from pathlib import Path
    from dotenv import load_dotenv
    _env_file = Path(__file__).resolve().parent / ".env"
    load_dotenv(_env_file)
    load_dotenv()

if not REAL_MODE:
    _TMP = tempfile.mkdtemp(prefix="aioac-tests-")
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{_TMP}/test.db",
        "STORAGE_DIR": f"{_TMP}/storage",
        "PAYMENT_PROVIDER": "mock",  # only a label stored on payments; the double below is what is injected
        "TRAINING_BACKEND": "local",
        "JOB_RUNNER": "inline",
        "LLM_PROVIDER": "openrouter",
        "OPENROUTER_API_KEY": "", "AZURE_OPENAI_API_KEY": "", "AZURE_OPENAI_BASE_URL": "", "AZURE_OPENAI_MODEL": "",
        "HF_TOKEN": "", "PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": "", "PAYPAL_WEBHOOK_ID": "",
        "SECRET_KEY": "test-only-secret-key-not-for-real-use-0123456789", "DEMO_LOGIN_ENABLED": "false",
        "INNGEST_EVENT_KEY": "", "INNGEST_SIGNING_KEY": "", "SAGEMAKER_BUCKET": "", "SAGEMAKER_ROLE_ARN": "",
    })
    os.environ["AIOAC_TEST_ISOLATED"] = "1"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.db.tables import Organization, Project, User
from doubles.payments import MockPaymentProvider
from app.integrations.storage.local import LocalStorage
from app.services.data.samples import churn_csv
from app.services.data import datasets


def make_user(s, email="default@example.test") -> User:
    """A user in its own organization (the test double of signing up; no password is checked)."""
    org = Organization(name=f"{email} (personal)")
    s.add(org)
    s.flush()
    u = User(email=email, password_hash="not-a-real-hash", org_id=org.id)
    s.add(u)
    s.commit()
    return u


@pytest.fixture
def session():
    e = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    with sessionmaker(e, expire_on_commit=False)() as s:
        yield s


@pytest.fixture
def user(session):
    """The default signed-in user of API tests that use the `session` fixture."""
    return make_user(session)


@pytest.fixture(autouse=True)
def _signed_in(request):
    """Existing API tests run as `user` without a cookie: current_user is overridden for them. Tests that exercise
    real login (tests/e2e/test_tenant_isolation.py, test_auth.py) set `pytestmark = pytest.mark.real_auth` to opt out."""
    if "real_auth" in request.keywords or "session" not in request.fixturenames:
        yield
        return
    from app.deps import current_user
    from app.main import app
    u = request.getfixturevalue("user")
    from tests.helpers import auth
    auth.DEFAULT["user"] = u
    app.dependency_overrides[current_user] = lambda: u
    yield
    app.dependency_overrides.pop(current_user, None)


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(str(tmp_path / "store"))


@pytest.fixture
def provider():
    return MockPaymentProvider()


@pytest.fixture
def project(session, user):
    p = Project(goal="predict which customers leave. I have no data.", user_id=user.id, org_id=user.org_id)
    session.add(p)
    session.commit()
    return p


@pytest.fixture
def chosen(session, storage, project):
    """Project with the synthetic churn dataset chosen."""
    c = datasets.add_candidate(session, storage, project, "churn", "bundled", churn_csv(1500))
    datasets.select_candidate(session, storage, project, c.id, "left")
    return project


@pytest.fixture(autouse=True)
def _payment_double(monkeypatch):
    """The app only builds the real PayPal provider. Tests get the in-memory double instead: every module that
    imported `get_payment_provider` is patched to return one shared MockPaymentProvider for the test."""
    double = MockPaymentProvider()
    for name, mod in list(sys.modules.items()):
        if name.startswith("app.") and hasattr(mod, "get_payment_provider"):
            monkeypatch.setattr(mod, "get_payment_provider", lambda: double)
    return double


@pytest.fixture
def verdict(monkeypatch):
    """Replaces the locked-test-set check with a chosen result, for tests that use a scripted backend whose
    'model' is not a real file. Set verdict['value'] (default 0.9, above the 0.8 target) or verdict['error']."""
    from app.services.data import verification
    box = {"value": 0.9, "error": None, "calls": 0}

    def fake(model_bytes, storage, locked_key, target, *args, **kw):
        box["calls"] += 1
        if box["error"]:
            raise verification.VerificationError(box["error"])
        return {"metric": "accuracy", "value": box["value"], "rows": 100}

    monkeypatch.setattr(verification, "verify_model", fake)
    return box


def pytest_collection_modifyitems(config, items):
    """Everything under tests/integration carries the `real` marker (select with `-m real`)."""
    for item in items:
        if any(k in str(item.fspath).replace("\\", "/") for k in ("/tests/integration/", "/tests/real/")):
            item.add_marker(pytest.mark.real)
