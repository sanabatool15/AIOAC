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

from ...config import settings
from ...db import Session
from ...db.tables import DatasetVersion, Forecast, Project
from ...ports import Storage
from ...repositories import analysis as analysis_repo
from ...repositories import datasets as datasets_repo
from ...repositories import forecasts as forecasts_repo
from . import baseline, families, task_wording, tasks, verification
from .tasks import regression
from .forecast import Prediction, extrapolate, not_eligible_reason, suggest_target

PILOT_SHARE = 0.08          # of the work rows
PILOT_MIN_ROWS, PILOT_MAX_ROWS = 100, 3000
PILOT_MAX_SHARE = 0.15      # a pilot bigger than this share is not a pilot: too little data
FOLDS = 3

PLAIN_NAMES = families.PLAIN_NAMES


class ForecastError(Exception):
    pass


def _score(name: str, X: pd.DataFrame, y: pd.Series, task: str = "classification", ref: float | None = None,
           residuals: list | None = None) -> tuple[float, float]:
    """Mean score (accuracy for classification) and its standard error over the cross-validation folds.
    For a number answer `ref` is the frozen error of the average guess; `residuals` collects |error| of every held-out row."""
    kind = tasks.get(task)
    accs = []
    for tr, te in kind.folds(X, y, FOLDS, 0):
        m = kind.build(name, X.iloc[tr], families.PILOT_SIZE[name])
        m.fit(X.iloc[tr], y.iloc[tr])
        pred = m.predict(X.iloc[te])
        accs.append(kind.score(y.iloc[te].to_numpy(), pred).value if ref is None
                    else kind.score(y.iloc[te].to_numpy(), pred, guess_error_ref=ref).value)
        if residuals is not None:
            residuals.extend(np.abs(y.iloc[te].to_numpy(dtype=float) - pred).tolist())
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


def _work_rows(session: Session, storage: Storage, project: Project, version: DatasetVersion, task: str):
    """The work rows (never the locked rows) and the number of locked rows. A number answer is read as numbers."""
    work_key, locked_key = verification.split_for(session, storage, version, task)
    work = pd.read_csv(storage.path(work_key))
    if task == "regression":
        work[version.target_column] = regression.to_number(work[version.target_column])
        work = work.dropna(subset=[version.target_column]).reset_index(drop=True)
    return work, len(pd.read_csv(storage.path(locked_key)))


def target_for_error(session: Session, storage: Storage, project: Project, typical_error: float) -> float:
    """A goal stated as "typically off by no more than X" (in the answer's own units) as the 0 to 1 score the check uses:
    1 - X / (the frozen error of always guessing the average). Code does this, the model never does the arithmetic."""
    task = tasks.task_of(project).id
    version = datasets_repo.get_version(session, project.chosen_dataset_version_id) if project.chosen_dataset_version_id else None
    if task != "regression" or version is None:
        raise ForecastError("a goal in the answer's own units only applies to a project that predicts a number")
    work, _ = _work_rows(session, storage, project, version, task)
    ref = regression.guess_error_ref(work[version.target_column])
    unit = task_wording.unit_for(version.target_column)
    if not 0 < typical_error < ref:
        raise ForecastError(f"a simple guess, always the average, is already off by about {task_wording.plain_amount(ref, unit)}; "
                            "pick a smaller number than that")
    return round(1 - typical_error / ref, 4)


