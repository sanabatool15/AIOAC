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


def _finished(session, project, passed, target=0.94):
    from app.db.tables import TrainingRun
    project.status = "done"
    session.add(TrainingRun(project_id=project.id, backend="x", status="done",
                            result={"verification": {"passed": passed, "target": target, "value": 0.95}}))
    session.commit()


def test_higher_target_round_after_a_hit_needs_a_strictly_higher_target(session, project):
    from app.services.lifecycle import TargetNotHigher, reopen_for_improvement
    _finished(session, project, True)
    for bad in (None, 0.94, 0.9):
        with pytest.raises(TargetNotHigher):
            reopen_for_improvement(session, project, bad)
        assert project.status == "done"
    with pytest.raises(TargetNotHigher, match="94 out of 100"):
        reopen_for_improvement(session, project, 0.94)
    reopen_for_improvement(session, project, 0.99)
    assert project.status == "baseline_done"


def test_missed_target_improve_is_unchanged_with_or_without_a_target(session, project):
    from app.services.lifecycle import reopen_for_improvement
    _finished(session, project, False)
    reopen_for_improvement(session, project, 0.5)  # even a lower target: the old Improve rule
    assert project.status == "baseline_done"
