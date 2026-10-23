import pytest

from app.repositories.ledger import LedgerRepository, NegativeBalance
from app.repositories.webhooks import WebhookRepository


def test_ledger_is_idempotent(session, project):
    led = LedgerRepository(session)
    assert led.append(project.id, "capture", 500, "CAP1")
    assert not led.append(project.id, "capture", 500, "CAP1")
    assert led.balance(project.id) == 500


def test_ledger_cannot_go_negative(session, project):
    led = LedgerRepository(session)
    led.append(project.id, "capture", 100, "CAP1")
    with pytest.raises(NegativeBalance):
        led.append(project.id, "refund", -101, "R1")
    assert led.balance(project.id) == 100


def test_ledger_has_no_update_or_delete():
    assert not [m for m in dir(LedgerRepository) if m.startswith(("update", "delete", "remove"))]


def test_webhook_recorded_once(session):
    wh = WebhookRepository(session)
    assert wh.record_once("E1", "t", {})
    assert not wh.record_once("E1", "t", {})