def run_pilot(session: Session, storage: Storage, project: Project, target: float, seed: int = 0) -> Forecast:
    """Free. Stores and returns a Forecast (eligible or not). Never touches the locked rows."""
    if not 0.0 < target < 1.0:
        raise ForecastError("the target must be between 0 and 1, for example 0.8 for 80 out of 100")
    version = datasets_repo.get_version(session, project.chosen_dataset_version_id) if project.chosen_dataset_version_id else None
    if version is None:
        raise ForecastError("choose a dataset first")
    task = tasks.task_of(project).id
    work, locked_rows = _work_rows(session, storage, project, version, task)
    is_number = task == "regression"
    ref = regression.guess_error_ref(work[version.target_column]) if is_number else None   # frozen: the scale of every later score
    unit = task_wording.unit_for(version.target_column) if is_number else ""
    total_rows = len(work) + locked_rows

    def save(pred: Prediction | None, pilot: dict, suggested: float | None = None) -> Forecast:
        scale = {"guess_error": ref, "unit": unit} if is_number else None
        reason = not_eligible_reason(pred, target, total_rows, suggested, task, scale)
        if reason is not None:  # tell the customer what they CAN get
            pilot = {**pilot, "suggested_target": suggested, "issues": data_issues(session, project, version, total_rows)}
        return forecasts_repo.add(session, project_id=project.id, target=target, metric=regression.METRIC if is_number else "accuracy",
                                  predicted_metric=pred.predicted if pred else 0.0,
                                  band_low=pred.band_low if pred else 0.0, band_high=pred.band_high if pred else 0.0,
                                  confidence=pred.confidence if pred else 0.0, eligible=reason is None,
                                  reason=reason, pilot=pilot, family=pilot.get("family"), dataset_version_id=version.id)

    pilot_rows = min(max(round(PILOT_SHARE * len(work)), PILOT_MIN_ROWS), PILOT_MAX_ROWS)
    if total_rows < settings.forecast_min_rows or pilot_rows > PILOT_MAX_SHARE * len(work):
        return save(None, {"rows_used": 0, "share_of_data": 0.0, "note": "too little data"})

    sample = work.sample(n=pilot_rows, random_state=seed).reset_index(drop=True)
    X, y = sample.drop(columns=[version.target_column]), sample[version.target_column]
    rungs = [max(pilot_rows // 4, 20), max(pilot_rows // 2, 40), pilot_rows]
    alive, dropped, history = list(PLAIN_NAMES if not is_number else families.REGRESSION_PLAIN_NAMES), [], []
    plain_names = families.REGRESSION_PLAIN_NAMES if is_number else PLAIN_NAMES
    t0 = time.perf_counter()
    for i, n in enumerate(rungs):
        scores = {m: _score(m, X.iloc[:n], y.iloc[:n], task, ref) for m in alive}
        history.append({"rows": n, "scores": {m: round(s[0], 4) for m, s in scores.items()}})
        if i < len(rungs) - 1:
            keep = max(1, math.ceil(len(alive) / 2))
            ranked = sorted(alive, key=lambda m: scores[m][0], reverse=True)
            for m in ranked[keep:]:
                dropped.append({"model": plain_names[m], "dropped_after_rows": n, "score": round(scores[m][0], 4)})
            alive = ranked[:keep]
    winner = alive[0]
    cost_samples = baseline.sample_timings(work, version.target_column, winner, families.FULL_SIZE[winner], task)  # time the CHOSEN type
    train_frac = (FOLDS - 1) / FOLDS  # cross-validation trains on 2/3 of each rung
    curve, residuals = [], []
    for n in rungs:
        mean, se = _score(winner, X.iloc[:n], y.iloc[:n], task, ref, residuals if n == rungs[-1] and is_number else None)
        curve.append((n * train_frac, mean, se))
    sigma = None   # None: the task's own finite-test term (classification, unchanged)
    if is_number:   # the spread of the errors on the survivor's largest rung, over the frozen scale
        abs_error_sd = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0
        sigma = tasks.get(task).finite_test_sigma(abs_error_sd, locked_rows, ref)
    full_train = round(0.8 * len(work))  # the paid run trains on 80% of the work rows
    pred = extrapolate(curve, full_train, locked_rows, target, task, sigma)
    pilot = {"rows_used": pilot_rows, "share_of_data": round(pilot_rows / total_rows, 3), "rungs": history,
             "kept": plain_names[winner], "family": winner, "dropped": dropped,
             "cost_samples": [list(x) for x in cost_samples],
             "learning_curve": [{"training_rows": round(n), "score": round(a, 4), "accuracy": round(a, 4)} for n, a, _ in curve],
             "full_run_training_rows": full_train, "pilot_seconds": round(time.perf_counter() - t0, 2)}
    if is_number:
        pilot.update({"task_type": task, "unit": unit, "score_scale": {"guess_error": ref, "abs_error_sd": abs_error_sd}})
    suggested = suggest_target(curve, full_train, locked_rows, task, sigma) if pred.confidence < settings.forecast_min_confidence else None
    return save(pred, pilot, suggested)
