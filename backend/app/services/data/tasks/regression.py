"""Regression (a number as the answer) behind the TaskKind interface (specs/ml-tasks/01 section 2.2).

Score = how much closer the model is than a simple guess that always says the average:
    score = clip(1 - error / guess_error_ref, 0, 1)
`error` is the average distance (mean absolute) of the model's guesses from the true answers on held-out rows.
`guess_error_ref` is FROZEN from the work rows at pilot time, so a target in plain units ("off by no more than $X")
converts to the same score before and after the paid run. The simple guess scores 0 by construction. Pure code plus
the free test; it delegates to baseline.py and families.py, which ship to SageMaker and must not import this package."""
import io
import math
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, train_test_split

from .. import baseline, families
from ..features import prepare_features
from .base import Score

METRIC = "error_reduction"
FREE_TEST_TREES = 100


def to_number(s: pd.Series) -> pd.Series:
    """The answer column as numbers: text like "$1,200" or "12%" is read as a number, anything else becomes empty."""
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float)
    t = s.astype(str).str.strip().str.replace(r"[$,%\s]", "", regex=True)
    t = t.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    return pd.to_numeric(t, errors="coerce")


def guess_error_ref(y_work) -> float:
    """Average distance of the work rows from their own average: the error of always guessing the average."""
    y = np.asarray(y_work, dtype=float)
    y = y[~np.isnan(y)]
    return float(np.mean(np.abs(y - y.mean()))) if len(y) else 0.0


class RegressionTask:
    id = "regression"
    plain_name = "a number"
    needs_target = True
    supports_fee = True
    families = families.REGRESSION_FAMILIES

    def split(self, df, target, share=0.2, seed=0):
        X, y = df.drop(columns=[target]), df[target]
        return train_test_split(X, y, test_size=share, random_state=seed)

    def locked_split(self, df, target, share, seed):
        return train_test_split(df, test_size=share, random_state=seed)

    def folds(self, X, y, n, seed=0):
        return list(KFold(n, shuffle=True, random_state=seed).split(X))

    def build(self, family, X, size=None):
        return families.build(family, X, size, task="regression")

    def score(self, y_true, y_pred, y_train=None, guess_error_ref: float | None = None):
        yt, yp = np.asarray(y_true, dtype=float), np.asarray(y_pred, dtype=float)
        error = float(np.mean(np.abs(yt - yp))) if len(yt) else 0.0
        centre = float(np.mean(np.asarray(y_train, dtype=float))) if y_train is not None and len(y_train) else float(np.mean(yt)) if len(yt) else 0.0
        guess_error = float(np.mean(np.abs(yt - centre))) if len(yt) else 0.0
        ref = guess_error_ref if guess_error_ref is not None else guess_error
        value = float(np.clip(1 - error / ref, 0, 1)) if ref and ref > 0 else 0.0
        return Score(value, 0.0, {"error": error, "guess_error": guess_error, "rows_test": int(len(yt))})

    def finite_test_variance(self, score, locked_rows):
        # Cautious fallback, used only when no spread of errors is given (the pilot always gives one, see finite_test_sigma).
        # A score between 0 and 1 has a standard deviation of at most 0.5, so this is an upper bound.
        return 0.25 / max(locked_rows, 1)

    def finite_test_sigma(self, abs_error_sd, locked_rows, guess_error_ref):
        """Standard deviation of the locked-rows score from the finite number of locked rows: the standard error of the
        average distance, sd(|error|) / sqrt(rows), divided by the frozen scale so it sits on the 0 to 1 score scale."""
        if locked_rows <= 0 or guess_error_ref <= 0 or abs_error_sd <= 0:
            return 0.0
        return float(abs_error_sd) / math.sqrt(locked_rows) / float(guess_error_ref)

    def trust(self, grade, score, simple_guess=0.0):
        from ..insights import trust_level
        return trust_level(grade, score, simple_guess)

    def free_test(self, path: str, target: str, unit: str = "") -> baseline.BaselineOutcome:
        return run_free_test(path, target, unit)


def run_free_test(path: str, target: str, unit: str = "") -> baseline.BaselineOutcome:
    """One 80/20 fit of the forest on a number answer. Reports the error, the error of always guessing the average,
    and the score. Rows with no usable answer are dropped. Deterministic."""
    raw = pd.read_csv(path)
    raw[target] = to_number(raw[target])
    df = prepare_features(raw.dropna(subset=[target]), target)
    task = RegressionTask()
    Xtr, Xte, ytr, yte = task.split(df, target, 0.2, 0)
    model = task.build("forest", Xtr, FREE_TEST_TREES)
    t0 = time.perf_counter()
    model.fit(Xtr, ytr)
    secs = time.perf_counter() - t0
    s = task.score(yte, model.predict(Xte), y_train=ytr, guess_error_ref=guess_error_ref(ytr))
    buf = io.BytesIO()
    joblib.dump(model, buf)
    extras = {"error": s.extras["error"], "guess_error": s.extras["guess_error"], "unit": unit, "rows_test": len(yte)}
    samples = baseline.sample_timings(df, target, "forest", FREE_TEST_TREES, task="regression")
    return baseline.BaselineOutcome(accuracy=s.value, simple_guess_accuracy=0.0, seconds=secs, samples=samples, model_bytes=None,
                                    train_rows=len(ytr), test_rows=len(yte), task_type="regression", score=s.value,
                                    error=s.extras["error"], guess_error=s.extras["guess_error"], extras=extras)
