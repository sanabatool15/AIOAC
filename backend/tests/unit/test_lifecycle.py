import pytest

from app.services.lifecycle import BadTransition, transition


def test_cannot_skip_states(session, project):
    with pytest.raises(BadTransition):
        transition(session, project, "training")


def test_paid_requires_a_confirmed_hold(session, project):
    project.status = "awaiting_payment"
    session.commit()
    with pytest.raises(BadTransition):
        transition(session, project, "paid")


def test_side_exits(session, project):
    transition(session, project, "failed")
    transition(session, project, "voided")
    assert project.status == "voided"


def test_voided_only_from_failed_or_stopped(session, project):
    with pytest.raises(BadTransition):
        transition(session, project, "voided")


def test_improve_round_only_after_a_missed_target(session, project):
    from app.db.tables import TrainingRun
    from app.services.lifecycle import reopen_for_improvement
    project.status = "done"
    session.commit()
    with pytest.raises(BadTransition):
        reopen_for_improvement(session, project)  # no run at all
    session.add(TrainingRun(project_id=project.id, backend="x", status="done", result={"verification": {"passed": True}}))
    session.commit()
    with pytest.raises(BadTransition):
        reopen_for_improvement(session, project)  # the target was reached: nothing to improve
    run = session.query(TrainingRun).one()
    run.result = {"verification": {"passed": False}}
    session.commit()
    reopen_for_improvement(session, project)
    assert project.status == "baseline_done"
