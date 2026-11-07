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


def _pipeline(X: pd.DataFrame, n_estimators: int) -> Pipeline:
    """The forest (the free baseline's model). Kept under this name for callers that only know the forest."""
    return families.build("forest", X, n_estimators)


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
    acc = float(accuracy_score(yte, model.predict(Xte)))
    guess = float(accuracy_score(yte, np.full(len(yte), ytr.mode().iloc[0])))
    buf = io.BytesIO()
    joblib.dump(model, buf)
    return BaselineOutcome(acc, guess, secs, [], buf.getvalue())


def sample_timings(df: pd.DataFrame, target: str, family: str = "forest", size: int | None = 100) -> list[tuple[int, float]]:
    """Seconds to fit `family` on 5%, 10% and 20% of the (already prepared) rows: the cost estimator's input."""
    samples: dict[int, float] = {}
    for frac in SAMPLE_FRACTIONS:
        n = min(len(df), max(int(len(df) * frac), MIN_SAMPLE_ROWS))
        if n in samples:
            continue
        sub = df.sample(n=n, random_state=0)
        X, y = sub.drop(columns=[target]), sub[target]
        m = families.build(family, X, size)
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
