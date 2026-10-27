import os
import sys
import tempfile

# Isolate from the developer's real .env, database and keys. This must run before `app` is imported,
# because app.config reads the environment once at import time and app.db builds its engine from it.
# The one exception: `RUN_REAL=1 pytest tests/real ...` (every path argument under tests/real) keeps the real
# environment and .env, because those tests exist to talk to the real services. Any other run, even with
# RUN_REAL=1 set, stays isolated and the real tests skip themselves.
_PATH_ARGS = [a for a in sys.argv[1:] if not a.startswith("-") and ("/" in a or "\\" in a or a.endswith(".py"))]
REAL_MODE = os.environ.get("RUN_REAL") == "1" and bool(_PATH_ARGS) and all(
    a.replace("\\", "/").split("::")[0].rstrip("/").split("tests/")[-1].startswith("real") for a in _PATH_ARGS)

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
        "INNGEST_EVENT_KEY": "", "INNGEST_SIGNING_KEY": "", "SAGEMAKER_BUCKET": "", "SAGEMAKER_ROLE_ARN": "",
    })
    os.environ["AIOAC_TEST_ISOLATED"] = "1"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.db.tables import Project
from doubles.payments import MockPaymentProvider
from app.integrations.storage.local import LocalStorage
from app.integrations.training_local.backend import LocalBackend
from app.services.data.samples import churn_csv
from app.services.data import datasets


@pytest.fixture
def session():
    e = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    with sessionmaker(e, expire_on_commit=False)() as s:
        yield s


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(str(tmp_path / "store"))


@pytest.fixture
def provider():
    return MockPaymentProvider()


@pytest.fixture
def project(session):
    p = Project(goal="predict which customers leave")
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


def pytest_collection_modifyitems(config, items):
    """Everything under tests/real carries the `real` marker (select with `-m real`)."""
    for item in items:
        if "/tests/real/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.real)
