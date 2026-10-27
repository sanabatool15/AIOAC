"""The free pilot: a small test on a slice of the data that yields a forecast (specs/payments.md).

The pilot trains a few model types on about 5-10% of the rows and drops the weak ones early (successive halving).
It draws a learning curve for the survivor and hands it to forecast.py. It costs the user nothing and never
touches the locked test set (verification.py). Everything it returns is an ESTIMATE.

  rungs   sample sizes P/4, P/2, P (P = pilot rows). Each model is scored by 3-fold cross-validation.
          After each rung the weaker half is dropped (3 models -> 2 -> 1).
"""
import math
import time

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ...config import settings
from ...db import Session
from ...db.tables import DatasetVersion, Forecast, Project
from ...ports import Storage
from ...repositories import analysis as analysis_repo
from ...repositories import datasets as datasets_repo
from ...repositories import forecasts as forecasts_repo
from . import verification
from .forecast import Prediction, extrapolate, not_eligible_reason, suggest_target

PILOT_SHARE = 0.08          # of the work rows
PILOT_MIN_ROWS, PILOT_MAX_ROWS = 100, 3000
PILOT_MAX_SHARE = 0.15      # a pilot bigger than this share is not a pilot: too little data
FOLDS = 3

PLAIN_NAMES = {"logistic": "a simple linear model", "forest": "a forest of decision trees", "boosting": "a boosted-trees model"}


class ForecastError(Exception):
    pass


def _model(name: str, X: pd.DataFrame) -> Pipeline:
    num = X.select_dtypes(include="number").columns.tolist()
    cat = [c for c in X.columns if c not in num]
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), num),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), cat),
    ])
    clf = {"logistic": LogisticRegression(max_iter=300),
           "forest": RandomForestClassifier(n_estimators=60, random_state=0, n_jobs=1),
           "boosting": HistGradientBoostingClassifier(max_iter=60, random_state=0)}[name]
    return Pipeline([("pre", pre), ("clf", clf)])


def _score(name: str, X: pd.DataFrame, y: pd.Series) -> tuple[float, float]:
    """Mean accuracy and its standard error over the cross-validation folds."""
    try:
        folds = list(StratifiedKFold(FOLDS, shuffle=True, random_state=0).split(X, y))
    except ValueError:
        folds = list(KFold(FOLDS, shuffle=True, random_state=0).split(X))
    accs = []
    for tr, te in folds:
        m = _model(name, X.iloc[tr])
        m.fit(X.iloc[tr], y.iloc[tr])
        accs.append(float((m.predict(X.iloc[te]) == y.iloc[te].to_numpy()).mean()))
    return float(np.mean(accs)), float(np.std(accs, ddof=1) / math.sqrt(len(accs))) if len(accs) > 1 else 0.0


def data_issues(session: Session, project: Project, version: DatasetVersion, rows: int) -> list[str]:
    """Plain-words reasons the forecast is weak: NOTE findings from the readiness report, too little data, a weak free test."""
    out: list[str] = []
    if rows < settings.forecast_min_rows:
        out.append(f"There are only {rows:,} usable rows, which is too little data.")
    report = analysis_repo.latest_insight_report(session, version.id)
    out += [f["text"] for f in (report.findings if report else []) if f.get("kind") == "NOTE" and f.get("text")]
    b = project.baseline_result or {}
    if b and b.get("accuracy", 0) - b.get("simple_guess_accuracy", 0) < 0.03:
        out.append("The free test barely beats a simple guess, so the data may not hold much signal for this question.")
    return out


def run_pilot(session: Session, storage: Storage, project: Project, target: float, seed: int = 0) -> Forecast:
    """Free. Stores and returns a Forecast (eligible or not). Never touches the locked rows."""
    if not 0.0 < target < 1.0:
        raise ForecastError("the target must be between 0 and 1, for example 0.8 for 80 out of 100")
    version = datasets_repo.get_version(session, project.chosen_dataset_version_id) if project.chosen_dataset_version_id else None
    if version is None:
        raise ForecastError("choose a dataset first")
    work_key, locked_key = verification.prepare_split(storage, version.id, version.storage_key, version.target_column)
    work = pd.read_csv(storage.path(work_key))
    locked_rows = len(pd.read_csv(storage.path(locked_key)))
    total_rows = len(work) + locked_rows

    def save(pred: Prediction | None, pilot: dict, suggested: float | None = None) -> Forecast:
        reason = not_eligible_reason(pred, target, total_rows, suggested)
        if reason is not None:  # tell the customer what they CAN get
            pilot = {**pilot, "suggested_target": suggested, "issues": data_issues(session, project, version, total_rows)}
        return forecasts_repo.add(session, project_id=project.id, target=target, metric="accuracy",
                                  predicted_metric=pred.predicted if pred else 0.0,
                                  band_low=pred.band_low if pred else 0.0, band_high=pred.band_high if pred else 0.0,
                                  confidence=pred.confidence if pred else 0.0, eligible=reason is None,
                                  reason=reason, pilot=pilot)

    pilot_rows = min(max(round(PILOT_SHARE * len(work)), PILOT_MIN_ROWS), PILOT_MAX_ROWS)
    if total_rows < settings.forecast_min_rows or pilot_rows > PILOT_MAX_SHARE * len(work):
        return save(None, {"rows_used": 0, "share_of_data": 0.0, "note": "too little data"})

    sample = work.sample(n=pilot_rows, random_state=seed).reset_index(drop=True)
    X, y = sample.drop(columns=[version.target_column]), sample[version.target_column]
    rungs = [max(pilot_rows // 4, 20), max(pilot_rows // 2, 40), pilot_rows]
    alive, dropped, history = list(PLAIN_NAMES), [], []
    t0 = time.perf_counter()
    for i, n in enumerate(rungs):
        scores = {m: _score(m, X.iloc[:n], y.iloc[:n]) for m in alive}
        history.append({"rows": n, "scores": {m: round(s[0], 4) for m, s in scores.items()}})
        if i < len(rungs) - 1:
            keep = max(1, math.ceil(len(alive) / 2))
            ranked = sorted(alive, key=lambda m: scores[m][0], reverse=True)
            for m in ranked[keep:]:
                dropped.append({"model": PLAIN_NAMES[m], "dropped_after_rows": n, "score": round(scores[m][0], 4)})
            alive = ranked[:keep]
    winner = alive[0]
    train_frac = (FOLDS - 1) / FOLDS  # cross-validation trains on 2/3 of each rung
    curve = []
    for n in rungs:
        mean, se = _score(winner, X.iloc[:n], y.iloc[:n])
        curve.append((n * train_frac, mean, se))
    full_train = round(0.8 * len(work))  # the paid run trains on 80% of the work rows
    pred = extrapolate(curve, full_train, locked_rows, target)
    pilot = {"rows_used": pilot_rows, "share_of_data": round(pilot_rows / total_rows, 3), "rungs": history,
             "kept": PLAIN_NAMES[winner], "dropped": dropped,
             "learning_curve": [{"training_rows": round(n), "accuracy": round(a, 4)} for n, a, _ in curve],
             "full_run_training_rows": full_train, "pilot_seconds": round(time.perf_counter() - t0, 2)}
    suggested = suggest_target(curve, full_train, locked_rows) if pred.confidence < settings.forecast_min_confidence else None
    return save(pred, pilot, suggested)
