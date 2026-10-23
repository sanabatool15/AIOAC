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
