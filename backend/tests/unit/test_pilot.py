"""The free pilot, the locked test set and the independent check."""
import pandas as pd
import pytest

from app.db.tables import DatasetVersion, InsightReport
from app.integrations.training_local.backend import LocalBackend
from app.repositories.ledger import LedgerRepository
from app.services.data import datasets, pilot, verification
from app.services.data.samples import churn_csv


def test_split_is_fixed_and_locked_rows_never_reach_the_work_rows(session, storage, chosen):
    v = session.get(DatasetVersion, chosen.chosen_dataset_version_id)
    wk, lk = verification.prepare_split(storage, v.id, v.storage_key, v.target_column)
    first = (storage.get(wk), storage.get(lk))
    assert verification.prepare_split(storage, v.id, v.storage_key, v.target_column) == (wk, lk)
    assert (storage.get(wk), storage.get(lk)) == first
    work, locked = pd.read_csv(storage.path(wk)), pd.read_csv(storage.path(lk))
    assert abs(len(locked) / (len(work) + len(locked)) - verification.LOCKED_SHARE) < 0.02
    key = lambda df: set(map(tuple, df.astype(str).values.tolist()))
    assert not (key(work) & key(locked))


def test_verification_is_independent_of_what_the_backend_reports(session, storage, chosen):
    v = session.get(DatasetVersion, chosen.chosen_dataset_version_id)
    wk, lk = verification.prepare_split(storage, v.id, v.storage_key, v.target_column)
    res = LocalBackend().run(storage.path(wk), v.target_column, 100)
    out = verification.verify_model(res.model_bytes, storage, lk, v.target_column)
    assert out["rows"] > 0 and 0.0 <= out["value"] <= 1.0
    with pytest.raises(verification.VerificationError):
        verification.verify_model(b"not a model", storage, lk, v.target_column)
    with pytest.raises(verification.VerificationError):
        verification.verify_model(None, storage, lk, v.target_column)


def test_pilot_uses_a_small_share_drops_models_and_costs_nothing(session, storage, chosen):
    f = pilot.run_pilot(session, storage, chosen, 0.6)
    assert 0.03 <= f.pilot["share_of_data"] <= 0.10 and f.pilot["dropped"] and f.pilot["kept"]
    assert len(f.pilot["learning_curve"]) == 3 and 0 <= f.confidence <= 1
    assert LedgerRepository(session).balance(chosen.id) == 0


def test_pilot_rejects_a_target_outside_zero_to_one(session, storage, chosen):
    with pytest.raises(pilot.ForecastError):
        pilot.run_pilot(session, storage, chosen, 1.5)


def test_small_data_is_not_eligible(session, storage, project):
    c = datasets.add_candidate(session, storage, project, "tiny", "bundled", churn_csv(300))
    datasets.select_candidate(session, storage, project, c.id, "left")
    f = pilot.run_pilot(session, storage, project, 0.6)
    assert not f.eligible and "too little" in f.reason.lower()


def test_data_issues_are_plain_words(session, chosen):
    v = session.get(DatasetVersion, chosen.chosen_dataset_version_id)
    session.add(InsightReport(dataset_version_id=v.id, measurements={}, grade="C",
                              findings=[{"kind": "OK", "text": "fine"}, {"kind": "NOTE", "text": "Many rows are missing values"}]))
    chosen.baseline_result = {"accuracy": 0.74, "simple_guess_accuracy": 0.73}
    session.commit()
    issues = pilot.data_issues(session, chosen, v, 100)
    assert "Many rows are missing values" in issues and "fine" not in issues
    assert any("too little data" in i for i in issues) and any("barely beats a simple guess" in i for i in issues)
    assert not any(w in " ".join(issues).lower() for w in ("f1", "precision", "train/test"))
    chosen.baseline_result = {"accuracy": 0.9, "simple_guess_accuracy": 0.5}
    assert not any("barely" in i for i in pilot.data_issues(session, chosen, v, 5000))
