"""The guided data fix: whitelist, proposal without side effects, child version, locked rows that never change."""
import io

import numpy as np
import pandas as pd
import pytest

from app.config import settings
from app.db.tables import DatasetVersion
from app.repositories import datasets as datasets_repo
from app.repositories import quotes as quotes_repo
from app.services.data import analysis, datasets, fixes, verification
from app.services.data.samples import churn_csv
from tests.helpers.builders import make_quote


def messy_csv(rows=1500, dups=60, empty_share=0.8) -> bytes:
    df = pd.read_csv(io.BytesIO(churn_csv(rows)))
    rng = np.random.default_rng(0)
    df["notes_col"] = np.where(rng.random(len(df)) < empty_share, np.nan, rng.random(len(df)))  # mostly empty
    df = pd.concat([df, df.sample(dups, random_state=1)], ignore_index=True)  # exact repeats
    return df.to_csv(index=False).encode()


@pytest.fixture
def messy(session, storage, project):
    c = datasets.add_candidate(session, storage, project, "messy", "bundled", messy_csv())
    datasets.select_candidate(session, storage, project, c.id, "left")
    analysis.readiness(session, storage, project)
    analysis.baseline(session, storage, project)
    assert project.status == "baseline_done"
    return project


def test_propose_reads_only_and_shows_before_and_after(session, storage, messy):
    before = (messy.chosen_dataset_version_id, messy.status, datasets_repo.count_versions(session, messy.id), set(storage.list("datasets")))
    p = fixes.propose_fix(session, storage, messy)
    assert p.available and p.rows_removed >= 60 and p.columns_dropped == ["notes_col"]
    assert p.rows_after == p.rows_before - p.rows_removed and p.columns_after == p.columns_before - 1
    assert {s["kind"] for s in p.steps} <= set(fixes.KINDS) and all(s["why"] for s in p.steps)
    assert "not" in p.note.lower() or "may not" in p.note.lower()
    assert before == (messy.chosen_dataset_version_id, messy.status, datasets_repo.count_versions(session, messy.id), set(storage.list("datasets")))


def test_nothing_to_fix_is_said_plainly(session, storage, project):
    clean = pd.read_csv(io.BytesIO(churn_csv(1000))).drop_duplicates()
    c = datasets.add_candidate(session, storage, project, "clean", "bundled", clean.to_csv(index=False).encode())
    datasets.select_candidate(session, storage, project, c.id, "left")
    chosen = project
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    p = fixes.propose_fix(session, storage, chosen)
    assert not p.available and "nothing" in p.message.lower()
    with pytest.raises(fixes.FixError):
        fixes.apply_fix(session, storage, chosen)


def test_apply_makes_a_child_version_and_sends_the_project_back_to_the_free_steps(session, storage, messy):
    root = datasets_repo.get_version(session, messy.chosen_dataset_version_id)
    q = make_quote(session, messy, approved=False)
    child, proposal = fixes.apply_fix(session, storage, messy, expected_version_id=root.id)
    assert child.parent_id == root.id and child.notes and child.rows == proposal.rows_after and child.columns == proposal.columns_after
    assert messy.chosen_dataset_version_id == child.id
    assert messy.status == "baseline_done"                       # readiness and the free test were re-run on the new data
    assert datasets_repo.get_version(session, root.id).rows == root.rows   # the original is untouched
    assert pd.read_csv(io.BytesIO(storage.get(root.storage_key))).shape[1] == root.columns
    assert analysis_report_for(session, child) is not None
    session.refresh(q)
    assert quotes_repo.latest_for_project(session, messy.id).expires_at <= q.expires_at   # the old price is no longer valid
    from datetime import datetime, timezone
    exp = q.expires_at if q.expires_at.tzinfo else q.expires_at.replace(tzinfo=timezone.utc)
    assert exp <= datetime.now(timezone.utc)


def analysis_report_for(session, version):
    from app.repositories import analysis as repo
    return repo.latest_insight_report(session, version.id)


def test_apply_refuses_when_the_data_moved_on_since_the_proposal(session, storage, messy):
    with pytest.raises(fixes.FixError, match="changed"):
        fixes.apply_fix(session, storage, messy, expected_version_id="an-older-version")


