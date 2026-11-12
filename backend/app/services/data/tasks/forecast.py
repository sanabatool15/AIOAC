"""Forecast (a number over time) behind the TaskKind interface (specs/ml-tasks/01 section 2.3), slice S8: features,
simple repeats and the free test. The pilot, the newest-block locked check, training and prediction come later.

Honesty rules this file enforces:
- Rows are not exchangeable. Nothing here shuffles, and a feature for a period only ever sees EARLIER periods.
- The held-out block is the NEWEST periods; the models are fitted on older ones only.
- The score is "how much closer than the best simple repeat" (repeat last period, repeat the same time last cycle, or
  always the average). If no model is clearly better than that, the score is 0 and the run must not be sold.

Pure: pandas, numpy and scikit-learn only; no app, database or storage imports (a later slice ships this folder to
SageMaker). Words for the user live in `services/data/task_wording.py`, not here."""
import time
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from .. import baseline, families
from ..features import prepare_features
from .base import Score
from .regression import RegressionTask, to_number

METRIC = "error_reduction"
MIN_PERIODS = 24            # fewer periods than this cannot even be tested
MIN_GAIN = 0.05             # a model must be at least 5% closer than the best simple repeat to count as better
FREE_TEST_TREES = 100
DEFAULT_HORIZON = 12
LAGS = (1, 2, 3)
SEASON_MIN_CYCLES = 3
SEASON_MIN_CORRELATION = 0.5

PERIOD_WORDS = {"h": "hour", "D": "day", "W": "week", "M": "month", "Q": "quarter", "Y": "year"}
_SEASON_CANDIDATES = {"h": (24, 168), "D": (7, 365), "W": (52,), "M": (12,), "Q": (4,), "Y": ()}
_DATE_PATTERN = r"\d{4}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}"


class ForecastDataError(ValueError):
    """The series cannot be used. The message is plain words for the user."""


# ---- finding the dates --------------------------------------------------------------------------------------------
def _to_dates(s: pd.Series) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(s, errors="coerce")


def detect_time_column(df: pd.DataFrame, target: str | None = None) -> str | None:
    """The first column (not the answer) that holds dates. Plain numbers are never read as dates."""
    for c in df.columns:
        if c == target:
            continue
        col = df[c]
        if pd.api.types.is_datetime64_any_dtype(col):
            return c
        if pd.api.types.is_numeric_dtype(col):
            continue
        sample = col.dropna().astype(str).head(50)
        if sample.empty or not sample.str.contains(_DATE_PATTERN, regex=True).mean() > 0.9:
            continue
        if _to_dates(sample).notna().mean() > 0.9:
            return c
    return None


def _period_alias(dates: pd.Series) -> str:
    """How often the dates repeat, from the typical gap between neighbouring dates."""
    d = pd.DatetimeIndex(dates.dropna().sort_values().unique())
    if len(d) < 3:
        raise ForecastDataError("There are too few different dates to see how often the answer is recorded.")
    step = float(np.median(np.diff(d.values).astype("timedelta64[s]").astype(float))) / 86400.0
    for lo, hi, alias in ((0.03, 0.06, "h"), (0.5, 1.5, "D"), (5, 9, "W"), (26, 33, "M"), (80, 100, "Q"), (350, 380, "Y")):
        if lo <= step <= hi:
            return alias
    raise ForecastDataError("The dates are not evenly spaced (for example every day, week or month), so we cannot test a forecast on them.")


