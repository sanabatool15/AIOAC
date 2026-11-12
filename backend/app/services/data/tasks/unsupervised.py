"""Grouping and unusual records (no answer column) behind the TaskKind interface (specs/ml-tasks/01 sections 2.4, 2.5).

There is no true answer to check, so the score is STEADINESS: would a second look at different rows give the same
groups (or the same flagged records)? A score near 0 means "no clear groups" or "nothing clearly unusual", and then the
run is not sold. These tasks carry no success fee (supports_fee = False): the user pays compute only. Everything here
is an estimate; the thresholds below were tuned on synthetic data only and need real-data calibration.

Pure: pandas, numpy and scikit-learn only; no app, database or storage imports. Words for the user live in task_wording."""
import time

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.model_selection import KFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .. import baseline
from ..features import prepare_features
from .base import Score

METRIC = "steadiness"
MIN_ROWS = 100
MAX_ROWS = 20_000            # the free test and the paid run look at most this many rows (keeps run time bounded)
K_RANGE = range(2, 7)
SILHOUETTE_FLOOR, SILHOUETTE_SPAN = 0.25, 0.35     # separation below the floor means "no clear groups"
CONTAMINATION = 0.03
SEPARATION_FLOOR, SEPARATION_SPAN = 3.3, 3.0       # how far the flagged records sit from the rest, in spreads
SILHOUETTE_SAMPLE = 2000


class UnsupervisedDataError(ValueError):
    """The data cannot be used. The message is plain words for the user."""


