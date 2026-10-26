import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Project
from app.providers.payments.mock import MockPaymentProvider
from app.providers.storage.local import LocalStorage
from app.providers.training.local import LocalBackend
from app.samples import churn_csv
from app.services import datasets


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


@pytest.fixture
def verdict(monkeypatch):
    """Replaces the locked-test-set check with a chosen result, for tests that use a scripted backend whose
    'model' is not a real file. Set verdict['value'] (default 0.9, above the 0.8 target) or verdict['error']."""
    from app.services import verify
    box = {"value": 0.9, "error": None, "calls": 0}

    def fake(model_bytes, storage, locked_key, target):
        box["calls"] += 1
        if box["error"]:
            raise verify.VerificationError(box["error"])
        return {"metric": "accuracy", "value": box["value"], "rows": 100}

    monkeypatch.setattr(verify, "verify_model", fake)
    return box
