"""Free pilot and forecast (specs/payments.md section 2, specs/cost.md).

The pilot trains a few model types on a small sample (about 5-10% of the rows), drops the weak ones early
(successive halving), draws a learning curve for the survivor and predicts the full-run result with a band.
Everything here is an ESTIMATE. The pilot costs the user nothing and never touches the locked test set.

Method, kept simple on purpose:
  rungs        sample sizes P/4, P/2, P (P = pilot rows). Each model is scored by 3-fold cross-validation.
               After each rung the weaker half is dropped (3 models -> 2 -> 1).
  curve        the survivor's error at each rung against its real training size.
  prediction   error shrinks as size^-c, fitted on the curve with c limited to 0..0.4 and the error never assumed
               to more than halve. This is deliberately conservative.
  uncertainty  cross-validation noise, curve-fit scatter, distance from the pilot to the full size, and the finite
               size of the locked test set, added in quadrature.
  confidence   chance the verified result reaches the target, from a normal approximation.
"""
import math
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import DatasetVersion, Forecast, Project
from ..providers.storage.base import Storage
from . import verify

PILOT_SHARE = 0.08          # of the work rows
PILOT_MIN_ROWS, PILOT_MAX_ROWS = 100, 3000
PILOT_MAX_SHARE = 0.15      # a pilot bigger than this share is not a pilot: too little data
FOLDS = 3
MAX_EXPONENT = 0.4
MAX_ERROR_SHRINK = 0.5      # the full run is never forecast to cut the error by more than half
MIN_SIGMA = 0.015
EXTRAPOLATION_SIGMA = 0.01  # added per doubling of training size beyond the pilot

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


def _phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


@dataclass
class Prediction:
    predicted: float
    band_low: float
    band_high: float
    confidence: float


def extrapolate(curve: list[tuple[float, float, float]], full_train_rows: int, locked_rows: int, target: float) -> Prediction:
    """curve = [(training rows, accuracy, standard error)] from the survivor. Pure maths, easy to test."""
    ns = np.array([n for n, _, _ in curve], dtype=float)
    err = np.clip(1 - np.array([a for _, a, _ in curve]), 1e-3, 1.0)
    last_n, last_err, last_se = ns[-1], err[-1], curve[-1][2]
    c, scatter = 0.0, 0.0
    if len(curve) >= 2:
        slope, intercept = np.polyfit(np.log(ns), np.log(err), 1)
        c = float(np.clip(-slope, 0.0, MAX_EXPONENT))
        scatter = float(np.std(np.log(err) - (intercept + slope * np.log(ns)))) * last_err
    growth = max(full_train_rows / last_n, 1.0)
    pred_err = max(last_err * growth ** (-c), last_err * MAX_ERROR_SHRINK)
    pred = 1 - pred_err
    p = min(max(pred, 0.01), 0.99)
    sigma = math.sqrt(max(last_se, MIN_SIGMA) ** 2 + scatter ** 2
                      + (EXTRAPOLATION_SIGMA * math.log2(growth)) ** 2 + p * (1 - p) / max(locked_rows, 1))
    confidence = 1 - _phi((target - pred) / sigma)
    return Prediction(round(pred, 4), round(max(0.0, pred - 1.96 * sigma), 4), round(min(1.0, pred + 1.96 * sigma), 4),
                      round(confidence, 3))


def not_eligible_reason(pred: Prediction | None, target: float, rows: int | None) -> str | None:
    """Plain-words reason the run should not be sold, or None when it is eligible."""
    if rows is not None and rows < settings.forecast_min_rows:
        return (f"There are only {rows:,} usable rows. That is too little for an honest forecast, "
                "so we cannot sell you a full run.")
    if pred is None:
        return "The test run could not produce a forecast for this data."
    if pred.confidence >= settings.forecast_min_confidence:
        return None
    pct = round(pred.confidence * 100)
    if pred.band_high < target:
        return (f"Even in the best case we expect about {round(pred.band_high * 100)} out of 100 right, "
                f"below your target of {round(target * 100)}. The chance of reaching it is about {pct}%.")
    return (f"We are only about {pct}% sure the full run would reach your target of {round(target * 100)} out of 100. "
            "That is not enough to sell you a run. A lower target or better data would help.")


def run_pilot(session: Session, storage: Storage, project: Project, target: float, seed: int = 0) -> Forecast:
    """Free. Stores and returns a Forecast (eligible or not). Never touches the locked rows."""
    if not 0.0 < target < 1.0:
        raise ForecastError("the target must be between 0 and 1, for example 0.8 for 80 out of 100")
    version = session.get(DatasetVersion, project.chosen_dataset_version_id) if project.chosen_dataset_version_id else None
    if version is None:
        raise ForecastError("choose a dataset first")
    work_key, locked_key = verify.prepare_split(storage, version.id, version.storage_key, version.target_column)
    work = pd.read_csv(storage.path(work_key))
    locked_rows = len(pd.read_csv(storage.path(locked_key)))
    total_rows = len(work) + locked_rows
    row = dict(job_id=project.id, target=target, metric="accuracy")

    def save(pred: Prediction | None, pilot: dict) -> Forecast:
        reason = not_eligible_reason(pred, target, total_rows)
        fc = Forecast(predicted_metric=pred.predicted if pred else 0.0, band_low=pred.band_low if pred else 0.0,
                      band_high=pred.band_high if pred else 0.0, confidence=pred.confidence if pred else 0.0,
                      eligible=reason is None, reason=reason, pilot=pilot, **row)
        session.add(fc)
        session.commit()
        return fc

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
    return save(pred, pilot)


def latest_forecast(session: Session, project_id: str) -> Forecast | None:
    return session.scalar(select(Forecast).where(Forecast.job_id == project_id).order_by(Forecast.created_at.desc()))