def _pre(X: pd.DataFrame) -> ColumnTransformer:
    num = X.select_dtypes(include="number").columns.tolist()
    cat = [c for c in X.columns if c not in num]
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), num),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), cat),
    ])


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Row labels and exact copies are dropped, text numbers read as numbers, repeated rows removed, size bounded."""
    out = prepare_features(df, None)
    if len(out) > MAX_ROWS:
        out = out.sample(n=MAX_ROWS, random_state=0).reset_index(drop=True)
    if out.shape[1] == 0 or len(out) < MIN_ROWS:
        raise UnsupervisedDataError(f"There are only {len(out):,} usable rows, which is too few to look for groups or unusual records.")
    return out


def build(kind: str, X: pd.DataFrame, param=None) -> Pipeline:
    """A fresh unfitted pipeline: `kind` is "grouping" (param = number of groups) or "unusual" (param = share to flag)."""
    est = KMeans(n_clusters=int(param or 3), n_init=5, random_state=0) if kind == "grouping" else \
        IsolationForest(contamination=float(param or CONTAMINATION), random_state=0, n_jobs=1)
    return Pipeline([("pre", _pre(X)), ("clf", est)])


def _halves(n: int, seed: int):
    idx = np.random.default_rng(seed).permutation(n)
    return idx[: n // 2], idx[n // 2:]


# ---- grouping ---------------------------------------------------------------------------------------------------------
def _best_k(Z: np.ndarray, seed: int) -> tuple[int, float]:
    sample = Z if len(Z) <= SILHOUETTE_SAMPLE else Z[np.random.default_rng(seed).choice(len(Z), SILHOUETTE_SAMPLE, replace=False)]
    best = (K_RANGE[0], -1.0)
    for k in K_RANGE:
        labels = KMeans(k, n_init=5, random_state=0).fit_predict(sample)
        if len(set(labels)) < 2:
            continue
        s = float(silhouette_score(sample, labels))
        if s > best[1]:
            best = (k, s)
    return best


def _grouping_score(Z: np.ndarray, k: int, silhouette: float, seed: int) -> tuple[float, float]:
    """(score, stability): two models fitted on different halves label ALL the rows; the score is how much they agree,
    damped to 0 when the groups are not clearly separate."""
    a, b = _halves(len(Z), seed)
    la = KMeans(k, n_init=5, random_state=0).fit(Z[a]).predict(Z)
    lb = KMeans(k, n_init=5, random_state=0).fit(Z[b]).predict(Z)
    stability = float(np.clip(adjusted_rand_score(la, lb), 0, 1))
    factor = float(np.clip((silhouette - SILHOUETTE_FLOOR) / SILHOUETTE_SPAN, 0, 1))
    return stability * factor, stability


def evaluate_grouping(df: pd.DataFrame, seed: int = 0, k: int | None = None) -> dict:
    X = clean(df)
    Z = _pre(X).fit_transform(X)
    if k is None:
        k, sil = _best_k(Z, seed)
    else:
        sample = Z if len(Z) <= SILHOUETTE_SAMPLE else Z[np.random.default_rng(seed).choice(len(Z), SILHOUETTE_SAMPLE, replace=False)]
        sil = float(silhouette_score(sample, KMeans(k, n_init=5, random_state=0).fit_predict(sample)))
    score, stability = _grouping_score(Z, k, sil, seed)
    labels = KMeans(k, n_init=5, random_state=0).fit_predict(Z)
    sizes = sorted((np.bincount(labels) / len(labels)).round(3).tolist(), reverse=True)
    return {"score": score, "stability": stability, "separation": sil, "groups": int(k), "group_shares": sizes, "rows": len(X)}


# ---- unusual -----------------------------------------------------------------------------------------------------------
def _flagged(Z: np.ndarray, train: np.ndarray, c: float) -> tuple[set, np.ndarray]:
    m = IsolationForest(contamination=c, random_state=0, n_jobs=1).fit(Z[train])
    return set(np.where(m.predict(Z) == -1)[0]), m.score_samples(Z)


def _separation(scores: np.ndarray, c: float) -> float:
    cut = np.quantile(scores, c)
    flagged = scores <= cut
    rest = scores[~flagged]
    if not flagged.any() or rest.std() == 0:
        return 0.0
    return float((rest.mean() - scores[flagged].mean()) / rest.std())


def _unusual_score(Z: np.ndarray, c: float, seed: int) -> tuple[float, float, float]:
    """(score, overlap, separation): two models on different halves flag records among ALL rows; the score is the overlap
    of the two flagged sets, damped to 0 when the flagged records do not stand clearly apart from the rest."""
    a, b = _halves(len(Z), seed)
    fa, scores = _flagged(Z, a, c)
    fb, _ = _flagged(Z, b, c)
    overlap = len(fa & fb) / max(len(fa | fb), 1)
    sep = _separation(scores, c)
    factor = float(np.clip((sep - SEPARATION_FLOOR) / SEPARATION_SPAN, 0, 1))
    return overlap * factor, overlap, sep


def evaluate_unusual(df: pd.DataFrame, seed: int = 0, contamination: float = CONTAMINATION) -> dict:
    X = clean(df)
    Z = _pre(X).fit_transform(X)
    score, overlap, sep = _unusual_score(Z, contamination, seed)
    return {"score": score, "stability": overlap, "separation": sep, "flag_share": contamination, "rows": len(X)}


# ---- the locked-rows check (verification.py): refit on the locked rows and compare with the saved model ---------------
def score_locked(kind: str, model: Pipeline, locked: pd.DataFrame, seed: int = 0) -> dict:
    """The saved model labels the locked rows; a second model of the same type fitted on those rows labels them too. The
    value is how much they agree, damped like the free test. Informational: these types carry no success fee."""
    X = prepare_features(locked, None)
    Z = model.named_steps["pre"].transform(X)
    if kind == "grouping":
        k = model.named_steps["clf"].n_clusters
        la = model.named_steps["clf"].predict(Z)
        lb = KMeans(k, n_init=5, random_state=0).fit_predict(Z)
        sample = Z if len(Z) <= SILHOUETTE_SAMPLE else Z[:SILHOUETTE_SAMPLE]
        sil = float(silhouette_score(sample, la[: len(sample)])) if len(set(la[: len(sample)])) > 1 else 0.0
        value = float(np.clip(adjusted_rand_score(la, lb), 0, 1)) * float(np.clip((sil - SILHOUETTE_FLOOR) / SILHOUETTE_SPAN, 0, 1))
        return {"value": value, "rows": int(len(Z))}
    c = model.named_steps["clf"].contamination
    fa = set(np.where(model.named_steps["clf"].predict(Z) == -1)[0])
    ref = IsolationForest(contamination=c, random_state=0, n_jobs=1).fit(Z)
    fb = set(np.where(ref.predict(Z) == -1)[0])
    overlap = len(fa & fb) / max(len(fa | fb), 1)
    sep = _separation(model.named_steps["clf"].score_samples(Z), c)
    return {"value": overlap * float(np.clip((sep - SEPARATION_FLOOR) / SEPARATION_SPAN, 0, 1)), "rows": int(len(Z))}


# ---- the TaskKinds -------------------------------------------------------------------------------------------------------
def _timings(df: pd.DataFrame, kind: str, param) -> list[tuple[int, float]]:
    """Seconds to fit one model on 5%, 10% and 20% of the rows: the cost estimator's input."""
    out: dict[int, float] = {}
    for frac in baseline.SAMPLE_FRACTIONS:
        n = min(len(df), max(int(len(df) * frac), baseline.MIN_SAMPLE_ROWS))
        if n in out:
            continue
        sub = df.sample(n=n, random_state=0)
        m = build(kind, sub, param)
        t0 = time.perf_counter()
        m.fit(sub)
        out[n] = time.perf_counter() - t0
    return sorted(out.items())


