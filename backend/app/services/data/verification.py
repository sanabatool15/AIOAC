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
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from ...db import Session
from ...db.tables import DatasetVersion
from ...ports import Storage
from ...repositories import datasets as datasets_repo
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


def prepare_split(storage: Storage, version_id: str, storage_key: str, target: str,
                  lineage: list[tuple[str, str]] | None = None) -> tuple[str, str]:
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
        _, parent_locked_key = prepare_split(storage, parent_id, parent_key, target, lineage[:-1])
        df = _csv_roundtrip(prepare_features(pd.read_csv(storage.path(storage_key)).dropna(subset=[target]), target))
        locked_parent = pd.read_csv(storage.path(parent_locked_key))
        cols = [c for c in df.columns if c in locked_parent.columns]
        is_locked = row_keys(df, cols).isin(set(row_keys(locked_parent, cols)))
        storage.put(work_key, df[~is_locked].to_csv(index=False).encode())
        storage.put(locked_key, df[is_locked].to_csv(index=False).encode())
        return work_key, locked_key
    df = prepare_features(pd.read_csv(storage.path(storage_key)).dropna(subset=[target]), target)
    try:
        work, locked = train_test_split(df, test_size=LOCKED_SHARE, random_state=SPLIT_SEED, stratify=df[target])
    except ValueError:  # a class with too few rows to stratify
        work, locked = train_test_split(df, test_size=LOCKED_SHARE, random_state=SPLIT_SEED)
    storage.put(work_key, work.to_csv(index=False).encode())
    storage.put(locked_key, locked.to_csv(index=False).encode())
    return work_key, locked_key


def split_for(session: Session, storage: Storage, version: DatasetVersion) -> tuple[str, str]:
    """The work and locked files of a dataset version, inheriting the locked rows from the root version (walks parent_id)."""
    chain, cur = [], version
    while cur.parent_id:
        cur = datasets_repo.get_version(session, cur.parent_id)
        if cur is None:
            break
        chain.append((cur.id, cur.storage_key))
    return prepare_split(storage, version.id, version.storage_key, version.target_column, list(reversed(chain)))


def verify_model(model_bytes: bytes | None, storage: Storage, locked_key: str, target: str) -> dict:
    """Score the finished model on the locked rows. Returns {metric, value, rows}. Raises VerificationError."""
    if not model_bytes:
        raise VerificationError("no model to verify")
    try:
        model = joblib.load(io.BytesIO(model_bytes))
        locked = pd.read_csv(storage.path(locked_key))
        value = float(accuracy_score(locked[target], model.predict(locked.drop(columns=[target]))))
    except Exception as exc:  # a broken model or file is OUR failure, never the buyer's
        raise VerificationError(type(exc).__name__) from exc
    return {"metric": "accuracy", "value": value, "rows": int(len(locked))}