# ---- one regular series ---------------------------------------------------------------------------------------------
def prepare_series(raw: pd.DataFrame, target: str, config: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """A regular series from the file: one row per period, oldest first, column `y` (the answer) plus any columns the
    config lists as `known_columns` (known ahead of time). Rows on the same date are added together (or averaged with
    `aggregate: "mean"`); missing periods and empty answers are filled by joining the points either side. Returns
    (series with a DatetimeIndex, info with counts for the readiness findings)."""
    config = config or {}
    tcol = config.get("time_column") or detect_time_column(raw, target)
    if not tcol or tcol not in raw.columns:
        raise ForecastDataError("We could not find a column with dates, so we cannot test a forecast.")
    known = [c for c in (config.get("known_columns") or []) if c in raw.columns and c not in (tcol, target)]
    others = prepare_features(raw[[c for c in raw.columns if c != tcol]], target, keep=known, dedupe=False)   # converts numbers stored as text
    dates = _to_dates(raw[tcol])
    y = to_number(others[target])
    frame = pd.DataFrame({"t": dates, "y": y})
    for c in known:
        frame[c] = to_number(others[c]) if c in others.columns else np.nan
    bad_dates = int(frame["t"].isna().sum())
    frame = frame.dropna(subset=["t"])
    if frame.empty:
        raise ForecastDataError("None of the dates could be read, so we cannot test a forecast.")
    alias = config.get("period_alias") or _period_alias(frame["t"])
    frame["p"] = frame["t"].dt.to_period({"h": "h", "D": "D", "W": "W", "M": "M", "Q": "Q", "Y": "Y"}[alias])
    repeated = int(len(frame) - frame["p"].nunique())
    how = "mean" if config.get("aggregate") == "mean" else "sum"
    grouped = frame.groupby("p")
    out = pd.DataFrame({"y": grouped["y"].sum(min_count=1) if how == "sum" else grouped["y"].mean()})
    for c in known:
        out[c] = grouped[c].mean()
    full = pd.period_range(out.index.min(), out.index.max(), freq=out.index.freq)
    out = out.reindex(full)
    gaps = int(out["y"].isna().sum())
    missing_answers = int(frame["y"].isna().groupby(frame["p"]).all().sum())   # periods whose rows all had no usable answer
    missing_answers = min(missing_answers, gaps)
    out = out.interpolate(limit_direction="both")
    out.index = out.index.to_timestamp()
    out.index.name = "t"
    info = {"time_column": tcol, "frequency": alias, "period": PERIOD_WORDS[alias], "periods": int(len(out)), "gaps": gaps - missing_answers,
            "missing_answers": missing_answers, "repeated_dates": repeated, "bad_dates": bad_dates, "aggregate": how}
    return out, info


# ---- the season and the horizon --------------------------------------------------------------------------------------
def detect_season(values, freq: str) -> int | None:
    """The length of a repeating pattern, if there is one: the step-to-step changes must correlate with the changes one
    cycle earlier. (Changes, not levels: a random walk or a rising line look 'repeating' in levels.) Needs three cycles."""
    d = np.diff(np.asarray(values, dtype=float))
    best, found = SEASON_MIN_CORRELATION, None
    for c in _SEASON_CANDIDATES.get(freq, ()):
        if len(values) < SEASON_MIN_CYCLES * c or len(d) <= c + 2 or np.std(d) == 0:
            continue
        a, b = d[:-c], d[c:]
        if np.std(a) == 0 or np.std(b) == 0:
            continue
        r = float(np.corrcoef(a, b)[0, 1])
        if r >= best:
            best, found = r, c
    return found


def horizon_for(config: dict | None, season: int | None, n: int) -> int:
    """How many periods ahead the test looks: the user's choice, else one season, else 12; never more than a sixth of the history."""
    h = int((config or {}).get("horizon") or season or DEFAULT_HORIZON)
    return max(1, min(h, n // 6))


def test_block(n: int, horizon: int) -> int:
    """How many of the newest periods are held out: a fifth of them, at least two horizons, at most half."""
    return min(max(int(np.ceil(0.2 * n)), 2 * horizon), n // 2)


def resolve_config(raw: pd.DataFrame, target: str, config: dict | None = None) -> dict:
    """The series settings for a project: what the user or agent chose wins, the rest is read from the data. Raises
    ForecastDataError (plain words) when there is no usable series."""
    cfg = dict(config or {})
    series, info = prepare_series(raw, target, cfg)
    cfg.setdefault("time_column", info["time_column"])
    cfg["frequency"] = info["frequency"]
    cfg.setdefault("aggregate", info["aggregate"])
    if "season" not in cfg:
        cfg["season"] = detect_season(series["y"].to_numpy(), info["frequency"])
    if not cfg.get("horizon"):
        cfg["horizon"] = horizon_for(cfg, cfg["season"], len(series))
    return cfg


# ---- features: a period only ever sees earlier periods -------------------------------------------------------------
@dataclass(frozen=True)
class FeatureSpec:
    freq: str                       # "h", "D", "W", "M", "Q" or "Y"
    season: int | None = None
    lags: tuple = LAGS

    @property
    def windows(self) -> tuple:
        return tuple(sorted({3, self.season or 6}))

    @property
    def need(self) -> int:
        """Earlier periods a row needs before it can be built."""
        return max(max(self.lags), max(self.windows), self.season or 0)


def feature_row(history, date, t: int, spec: FeatureSpec) -> dict:
    """The features for the period AFTER `history` (all earlier values), dated `date`, at position `t`. Used both to
    build the training table and, one step at a time, to forecast ahead."""
    h = np.asarray(history, dtype=float)
    m = len(h)
    row = {}
    for k in spec.lags:
        row[f"lag_{k}"] = float(h[-k]) if m >= k else np.nan
    if spec.season:
        row["lag_season"] = float(h[-spec.season]) if m >= spec.season else np.nan
    for w in spec.windows:
        seg = h[-w:] if m >= w else None
        row[f"roll_mean_{w}"] = float(seg.mean()) if seg is not None else np.nan
        row[f"roll_std_{w}"] = float(seg.std(ddof=1)) if seg is not None else np.nan
    ts = pd.Timestamp(date)
    if spec.freq in ("h", "D", "W", "M", "Q"):
        row["month"] = int(ts.month)
    if spec.freq in ("h", "D"):
        row["dayofweek"] = int(ts.dayofweek)
    if spec.freq in ("W", "D"):
        row["weekofyear"] = int(ts.isocalendar()[1])
    if spec.freq == "h":
        row["hour"] = int(ts.hour)
    row["time_index"] = int(t)
    return row


def make_features(df: pd.DataFrame, time_col: str, target: str, spec: FeatureSpec, extra=()) -> pd.DataFrame:
    """Features plus the answer, one row per period, oldest first. Lags and rolling windows are built only from earlier
    rows, so a row never sees itself or the future. The first rows (not enough earlier periods) are dropped. `extra`
    lists numeric columns known ahead of time (a planned promotion); every other column is left out. The date column
    itself is not a feature: only calendar parts of it are. The index keeps the labels of the rows passed in."""
    d = df.assign(_when=_to_dates(df[time_col])).sort_values("_when", kind="stable")
    y = d[target].to_numpy(dtype=float)
    when = list(d["_when"])
    rows = [feature_row(y[:i], when[i], i, spec) for i in range(spec.need, len(d))]
    out = pd.DataFrame(rows, index=d.index[spec.need:])
    for c in extra:
        out[c] = d[c].to_numpy(dtype=float)[spec.need:]
    out[target] = y[spec.need:]
    return out


# ---- simple repeats (the simple guess) -----------------------------------------------------------------------------
def simple_repeat(kind: str, past, steps: int, season: int | None) -> np.ndarray:
    """What repeating the past would say for the next `steps` periods: "last" (the last value), "seasonal" (the last
    cycle, again and again) or "average" (the average of everything so far)."""
    p = np.asarray(past, dtype=float)
    if kind == "last":
        return np.full(steps, p[-1])
    if kind == "average":
        return np.full(steps, p.mean())
    if kind == "seasonal":
        if not season or len(p) < season:
            raise ValueError("no season to repeat")
        cycle = p[-season:]
        return np.array([cycle[i % season] for i in range(steps)])
    raise ValueError(f"unknown simple repeat: {kind}")


def window_origins(start: int, n: int, horizon: int) -> list[int]:
    """First positions of the held-out windows: back to back, each `horizon` long, all inside the series."""
    return list(range(start, n - horizon + 1, horizon))


def simple_repeat_window_errors(y, start: int, horizon: int, season: int | None) -> dict:
    """For each simple repeat, the average distance from the truth in each held-out window. Each window repeats only
    what came before its own first period."""
    y = np.asarray(y, dtype=float)
    kinds = ("last", "seasonal", "average") if season else ("last", "average")
    out = {k: [] for k in kinds}
    for o in window_origins(start, len(y), horizon):
        actual = y[o:o + horizon]
        for k in kinds:
            out[k].append(float(np.mean(np.abs(actual - simple_repeat(k, y[:o], horizon, season)))))
    return {k: v for k, v in out.items() if v}


def simple_repeat_errors(y, start: int, horizon: int, season: int | None) -> dict:
    """Average distance of each simple repeat from the truth over all the held-out windows."""
    return {k: float(np.mean(v)) for k, v in simple_repeat_window_errors(y, start, horizon, season).items()}


# ---- scoring a model on the held-out windows ------------------------------------------------------------------------
def forecast_ahead(model, history, dates, t0: int, spec: FeatureSpec, columns: list, extra_rows=None) -> np.ndarray:
    """Recursive forecast: predict one period, add the prediction to the history, predict the next. A forecast window
    never sees the actual values inside itself."""
    hist = [float(v) for v in history]
    out = []
    for j, d in enumerate(dates):
        row = feature_row(hist, d, t0 + j, spec)
        if extra_rows is not None:
            row.update(extra_rows[j])
        p = float(model.predict(pd.DataFrame([row], columns=columns))[0])
        hist.append(p)
        out.append(p)
    return np.array(out)


def window_errors(model, y, dates, start: int, horizon: int, spec: FeatureSpec, columns: list, known=None) -> list[float]:
    """Average distance from the truth in each held-out window (a list, one number per window)."""
    errs = []
    for o in window_origins(start, len(y), horizon):
        extra = [{c: float(known[c].iloc[o + j]) for c in known.columns} for j in range(horizon)] if known is not None and len(known.columns) else None
        pred = forecast_ahead(model, y[:o], dates[o:o + horizon], o, spec, columns, extra)
        errs.append(float(np.mean(np.abs(y[o:o + horizon] - pred))))
    return errs


def free_test(path: str, target: str, config: dict | None = None, unit: str = "") -> baseline.BaselineOutcome:
    return free_test_from_frame(pd.read_csv(path), target, config, unit)


def free_test_from_frame(raw: pd.DataFrame, target: str, config: dict | None = None, unit: str = "") -> baseline.BaselineOutcome:
    """The free test for a series. The newest periods are held out; models are fitted on older ones only and forecast
    the held-out block window by window (each window starts from real earlier values). The same windows score the simple
    repeats. Two model types are tried (a straight-line one and a forest) and the closer one is reported. Deterministic."""
    cfg = resolve_config(raw, target, config)
    s, info = prepare_series(raw, target, cfg)
    n = len(s)
    if n < MIN_PERIODS:
        raise ForecastDataError(f"Only {n} periods of history, which is too few to test a forecast (we need at least {MIN_PERIODS}).")
    y = s["y"].to_numpy(dtype=float)
    dates = list(s.index)
    freq, season = cfg["frequency"], cfg.get("season")
    horizon = horizon_for(cfg, season, n)
    block = test_block(n, horizon)
    train_end = n - block
    spec = FeatureSpec(freq, season)
    known_cols = [c for c in (cfg.get("known_columns") or []) if c in s.columns]
    frame = make_features(s.reset_index(), "t", "y", spec, extra=known_cols)
    train = frame[frame.index < train_end]
    if len(train) < 10 or not window_origins(train_end, n, horizon):
        raise ForecastDataError(f"Only {n} periods of history, which is too few to test a forecast.")
    X, yt = train.drop(columns=["y"]), train["y"]
    known = s[known_cols] if known_cols else None
    results = {}
    for fam in ("ridge", "forest"):
        model = families.build(fam, X, FREE_TEST_TREES if fam == "forest" else None, "regression")
        t0 = time.perf_counter()
        model.fit(X, yt)
        secs = time.perf_counter() - t0
        results[fam] = (window_errors(model, y, dates, train_end, horizon, spec, list(X.columns), known), secs)
    family = min(results, key=lambda f: np.mean(results[f][0]))
    per_window, seconds = results[family]
    error = float(np.mean(per_window))
    by_window = simple_repeat_window_errors(y, train_end, horizon, season)
    repeats = {k: float(np.mean(v)) for k, v in by_window.items()}
    best = min(repeats, key=repeats.get)
    guess_error = repeats[best]
    # A model only counts as better than the best simple repeat if it is clearly closer overall, closer in EVERY
    # held-out window, and also closer on earlier stretches it was not fitted on (a lucky run must not be sold).
    beats = guess_error > 0 and error <= (1 - MIN_GAIN) * guess_error and all(m < r for m, r in zip(per_window, by_window[best]))
    if beats:
        for cut in (train_end - horizon, train_end - 2 * horizon):
            past = train[train.index < cut]
            if len(past) < 10:
                continue
            m = families.build(family, X, FREE_TEST_TREES if family == "forest" else None, "regression")
            m.fit(past.drop(columns=["y"]), past["y"])
            back = window_errors(m, y[:cut + horizon], dates[:cut + horizon], cut, horizon, spec, list(X.columns),
                                 known.iloc[:cut + horizon] if known is not None else None)
            rep = simple_repeat_window_errors(y[:cut + horizon], cut, horizon, season)
            if best not in rep or not back[0] < 1.15 * rep[best][0]:
                beats = False
                break
    value = float(np.clip(1 - error / guess_error, 0, 1)) if beats else 0.0
    windows = len(window_origins(train_end, n, horizon))
    extras = {"error": error, "guess_error": guess_error, "unit": unit, "rows_test": windows * horizon, "horizon": horizon,
              "frequency": freq, "period": PERIOD_WORDS[freq], "season": season, "best_simple_repeat": best,
              "simple_repeats": repeats, "beats_simple_repeat": bool(beats), "family": family, "periods": n}
    samples = baseline.sample_timings(frame, "y", family, FREE_TEST_TREES if family == "forest" else None, task="regression")
    return baseline.BaselineOutcome(accuracy=value, simple_guess_accuracy=0.0, seconds=seconds, samples=samples, model_bytes=None,
                                    train_rows=len(train), test_rows=windows * horizon, task_type="forecast", score=value,
                                    error=error, guess_error=guess_error, extras=extras)


# ---- the TaskKind --------------------------------------------------------------------------------------------------
def _in_time_order(df: pd.DataFrame, target: str) -> pd.DataFrame:
    """The rows oldest first by their date column (or as given when there is none). Never random."""
    tcol = detect_time_column(df, target)
    return df if tcol is None else df.loc[_to_dates(df[tcol]).sort_values(kind="stable").index]


class ForecastTask:
    id = "forecast"
    plain_name = "a number over time"
    needs_target = True
    supports_fee = True
    families = families.REGRESSION_FAMILIES

    def split(self, df, target, share=0.2, seed=0):
        """The newest `share` of the periods are held out. `seed` changes nothing: there is nothing random."""
        d = _in_time_order(df, target)
        k = max(1, round(share * len(d)))
        old, new = d.iloc[:-k], d.iloc[-k:]
        return old.drop(columns=[target]), new.drop(columns=[target]), old[target], new[target]

    def locked_split(self, df, target, share, seed):
        d = _in_time_order(df, target)
        k = max(1, round(share * len(d)))
        return d.iloc[:-k], d.iloc[-k:]

    def folds(self, X, y, n, seed=0):
        """Expanding windows: each fold trains on everything before its test block. X must be in time order."""
        return list(TimeSeriesSplit(n_splits=n).split(X))

    def build(self, family, X, size=None):
        return families.build(family, X, size, task="regression")

    def score(self, y_true, y_pred, y_train=None, guess_error_ref: float | None = None) -> Score:
        return RegressionTask().score(y_true, y_pred, y_train, guess_error_ref)

    def finite_test_variance(self, score, locked_rows):
        # Same cautious bound as a plain number, plus a fixed extra term because the future can change regime
        # (specs/ml-tasks/01 section 2.3, tuned on real data in a later slice).
        return 0.25 / max(locked_rows, 1) + 0.03 ** 2

    def trust(self, grade, score, simple_guess=0.0):
        from ..insights import trust_level
        return trust_level(grade, score, simple_guess)

    def free_test(self, path: str, target: str, config: dict | None = None, unit: str = "") -> baseline.BaselineOutcome:
        return free_test(path, target, config, unit)


# ---- S9: the paid model, the pilot's learning curve, and the locked-block check ---------------------------------------
_DATE_FREQ = {"h": "h", "D": "D", "W": "W-MON", "M": "MS", "Q": "QS", "Y": "YS"}


class ForecastModel:
    """What the paid run saves: the fitted model plus the history it needs to keep forecasting one period at a time.
    It forecasts forward from the end of the history it was trained on; it never sees newer rows than that."""

    def __init__(self, pipeline, spec: FeatureSpec, columns: list, history, dates, cfg: dict, known_cols: list, family: str):
        self.pipeline, self.spec, self.columns = pipeline, spec, list(columns)
        self.history, self.dates = np.asarray(history, dtype=float), list(dates)
        self.cfg, self.known_cols, self.family = dict(cfg), list(known_cols), family

    def next_dates(self, n: int) -> list:
        return list(pd.date_range(self.dates[-1], periods=n + 1, freq=_DATE_FREQ[self.spec.freq])[1:])

    def forecast(self, n: int, extra_rows=None) -> np.ndarray:
        """The next `n` periods after the end of the history."""
        return forecast_ahead(self.pipeline, self.history, self.next_dates(n), len(self.history), self.spec, self.columns, extra_rows)

    def predict(self, X):   # so code that only knows a model with .predict(rows) still works on feature rows
        return self.pipeline.predict(X)


def _known_cols(cfg: dict, s: pd.DataFrame) -> list:
    return [c for c in (cfg.get("known_columns") or []) if c in s.columns]


def fit_forecaster(raw: pd.DataFrame, target: str, cfg: dict, family: str, size: int | None = None) -> ForecastModel:
    """Fit `family` on every period of `raw` (the WORK rows of the paid run). Raises ForecastDataError (plain words)."""
    cfg = resolve_config(raw, target, cfg)
    s, info = prepare_series(raw, target, cfg)
    spec = FeatureSpec(cfg["frequency"], cfg.get("season"))
    known = _known_cols(cfg, s)
    frame = make_features(s.reset_index(), "t", "y", spec, extra=known)
    if len(frame) < 10:
        raise ForecastDataError(f"Only {len(s)} periods of history, which is too few to train a forecast.")
    X, yt = frame.drop(columns=["y"]), frame["y"]
    pipe = families.build(family, X, size, "regression")
    pipe.fit(X, yt)
    return ForecastModel(pipe, spec, X.columns, s["y"].to_numpy(), list(s.index), cfg, known, family)


def score_locked_block(model: ForecastModel, locked_raw: pd.DataFrame, target: str, guess_error_ref: float) -> dict:
    """Score the finished model ONCE on the newest periods it never saw. Each window starts from real earlier values (the
    model's own history, then the locked periods) and forecasts `horizon` periods ahead without seeing them. The value is
    on the same scale as the target: 1 - typical miss / the frozen miss of the best simple repeat from the pilot."""
    cfg = model.cfg
    s_lock, _ = prepare_series(locked_raw, target, {**cfg, "period_alias": cfg["frequency"]})
    start = len(model.history)
    full_idx = pd.date_range(model.dates[0], periods=start + 1000, freq=_DATE_FREQ[model.spec.freq])
    first_lock = s_lock.index.min()
    pos = int(np.searchsorted(full_idx.values, np.datetime64(first_lock)))
    n_gap = pos - start
    last = s_lock.index.max()
    total = int(np.searchsorted(full_idx.values, np.datetime64(last))) + 1
    y_full = np.concatenate([model.history, np.full(max(n_gap, 0), np.nan), np.nan * np.ones(total - max(pos, start))])
    y_full = pd.Series(y_full[:total]).copy()
    for t, v in s_lock["y"].items():
        y_full.iloc[int(np.searchsorted(full_idx.values, np.datetime64(t)))] = v
    y_full = y_full.interpolate(limit_direction="both").to_numpy(dtype=float)
    dates = list(full_idx[:total])
    horizon = cfg["horizon"]
    if not window_origins(start, total, horizon):
        raise ForecastDataError("The newest periods held back are too few to check the forecast.")
    if model.known_cols:
        raise ForecastDataError("Forecasts that use planned future columns cannot be checked yet.")
    errs = window_errors(model.pipeline, y_full, dates, start, horizon, model.spec, model.columns, None)
    err = float(np.mean(errs))
    return {"value": float(np.clip(1 - err / guess_error_ref, 0, 1)), "typical_error": err,
            "rows": len(errs) * horizon, "windows": len(errs)}


def pilot_curve(work_raw: pd.DataFrame, target: str, cfg: dict) -> dict:
    """The free pilot for a series, on the WORK periods only. The newest block of the work periods is held out and the
    best simple repeat on it gives the frozen scale. Two model types are fitted on growing amounts of the older periods
    (60%, 80%, all) and each is scored on that same block; the closer type is kept. Returns the learning curve and what
    the forecast needs. Raises ForecastDataError."""
    cfg = resolve_config(work_raw, target, cfg)
    s, info = prepare_series(work_raw, target, cfg)
    n = len(s)
    if n < MIN_PERIODS:
        raise ForecastDataError(f"Only {n} periods of history, which is too few to test a forecast (we need at least {MIN_PERIODS}).")
    y = s["y"].to_numpy(dtype=float)
    dates = list(s.index)
    season = cfg.get("season")
    horizon = horizon_for(cfg, season, n)
    block = test_block(n, horizon)
    train_end = n - block
    spec = FeatureSpec(cfg["frequency"], season)
    known = _known_cols(cfg, s)
    if known:
        raise ForecastDataError("Forecasts that use planned future columns cannot be sold yet.")
    frame = make_features(s.reset_index(), "t", "y", spec)
    if not window_origins(train_end, n, horizon) or len(frame[frame.index < train_end]) < 10:
        raise ForecastDataError(f"Only {n} periods of history, which is too few to test a forecast.")
    repeats = simple_repeat_errors(y, train_end, horizon, season)
    best = min(repeats, key=repeats.get)
    ref = repeats[best]
    if ref <= 0:
        raise ForecastDataError("The history repeats itself exactly, so there is nothing to forecast.")
    results: dict[str, list] = {}
    for fam in ("ridge", "forest"):
        pts = []
        for share in (0.6, 0.8, 1.0):
            cut = max(int(round(share * train_end)), spec.need + 10)
            tr = frame[frame.index < min(cut, train_end)]
            if len(tr) < 10:
                continue
            m = families.build(fam, tr.drop(columns=["y"]), FREE_TEST_TREES if fam == "forest" else None, "regression")
            m.fit(tr.drop(columns=["y"]), tr["y"])
            errs = window_errors(m, y, dates, train_end, horizon, spec, list(tr.drop(columns=["y"]).columns), None)
            sc = [float(np.clip(1 - e / ref, 0, 1)) for e in errs]
            pts.append((float(len(tr)), float(np.mean(sc)), float(np.std(sc, ddof=1) / np.sqrt(len(sc))) if len(sc) > 1 else 0.0, errs))
        results[fam] = pts
    family = max(results, key=lambda f: results[f][-1][1] if results[f] else -1)
    pts = results[family]
    if len(pts) < 2:
        raise ForecastDataError(f"Only {n} periods of history, which is too few to test a forecast.")
    last_errs = np.asarray(pts[-1][3], dtype=float)
    return {"curve": [(a, b, c) for a, b, c, _ in pts], "family": family, "ref": ref, "best_simple_repeat": best,
            "horizon": horizon, "periods": n, "full_train_rows": int(len(frame)), "cfg": cfg,
            "abs_error_sd": float(np.std(last_errs, ddof=1)) if len(last_errs) > 1 else 0.0,
            "cost_samples": baseline.sample_timings(frame, "y", family, FREE_TEST_TREES if family == "forest" else None, task="regression"),
            "frame_rows": len(frame)}
