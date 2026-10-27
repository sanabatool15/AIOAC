"""Locked test set and independent verification (specs/payments.md).

The cleaned dataset is split once, with a fixed seed, into WORK rows and LOCKED rows. The free pilot and the paid run
only ever see the work rows. After the paid run, the finished model is scored once on the locked rows. That score,
not the number the training backend reports about itself, decides whether the success fee may be captured.
"""
import io

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from ...ports import Storage
from .features import prepare_features

LOCKED_SHARE = 0.20
SPLIT_SEED = 7


class VerificationError(Exception):
    """Our side could not verify (bad model file, missing data). The user pays nothing in this case."""


def split_keys(version_id: str) -> tuple[str, str]:
    return f"splits/{version_id}/work.csv", f"splits/{version_id}/locked.csv"


def prepare_split(storage: Storage, version_id: str, storage_key: str, target: str) -> tuple[str, str]:
    """Writes work.csv and locked.csv once (the same split every time) and returns their storage keys."""
    work_key, locked_key = split_keys(version_id)
    if storage.exists(work_key) and storage.exists(locked_key):
        return work_key, locked_key
    df = prepare_features(pd.read_csv(storage.path(storage_key)).dropna(subset=[target]), target)
    try:
        work, locked = train_test_split(df, test_size=LOCKED_SHARE, random_state=SPLIT_SEED, stratify=df[target])
    except ValueError:  # a class with too few rows to stratify
        work, locked = train_test_split(df, test_size=LOCKED_SHARE, random_state=SPLIT_SEED)
    storage.put(work_key, work.to_csv(index=False).encode())
    storage.put(locked_key, locked.to_csv(index=False).encode())
    return work_key, locked_key


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
