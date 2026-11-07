"""Model versions: repository on SQLite, the current-model rule, and old rows without any version data."""
import pytest

from app.db.tables import Model
from app.integrations.training_local.backend import LocalBackend
from app.repositories import training_runs as runs_repo
from app.services import training
from app.services.data import models as mv
from tests.helpers.builders import held


def add(session, project, n, value=None, passed=None, **kw):
    """A model row with the given verification result. Run ids are not checked on SQLite."""
    q = {"verification": {"value": value, "target": 0.8, "passed": passed}} if value is not None else {}
    return runs_repo.add_model(session, project.id, f"run{n}", f"models/{n}", q, **kw)


def test_models_for_project_is_oldest_first_and_scoped(session, project):
    a, b = add(session, project, 1), add(session, project, 2)
    assert [m.id for m in runs_repo.models_for_project(session, project.id)] == [a.id, b.id]
    assert runs_repo.models_for_project(session, "someone-else") == []
    assert runs_repo.get_model(session, project.id, a.id).id == a.id
    assert runs_repo.get_model(session, "someone-else", a.id) is None


def test_old_rows_without_a_flag_use_the_newest_as_current_and_number_by_creation(session, project):
    a, b, c = add(session, project, 1), add(session, project, 2), add(session, project, 3)
    assert runs_repo.current_model(session, project.id).id == c.id
    assert mv.version_numbers(runs_repo.models_for_project(session, project.id)) == {a.id: 1, b.id: 2, c.id: 3}
    assert runs_repo.next_version_no(session, project.id) == 4


def test_set_current_is_exclusive(session, project):
    a, b = add(session, project, 1, is_current=True), add(session, project, 2)
    assert runs_repo.current_model(session, project.id).id == a.id  # the flag wins over "newest"
    runs_repo.set_current(session, project.id, b.id)
    session.refresh(a)
    session.refresh(b)
    assert (a.is_current, b.is_current) == (False, True)
    assert session.query(Model).filter_by(project_id=project.id, is_current=True).count() == 1


@pytest.mark.parametrize("cur_value,cur_passed,new_value,new_passed,promote", [
    (None, None, 0.7, False, True),        # first model
    (0.7, False, 0.9, True, True),         # new one passed, old one did not
    (0.9, True, 0.6, False, False),        # old one passed, new one did not
    (0.85, True, 0.82, True, False),       # both passed, new is worse: keep the better one
    (0.82, True, 0.85, True, True),        # both passed, new is better
    (0.85, True, 0.85, True, True),        # tie goes to the newer one
    (0.6, False, 0.5, False, False),       # neither passed: keep the best score
    (0.5, False, 0.6, False, True),
])
def test_should_promote(session, project, cur_value, cur_passed, new_value, new_passed, promote):
    cur = None if cur_value is None else add(session, project, 1, cur_value, cur_passed)
    assert mv.should_promote(cur, new_value, new_passed) is promote


def test_record_new_model_numbers_and_never_promotes_a_worse_model(session, project):
    r = {"verification": {"value": 0.9, "target": 0.8, "passed": True}}
    m1 = mv.record_new_model(session, project.id, "r1", "k1", r, "dv1", None, None)
    worse = {"verification": {"value": 0.82, "target": 0.8, "passed": True}}
    m2 = mv.record_new_model(session, project.id, "r2", "k2", worse, "dv1", None, None)
    session.refresh(m1)
    assert (m1.version_no, m2.version_no) == (1, 2)
    assert m1.is_current and not m2.is_current
    assert runs_repo.current_model(session, project.id).id == m1.id
    better = {"verification": {"value": 0.95, "target": 0.8, "passed": True}}
    m3 = mv.record_new_model(session, project.id, "r3", "k3", better, "dv1", None, None)
    session.refresh(m1)
    assert m3.is_current and not m1.is_current and m3.version_no == 3


def test_a_new_model_beside_old_rows_keeps_the_old_current_one_pinned(session, project):
    add(session, project, 1, 0.95, True)
    old2 = add(session, project, 2, 0.5, False)  # old rows, no flags
    assert runs_repo.current_model(session, project.id).id == old2.id  # fallback: newest
    worse = {"verification": {"value": 0.4, "target": 0.8, "passed": False}}
    m = mv.record_new_model(session, project.id, "r3", "k3", worse, None, None, None)
    assert m.version_no == 3  # numbering continues from the old rows
    assert runs_repo.current_model(session, project.id).id == old2.id  # 0.5 beats 0.4, and is now pinned
    session.refresh(old2)
    assert old2.is_current


def test_a_real_run_gets_its_version_fields(session, storage, chosen, provider):
    held(session, storage, chosen, provider)
    run = training.run_training(session, chosen, LocalBackend(), storage, provider)
    row = runs_repo.current_model(session, chosen.id)
    assert row.version_no == 1 and row.is_current and row.dataset_version_id == chosen.chosen_dataset_version_id
    assert row.quote_id and row.verified_value == run.result["verification"]["value"] and row.passed is not None
    assert run.dataset_version_id == chosen.chosen_dataset_version_id
