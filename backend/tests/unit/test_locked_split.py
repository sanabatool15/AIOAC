"""The locked test rows belong to the ROOT dataset version; children inherit them (HUMAN REVIEW: verification)."""
import io

import numpy as np
import pandas as pd

from app.repositories import datasets as datasets_repo
from app.services.data import datasets, verification
from app.services.data.samples import churn_csv


def make_child(session, storage, project, parent, df, note="test child"):
    key = f"datasets/{project.id}/v{datasets_repo.count_versions(session, project.id) + 1}.csv"
    storage.put(key, df.to_csv(index=False).encode())
    return datasets_repo.add_version(session, project_id=project.id, parent_id=parent.id, storage_key=key, rows=len(df),
                                     columns=df.shape[1], target_column=parent.target_column, source=parent.source,
                                     license=parent.license, notes=note)


def sets(storage, version):
    wk, lk = verification.split_keys(version.id)
    return pd.read_csv(storage.path(wk)), pd.read_csv(storage.path(lk))


def test_child_with_fewer_rows_and_columns_keeps_the_roots_locked_rows(session, storage, project):
    df = pd.read_csv(io.BytesIO(churn_csv(1200)))
    df["sparse"] = np.where(np.arange(len(df)) % 5 == 0, 1.0, np.nan)
    c = datasets.add_candidate(session, storage, project, "d", "bundled", df.to_csv(index=False).encode())
    root = datasets.select_candidate(session, storage, project, c.id, "left")
    verification.split_for(session, storage, root)
    root_work, root_locked = sets(storage, root)

    smaller = df.drop(columns=["sparse"]).sample(frac=0.8, random_state=3)    # lost 20% of its rows and a column
    child = make_child(session, storage, project, root, smaller)
    verification.split_for(session, storage, child)
    work, locked = sets(storage, child)
    cols = list(locked.columns)
    root_keys = set(verification.row_keys(root_locked, cols))
    # every locked row of the child is a locked row of the root, and no work row is locked content
    assert set(verification.row_keys(locked, cols)) <= root_keys
    assert not set(verification.row_keys(work, cols)) & root_keys
    # the rows of the root's locked set that are still present in the child are exactly the child's locked rows
    present = set(verification.row_keys(smaller.drop_duplicates(), cols)) & root_keys
    assert set(verification.row_keys(locked, cols)) == present
    assert len(work) < len(root_work)   # the work set shrank, the locked rows did not move


def test_child_with_the_same_rows_has_identical_locked_rows(session, storage, project):
    df = pd.read_csv(io.BytesIO(churn_csv(900)))
    c = datasets.add_candidate(session, storage, project, "d", "bundled", df.to_csv(index=False).encode())
    root = datasets.select_candidate(session, storage, project, c.id, "left")
    verification.split_for(session, storage, root)
    _, root_locked = sets(storage, root)
    child = make_child(session, storage, project, root, df)
    verification.split_for(session, storage, child)
    _, locked = sets(storage, child)
    cols = list(root_locked.columns)
    assert sorted(verification.row_keys(locked, cols)) == sorted(verification.row_keys(root_locked, cols))


def test_a_missing_value_is_part_of_a_rows_key(session, storage, project):
    a = pd.DataFrame({"x": [1.0, np.nan], "y": ["a", "a"]})
    assert verification.row_keys(a, ["x", "y"]).nunique() == 2
    assert verification.row_keys(pd.DataFrame({"x": [np.nan, np.nan], "y": ["a", "a"]}), ["x", "y"]).nunique() == 1
