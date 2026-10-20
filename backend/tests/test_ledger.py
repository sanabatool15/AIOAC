from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Job
from app.repositories.ledger import LedgerRepository
from app.repositories.webhooks import WebhookRepository
from app.services.cost import estimate_cost_cents


def session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(e)()
    s.add(Job(id="j1", description="x"))
    s.commit()
    return s


def test_ledger_is_idempotent():
    s = session()
    led = LedgerRepository(s)
    assert led.append("j1", "capture", 500, "CAP1")
    assert not led.append("j1", "capture", 500, "CAP1")
    assert led.balance("j1") == 500


def test_webhook_recorded_once():
    s = session()
    wh = WebhookRepository(s)
    assert wh.record_once("E1", "t", {})
    assert not wh.record_once("E1", "t", {})


def test_cost_estimate_includes_fees():
    assert estimate_cost_cents(0, 1, 1, "ml.m5.large") == 51