def test_apply_only_before_paying(session, storage, messy):
    messy.status = "awaiting_payment"
    session.commit()
    with pytest.raises(fixes.FixError):
        fixes.apply_fix(session, storage, messy)


def test_at_most_three_fixes_per_project(session, storage, messy, monkeypatch):
    monkeypatch.setattr(settings, "max_fixes_per_project", 1)
    fixes.apply_fix(session, storage, messy)
    assert fixes.fixes_used(session, messy.id) == 1
    # make more mess so a second fix would be possible, then see the limit speak
    v = datasets_repo.get_version(session, messy.chosen_dataset_version_id)
    p = fixes.propose_fix(session, storage, messy)
    assert not p.available and p.fixes_left == 0 and "most we try" in p.message
    with pytest.raises(fixes.FixError):
        fixes.apply_fix(session, storage, messy)
    assert v.id == messy.chosen_dataset_version_id


def test_the_answer_column_is_never_dropped(session, storage, project):
    df = pd.read_csv(io.BytesIO(churn_csv(800)))
    df.loc[df.sample(frac=0.7, random_state=0).index, "left"] = np.nan  # the answer itself is mostly empty
    df["mostly"] = np.nan
    c = datasets.add_candidate(session, storage, project, "x", "bundled", df.to_csv(index=False).encode())
    datasets.select_candidate(session, storage, project, c.id, "left")
    p = fixes.propose_fix(session, storage, project)
    assert "left" not in p.columns_dropped and p.columns_dropped == ["mostly"]


# ---- the locked rows -------------------------------------------------------------------------------------
def lock_sets(storage, version_id):
    wk, lk = verification.split_keys(version_id)
    return pd.read_csv(storage.path(wk)), pd.read_csv(storage.path(lk))


def test_a_childs_locked_rows_are_the_parents_and_none_lands_in_its_work_set(session, storage, messy):
    root = datasets_repo.get_version(session, messy.chosen_dataset_version_id)
    verification.split_for(session, storage, root)
    root_work, root_locked = lock_sets(storage, root.id)
    child, _ = fixes.apply_fix(session, storage, messy)
    verification.split_for(session, storage, child)
    work, locked = lock_sets(storage, child.id)
    cols = list(locked.columns)
    assert "notes_col" not in cols and set(cols) < set(root_locked.columns)
    # the locked rows are the root's locked rows, restricted to the columns the child keeps
    assert sorted(verification.row_keys(locked, cols)) == sorted(verification.row_keys(root_locked.drop_duplicates(subset=cols), cols))
    # no locked row is in the work set (compared on the kept columns), and the work set only shrank
    assert not set(verification.row_keys(work, cols)) & set(verification.row_keys(locked, cols))
    assert len(work) <= len(root_work)


def test_the_split_is_inherited_through_a_chain_of_versions(session, storage, messy, monkeypatch):
    monkeypatch.setattr(settings, "max_fixes_per_project", 3)
    root = datasets_repo.get_version(session, messy.chosen_dataset_version_id)
    verification.split_for(session, storage, root)
    _, root_locked = lock_sets(storage, root.id)
    child, _ = fixes.apply_fix(session, storage, messy)
    # a second version made by hand from the child (as a later fix would): grandchild of the root
    grand = datasets_repo.add_version(session, project_id=messy.id, parent_id=child.id, storage_key=child.storage_key, rows=child.rows,
                                      columns=child.columns, target_column=child.target_column, source=child.source, license=child.license, notes="same")
    verification.split_for(session, storage, grand)
    work, locked = lock_sets(storage, grand.id)
    cols = list(locked.columns)
    assert set(verification.row_keys(locked, cols)) == set(verification.row_keys(root_locked, cols))
    assert not set(verification.row_keys(work, cols)) & set(verification.row_keys(locked, cols))


def test_a_root_split_is_unchanged_by_the_new_code(session, storage, chosen):
    v = datasets_repo.get_version(session, chosen.chosen_dataset_version_id)
    a = verification.split_for(session, storage, v)
    assert a == verification.split_keys(v.id)
    assert isinstance(v, DatasetVersion) and v.parent_id is None
