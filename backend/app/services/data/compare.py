"""Compare the model types on the WORK rows and say what seems to drive the answer. Pure: a DataFrame in, plain facts out.

No SQL, no storage, no payments. The caller passes only work rows (never the locked test rows, see verification.py).
It fits one small model of each type (families.py) on a sample of at most MAX_ROWS rows, scores each on a slice of
those rows held back for the purpose, and looks at which columns matter on the best type. Seeds are fixed, so the same
input always gives the same numbers. Everything is an ESTIMATE and a clue, never a promise.
"""
import time

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.model_selection import train_test_split

from . import baseline, families

MAX_ROWS = 5000            # rows used for the fits
MIN_ROWS = 60
HOLD_SHARE = 0.25
CLUE_ROWS = 800            # rows the column check scores on
CLUE_REPEATS = 3
MAX_CLUES = 5
BUDGET_S = 12.0
CLOSE_POINTS = 2           # kinds within this many points of each other count as the same
STEEP_CURVE, FLAT_CURVE = 0.03, 0.01   # learning-curve gain (0 to 1) across the free small test
A_LOT, SOME, TINY = 0.05, 0.01, 0.002  # drop in right answers (0 to 1) when a column is scrambled

CLUES_NOTE = "These are clues, not causes: a column that matters may only travel with the real reason."
ESTIMATE_NOTE = "An estimate, not a promise for new data."


def _pts(x: float) -> int:
    return round(float(x) * 100)


def more_data_effect(curve) -> dict:
    """From the stored free-pilot learning curve (list of {training_rows, accuracy}); no retraining."""
    try:
        gain = float(curve[-1]["accuracy"]) - float(curve[0]["accuracy"])
    except (TypeError, KeyError, IndexError, ValueError):
        return {"trend": "unknown", "text": "We have no learning curve for this data yet, so we cannot say whether more rows would help."}
    if gain >= STEEP_CURVE:
        return {"trend": "rising", "text": f"Showing the model more rows helped in the free small test (about {_pts(gain)} more right in 100), "
                                           "so more rows might help a little more. That is an estimate, not a promise."}
    if gain <= FLAT_CURVE:
        return {"trend": "flat", "text": "Showing the model more rows barely changed the score in the free small test, "
                                         "so more rows alone are unlikely to help much."}
    return {"trend": "rising", "text": f"More rows helped a little in the free small test (about {_pts(gain)} more right in 100); "
                                       "an estimate, not a promise."}


def verdict(kinds: list[dict]) -> str:
    """One plain line. Compares in whole points out of 100."""
    if len(kinds) < 2:
        return "We could not compare the model types in the time allowed."
    scores = sorted((k["right_out_of_100"] for k in kinds), reverse=True)
    best = max(kinds, key=lambda k: k["right_out_of_100"])
    n = len(kinds)
    word = {2: "two", 3: "three"}.get(n, str(n))
    if scores[0] - scores[-1] <= CLOSE_POINTS:
        return f"The {word} kinds score within {CLOSE_POINTS} points of each other, so the type of model is not the problem."
    if scores[0] - scores[1] > CLOSE_POINTS or n == 2:
        return f"One kind is clearly better: {best['name']} scores {scores[0] - scores[1]} points above the next one."
    return f"{best['name']} scores {scores[0] - scores[-1]} points above the weakest kind, so the type of model matters a little."


def _how_much(drop: float) -> str:
    return "a lot" if drop >= A_LOT else "some" if drop >= SOME else "a little"


def _effect(drop: float) -> str:
    if drop >= SOME:
        return f"About {_pts(drop)} fewer right in 100 without it."
    return "Changes the score only slightly."


def top_clues(model, X: pd.DataFrame, y: pd.Series, deadline: float) -> list[dict]:
    """Up to MAX_CLUES columns whose values, when shuffled, cost the most right answers on the held-back rows."""
    if time.perf_counter() > deadline or X.shape[1] == 0:
        return []
    if len(X) > CLUE_ROWS:
        idx = np.random.RandomState(0).choice(len(X), CLUE_ROWS, replace=False)
        X, y = X.iloc[idx], y.iloc[idx]
    r = permutation_importance(model, X, y, scoring="accuracy", n_repeats=CLUE_REPEATS, random_state=0, n_jobs=1)
    order = sorted(range(X.shape[1]), key=lambda i: (-r.importances_mean[i], str(X.columns[i])))
    return [{"column": str(X.columns[i]), "how_much": _how_much(r.importances_mean[i]), "plain_effect": _effect(r.importances_mean[i])}
            for i in order[:MAX_CLUES] if r.importances_mean[i] >= TINY]


def _split(df: pd.DataFrame, target: str):
    X, y = df.drop(columns=[target]), df[target]
    try:
        return train_test_split(X, y, test_size=HOLD_SHARE, random_state=0, stratify=y)
    except ValueError:
        return train_test_split(X, y, test_size=HOLD_SHARE, random_state=0)


def compare(work: pd.DataFrame, target: str, learning_curve=None, budget_s: float = BUDGET_S, max_rows: int = MAX_ROWS) -> dict:
    """`work` must hold only work rows (already prepared by features.prepare_features). Returns plain facts or {"error": ...}."""
    t0 = time.perf_counter()
    deadline = t0 + budget_s
    df = work.dropna(subset=[target])
    if df[target].nunique() < 2 or len(df) < MIN_ROWS:
        return {"error": "there is too little data to compare model types honestly"}
    if len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=0)
    Xtr, Xte, ytr, yte = _split(df, target)
    guess = float((yte == ytr.mode().iloc[0]).mean())
    kinds, fitted = [], {}
    for fam in families.FAMILIES:
        if kinds and time.perf_counter() > deadline:
            break
        try:
            m = families.build(fam, Xtr, families.PILOT_SIZE[fam])
            m.fit(Xtr, ytr)
            pred = m.predict(Xte)
        except Exception:   # one type failing must not hide the others
            continue
        row = {"family": fam, "name": families.plain_name(fam), "right_out_of_100": _pts((pred == yte.to_numpy()).mean()),
               "simple_guess_out_of_100": _pts(guess)}
        rare = baseline.rare_group_recall(df[target], yte, pred)
        if rare is not None:
            row["rare_group_caught_out_of_100"] = _pts(rare)
        kinds.append(row)
        fitted[fam] = m
    if not kinds:
        return {"error": "we could not fit any model type on this data"}
    best = max(kinds, key=lambda k: (k["right_out_of_100"], -families.FAMILIES.index(k["family"])))
    try:
        clues = top_clues(fitted[best["family"]], Xte, yte, deadline)
    except Exception:
        clues = []
    return {"is_estimate": True, "rows_used": int(len(df)), "kinds": kinds,
            "best": {"family": best["family"], "name": best["name"]}, "verdict": verdict(kinds),
            "effect_of_more_data": more_data_effect(learning_curve), "top_clues": clues, "clues_note": CLUES_NOTE,
            "note": ESTIMATE_NOTE, "seconds": round(time.perf_counter() - t0, 1)}
