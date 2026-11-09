"""Model families: one factory for the pilot, the free baseline, the local paid backend and the SageMaker script."""
import pandas as pd
import pytest

from app.integrations.training_local.backend import LocalBackend
from app.services.data import baseline, datasets, families, pilot, verification
from app.services.data.features import prepare_features
from app.services.data.samples import churn_csv


@pytest.fixture
def frame():
    df = pd.read_csv(__import__("io").BytesIO(churn_csv(600)))
    df = prepare_features(df, "left")
    return df.drop(columns=["left"]), df["left"]


@pytest.mark.parametrize("family", families.FAMILIES)
def test_every_family_fits_and_predicts(frame, family):
    X, y = frame
    m = families.build(family, X, 20)
    m.fit(X, y)
    assert len(m.predict(X)) == len(X)


def test_unknown_family_is_refused(frame):
    with pytest.raises(ValueError):
        families.build("deep-magic", frame[0])


def test_the_free_baseline_is_still_the_forest(frame):
    X, _ = frame
    assert type(baseline._pipeline(X, 10).named_steps["clf"]).__name__ == "RandomForestClassifier"


def test_plain_names_and_the_not_a_promise_note():
    for fam in families.FAMILIES:
        info = families.type_info(fam)
        assert info["name"] and info["family"] == fam and "not a promise" in info["note"]
    assert families.type_info(None)["family"] == "forest"  # old quotes and models have no family


def test_pilot_stores_the_family_it_kept_and_timings_of_that_family(session, storage, chosen):
    from app.services.data import analysis
    analysis.readiness(session, storage, chosen)
    analysis.baseline(session, storage, chosen)
    f = pilot.run_pilot(session, storage, chosen, 0.6)
    assert f.family in families.FAMILIES and f.family == f.pilot["family"]
    assert f.dataset_version_id == chosen.chosen_dataset_version_id
    assert f.pilot["cost_samples"] and all(len(s) == 2 and s[1] > 0 for s in f.pilot["cost_samples"])


@pytest.mark.parametrize("family", families.FAMILIES)
def test_local_backend_trains_the_requested_family(session, storage, chosen, family):
    from app.repositories import datasets as datasets_repo
    v = datasets_repo.get_version(session, chosen.chosen_dataset_version_id)
    wk, _ = verification.prepare_split(storage, v.id, v.storage_key, v.target_column)
    res = LocalBackend().run(storage.path(wk), v.target_column, 100, family=family)
    import io
    import joblib
    model = joblib.load(io.BytesIO(res.model_bytes))
    expected = {"logistic": "LogisticRegression", "forest": "RandomForestClassifier", "boosting": "HistGradientBoostingClassifier"}[family]
    assert type(model.named_steps["clf"]).__name__ == expected