class _NoAnswerTask:
    needs_target = False
    supports_fee = False
    kind = ""

    def split(self, df, target, share=0.2, seed=0):
        train, test = train_test_split(df, test_size=share, random_state=seed)
        return train, test, None, None

    def locked_split(self, df, target, share, seed):
        return train_test_split(df, test_size=share, random_state=seed)

    def folds(self, X, y, n, seed=0):
        return list(KFold(n, shuffle=True, random_state=seed).split(X))

    def build(self, family, X, size=None):
        return build(self.kind, X, size)

    def score(self, y_true=None, y_pred=None, y_train=None) -> Score:
        raise NotImplementedError("grouping and unusual have no answer to score; use free_test / score_locked")

    def finite_test_variance(self, score, locked_rows):
        return 0.25 / max(locked_rows, 1)

    def trust(self, grade, score, simple_guess=0.0):
        from ..insights import trust_level
        return trust_level(grade, score, simple_guess)


class GroupingTask(_NoAnswerTask):
    id, kind, plain_name, families = "grouping", "grouping", "natural groups", ("kmeans",)

    def free_test(self, path: str, target=None, config: dict | None = None, unit: str = "") -> baseline.BaselineOutcome:
        df = pd.read_csv(path)
        r = evaluate_grouping(df, k=(config or {}).get("n_clusters"))
        samples = _timings(clean(df), "grouping", r["groups"])
        return baseline.BaselineOutcome(accuracy=r["score"], simple_guess_accuracy=0.0, seconds=0.0, samples=samples, model_bytes=None,
                                        train_rows=r["rows"], test_rows=r["rows"], task_type="grouping", score=r["score"], extras=r)


class UnusualTask(_NoAnswerTask):
    id, kind, plain_name, families = "unusual", "unusual", "records that look unlike the rest", ("isolation",)

    def free_test(self, path: str, target=None, config: dict | None = None, unit: str = "") -> baseline.BaselineOutcome:
        df = pd.read_csv(path)
        c = float((config or {}).get("contamination") or CONTAMINATION)
        r = evaluate_unusual(df, contamination=c)
        samples = _timings(clean(df), "unusual", c)
        return baseline.BaselineOutcome(accuracy=r["score"], simple_guess_accuracy=0.0, seconds=0.0, samples=samples, model_bytes=None,
                                        train_rows=r["rows"], test_rows=r["rows"], task_type="unusual", score=r["score"], extras=r)


def fit_final(kind: str, df: pd.DataFrame, config: dict | None = None) -> Pipeline:
    """The paid model: the chosen type fitted on every WORK row (bounded to MAX_ROWS)."""
    X = clean(df)
    cfg = config or {}
    param = cfg.get("n_clusters") if kind == "grouping" else cfg.get("contamination")
    if kind == "grouping" and not param:
        param, _ = _best_k(_pre(X).fit_transform(X), 0)
    return build(kind, X, param).fit(X)
