"""Locked test set and independent verification (specs/payments.md).

The cleaned dataset is split once, with a fixed seed, into WORK rows and LOCKED rows. The free pilot and the paid run
only ever see the work rows. After the paid run, the finished model is scored once on the locked rows. That score,
not the number the training backend reports about itself, decides whether the success fee may be captured.

The locked rows belong to the ROOT dataset version and never change. A child version (a guided data fix, see fixes.py)
inherits them: its locked rows are the root's locked rows (kept columns only), and its work rows are every other row of
the child. The work set may shrink; no row that is locked (by content, on the columns the child keeps) can ever be in a
child's work set, so models of different versions are scored on the same locked rows and stay comparable.
"""
import io

import joblib
import pandas as pd

from ...db import Session
from ...db.tables import DatasetVersion
from ...ports import Storage
from ...repositories import datasets as datasets_repo
from . import tasks
from .features import prepare_features

LOCKED_SHARE = 0.20
SPLIT_SEED = 7


class VerificationError(Exception):
    """Our side could not verify (bad model file, missing data). The user pays nothing in this case."""


def split_keys(version_id: str) -> tuple[str, str]:
    return f"splits/{version_id}/work.csv", f"splits/{version_id}/locked.csv"


def row_keys(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    """A stable text key per row over `columns`: the same row content gives the same key in every version of the data."""
    keys = pd.Series([""] * len(df), index=df.index, dtype=str)
    for c in columns:
        keys = keys + "\x1f" + df[c].astype("object").where(df[c].notna(), "<missing>").map(str)   # newer pandas keeps NaN through astype(str)
    return keys


def _csv_roundtrip(df: pd.DataFrame) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(df.to_csv(index=False)))


def _read_answer(path: str, target: str, task: str) -> pd.DataFrame:
    """The dataset with rows that have no answer dropped. For a number answer, text like "$1,200" is read as a number
    first, exactly as the free test and the pilot read it, so the locked rows hold numbers."""
    df = pd.read_csv(path)
    if target is None:   # grouping and unusual: no answer column, every row counts
        return df
    if task in ("regression", "forecast"):
        from .tasks.regression import to_number
        df[target] = to_number(df[target])
    return df.dropna(subset=[target])


def _clean(path: str, target: str, task: str) -> pd.DataFrame:
    """The rows both files are cut from. A series over time keeps its date column and its repeated rows: two equal rows
    on different dates are real data, and the date is not a row label."""
    df = _read_answer(path, target, task)
    if target is None:
        from .tasks.unsupervised import clean as clean_no_answer
        return clean_no_answer(df)
    if task == "forecast":
        from .tasks.forecast import detect_time_column
        tcol = detect_time_column(df, target)
        return prepare_features(df, target, keep=[tcol] if tcol else (), dedupe=False)
    return prepare_features(df, target)


def prepare_split(storage: Storage, version_id: str, storage_key: str, target: str,
                  lineage: list[tuple[str, str]] | None = None, task: str = "classification") -> tuple[str, str]:
    """Writes work.csv and locked.csv once (the same split every time) and returns their storage keys.

    `lineage` is the chain of ancestors of this version, ROOT FIRST, as (version id, storage key) pairs. With no lineage
    this version is a root: its split is drawn here. With a lineage the split is inherited from the parent (which is
    in turn inherited from the root), see the module docstring.
    """
    work_key, locked_key = split_keys(version_id)
    if storage.exists(work_key) and storage.exists(locked_key):
        return work_key, locked_key
    if lineage:
        parent_id, parent_key = lineage[-1]
        _, parent_locked_key = prepare_split(storage, parent_id, parent_key, target, lineage[:-1], task)
        df = _csv_roundtrip(_clean(storage.path(storage_key), target, task))
        locked_parent = pd.read_csv(storage.path(parent_locked_key))
        cols = [c for c in df.columns if c in locked_parent.columns]
        is_locked = row_keys(df, cols).isin(set(row_keys(locked_parent, cols)))
        storage.put(work_key, df[~is_locked].to_csv(index=False).encode())
        storage.put(locked_key, df[is_locked].to_csv(index=False).encode())
        return work_key, locked_key
    df = _clean(storage.path(storage_key), target, task)
    work, locked = tasks.get(task).locked_split(df, target, LOCKED_SHARE, SPLIT_SEED)
    storage.put(work_key, work.to_csv(index=False).encode())
    storage.put(locked_key, locked.to_csv(index=False).encode())
    return work_key, locked_key


def split_for(session: Session, storage: Storage, version: DatasetVersion, task: str = "classification") -> tuple[str, str]:
    """The work and locked files of a dataset version, inheriting the locked rows from the root version (walks parent_id)."""
    chain, cur = [], version
    while cur.parent_id:
        cur = datasets_repo.get_version(session, cur.parent_id)
        if cur is None:
            break
        chain.append((cur.id, cur.storage_key))
    return prepare_split(storage, version.id, version.storage_key, version.target_column, list(reversed(chain)), task)


def kind_forecast_score(model, locked, target, ref):
    from .tasks.forecast import score_locked_block
    return score_locked_block(model, locked.assign(**{target: _to_number(locked[target])}), target, ref)


def _to_number(s):
    from .tasks.regression import to_number
    return to_number(s)


def verify_model(model_bytes: bytes | None, storage: Storage, locked_key: str, target: str, task: str = "classification",
                 guess_error_ref: float | None = None, config: dict | None = None) -> dict:
    """Score the finished model on the locked rows. Returns {metric, value, rows}. Raises VerificationError.
    For a number answer `guess_error_ref` is the FROZEN pilot scale (the average-guess distance of the work rows), so the
    value sits on the same scale as the target; without it (a forecast made before this existed) we refuse to check."""
    if not model_bytes:
        raise VerificationError("no model to verify")
    try:
        model = joblib.load(io.BytesIO(model_bytes))
        locked = pd.read_csv(storage.path(locked_key))
        kind = tasks.get(task)
        if not kind.needs_target:   # grouping / unusual: refit on the locked rows and compare (tasks/unsupervised.py)
            from .tasks.unsupervised import score_locked
            res = score_locked(task, model, pd.read_csv(storage.path(locked_key)))
            return {"metric": "steadiness", "value": res["value"], "rows": res["rows"]}
        if task == "forecast":   # the newest periods, forecast window by window from real earlier values (tasks/forecast.py)
            if not guess_error_ref or guess_error_ref <= 0:
                raise VerificationError("no frozen scale for a forecast")
            res = kind_forecast_score(model, pd.read_csv(storage.path(locked_key)), target, guess_error_ref)
            return {"metric": "error_reduction", "value": res["value"], "rows": res["rows"], "typical_error": res["typical_error"]}
        if task == "regression":
            if not guess_error_ref or guess_error_ref <= 0:
                raise VerificationError("no frozen scale for a number answer")
            pred = model.predict(locked.drop(columns=[target]))
            value = kind.score(locked[target], pred, guess_error_ref=guess_error_ref).value
            typical_error = float(abs(locked[target].to_numpy(dtype=float) - pred).mean())   # in the answer's own units
        else:
            value = kind.score(locked[target], model.predict(locked.drop(columns=[target]))).value
    except VerificationError:
        raise
    except Exception as exc:  # a broken model or file is OUR failure, never the buyer's
        raise VerificationError(type(exc).__name__) from exc
    out = {"metric": "error_reduction" if task == "regression" else "accuracy", "value": value, "rows": int(len(locked))}
    if task == "regression":
        out["typical_error"] = typical_error
    return out
