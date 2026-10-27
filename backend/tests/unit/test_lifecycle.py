import pytest

from app.services.lifecycle import BadTransition, transition


def test_cannot_skip_states(session, project):
    with pytest.raises(BadTransition):
        transition(session, project, "training")


def test_paid_requires_verified_payment(session, project):
    project.status = "awaiting_payment"
    session.commit()
    with pytest.raises(BadTransition):
        transition(session, project, "paid")


def test_side_exits(session, project):
    transition(session, project, "failed")
    transition(session, project, "refunded")
    assert project.status == "refunded"
