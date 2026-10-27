from datetime import datetime, timedelta, timezone

import pytest

from app.services.data.samples import churn_csv
from app.services.data import datasets


def test_select_keeps_one_and_deletes_the_rest(session, storage, project):
    a = datasets.add_candidate(session, storage, project, "a", "bundled", churn_csv(500, 1))
    b = datasets.add_candidate(session, storage, project, "b", "bundled", churn_csv(500, 2))
    datasets.select_candidate(session, storage, project, a.id, "left")
    assert storage.list("candidates") == []
    assert len(storage.list("datasets")) == 1
    assert (a.status, b.status) == ("chosen", "discarded")
    assert project.status == "data_chosen"


def test_unknown_target_is_rejected(session, storage, project):
    c = datasets.add_candidate(session, storage, project, "a", "bundled", churn_csv(300))
    with pytest.raises(datasets.DatasetError):
        datasets.select_candidate(session, storage, project, c.id, "nope")


def test_unreadable_csv_is_rejected(session, storage, project):
    with pytest.raises(datasets.DatasetError):
        datasets.add_candidate(session, storage, project, "bad", "upload", b"")


def test_expired_candidates_are_purged(session, storage, project):
    c = datasets.add_candidate(session, storage, project, "a", "bundled", churn_csv(300))
    later = datetime.now(timezone.utc) + timedelta(days=3)
    assert datasets.purge_expired(session, storage, now=later) == 1
    assert storage.list("candidates") == [] and c.status == "discarded"


def test_orphan_report(session, storage, project):
    storage.put("candidates/ghost.csv", b"x")
    assert datasets.orphans(session, storage) == ["candidates/ghost.csv"]


def test_clean_creates_new_version_and_keeps_original(session, storage, chosen):
    from app.db.tables import DatasetVersion
    v1 = session.get(DatasetVersion, chosen.chosen_dataset_version_id)
    v2 = datasets.clean(session, storage, v1)
    assert v2.parent_id == v1.id and storage.exists(v1.storage_key) and storage.exists(v2.storage_key)
