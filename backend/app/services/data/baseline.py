"""Free baseline (specs/data.md section 5). Real scikit-learn on held-out data, plus sample timings for the cost estimator."""
import io
import time
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from . import families
from .features import prepare_features

SAMPLE_FRACTIONS = (0.05, 0.1, 0.2)
MIN_SAMPLE_ROWS = 30


@dataclass
class BaselineOutcome:
    accuracy: float
    simple_guess_accuracy: float
    seconds: float
    samples: list[tuple[int, float]]  # (rows, seconds) for the cost estimator
    model_bytes: bytes | None = None
    train_rows: int = 0
    test_rows: int = 0
    rare_group_caught: float | None = None   # share (0 to 1) of the smallest group the model found on the held-out rows; None unless lopsided
    # Set only for a number as the answer (tasks/regression.py). For classification they stay None and `accuracy` is the score.
    task_type: str = "classification"
    score: float | None = None               # error reduction against always guessing the average, 0 to 1
    error: float | None = None               # average distance of the model's guesses from the true answers
    guess_error: float | None = None         # the same for always guessing the average
    extras: dict | None = None


def _pipeline(X: pd.DataFrame, n_estimators: int) -> Pipeline:
    """The forest (the free baseline's model). Kept under this name for callers that only know the forest."""
    return families.build("forest", X, n_estimators)


RARE_GROUP_BELOW = 0.20


def rare_group_recall(y_all, y_true, y_pred) -> float | None:
    """Share of the smallest group's held-out rows that the model got right. Only when that group is under 20% of
    `y_all` (all rows) and has rows in `y_true`; otherwise None. Pure: no model, no I/O."""
    y_all, y_true, y_pred = pd.Series(list(y_all)), pd.Series(list(y_true)), pd.Series(list(y_pred))
    shares = y_all.value_counts(normalize=True)
    if len(shares) < 2 or float(shares.iloc[-1]) >= RARE_GROUP_BELOW:
        return None
    mask = y_true == shares.index[-1]
    if not mask.any():
        return None
    return float((y_pred[mask] == y_true[mask]).mean())


def _split(df: pd.DataFrame, target: str):
    X, y = df.drop(columns=[target]), df[target]
    try:
        return train_test_split(X, y, test_size=0.2, random_state=0, stratify=y)
    except ValueError:  # a class with too few rows to stratify
        return train_test_split(X, y, test_size=0.2, random_state=0)


def fit_and_score(path: str, target: str, n_estimators: int = 100, family: str = "forest") -> BaselineOutcome:
    """Train and score one model family. `n_estimators` sizes the forest; other families use their full-run size."""
    df = prepare_features(pd.read_csv(path).dropna(subset=[target]), target)
    Xtr, Xte, ytr, yte = _split(df, target)
    model = families.build(family, Xtr, n_estimators if family == "forest" else None)
    t0 = time.perf_counter()
    model.fit(Xtr, ytr)
    secs = time.perf_counter() - t0
    pred = model.predict(Xte)
    acc = float(accuracy_score(yte, pred))
    guess = float(accuracy_score(yte, np.full(len(yte), ytr.mode().iloc[0])))
    buf = io.BytesIO()
    joblib.dump(model, buf)
    return BaselineOutcome(acc, guess, secs, [], buf.getvalue(), train_rows=len(ytr), test_rows=len(yte),
                           rare_group_caught=rare_group_recall(df[target], yte, pred))


def sample_timings(df: pd.DataFrame, target: str, family: str = "forest", size: int | None = 100,
                   task: str = "classification") -> list[tuple[int, float]]:
    """Seconds to fit `family` on 5%, 10% and 20% of the (already prepared) rows: the cost estimator's input."""
    samples: dict[int, float] = {}
    for frac in SAMPLE_FRACTIONS:
        n = min(len(df), max(int(len(df) * frac), MIN_SAMPLE_ROWS))
        if n in samples:
            continue
        sub = df.sample(n=n, random_state=0)
        X, y = sub.drop(columns=[target]), sub[target]
        m = families.build(family, X, size, task)
        t0 = time.perf_counter()
        m.fit(X, y)
        samples[n] = time.perf_counter() - t0
    return sorted(samples.items())


def run_baseline(path: str, target: str) -> BaselineOutcome:
    """Held-out accuracy plus timings on small samples (the cost estimator's input)."""
    out = fit_and_score(path, target)
    df = prepare_features(pd.read_csv(path).dropna(subset=[target]), target)
    out.samples = sample_timings(df, target)
    out.model_bytes = None
    return out
