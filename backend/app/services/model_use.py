"""Use a trained model: describe it, predict one record, predict a CSV, hand out the file. Free of charge.

The model is the scikit-learn Pipeline saved by training (storage key in the `models` table). It was trained on the
cleaned columns (row-ID and answer-copy columns dropped), so the columns offered here are the ones the pipeline learned.
Missing values are filled by the pipeline's own imputers. A scikit-learn version mismatch gives a plain message.
"""
import io
import json
import warnings

import joblib
import numpy as np
import pandas as pd

from ..db import Session
from ..db.tables import Model, Project
from ..ports import LLMClient, Storage
from ..repositories import datasets as datasets_repo
from ..repositories import training_runs as runs_repo
from .data import column_labels

MAX_BATCH_ROWS = 5_000
MAX_BATCH_BYTES = 5 * 1024 * 1024
MAX_CHOICES = 20
NOTE = "an estimate, not a promise"
ESTIMATE_NOTE = "Accuracy figures are estimates from held-back test rows. They are not a promise about future results."


class NoModel(Exception):
    pass


class ModelUnusable(Exception):
    """The file cannot be loaded here (version mismatch, damaged file)."""


class BadInput(Exception):
    """The user's record or CSV cannot be used. The message is plain and safe to show."""


class Loaded:
    def __init__(self, row: Model, pipeline, trained_with: str | None, size: int):
        self.row, self.pipeline, self.trained_with, self.size = row, pipeline, trained_with, size
        pre = pipeline.named_steps["pre"]
        parts = {name: cols for name, _, cols in pre.transformers_ if name in ("num", "cat")}
        self.num: list[str] = list(parts.get("num", []))
        self.cat: list[str] = list(parts.get("cat", []))
        self.columns: list[str] = list(getattr(pipeline, "feature_names_in_", self.num + self.cat))


def current_model(session: Session, project: Project) -> Model:
    row = runs_repo.latest_model(session, project.id)
    if row is None:
        raise NoModel("there is no trained model for this project yet")
    return row


def load(session: Session, storage: Storage, project: Project) -> Loaded:
    row = current_model(session, project)
    try:
        data = storage.get(row.storage_key)
    except Exception:
        raise ModelUnusable("The saved model file could not be found.")
    import sklearn
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pipeline = joblib.load(io.BytesIO(data))
        pipeline.named_steps["pre"].transformers_  # must be a fitted pipeline of the shape we trained
    except Exception:
        raise ModelUnusable("This model was saved with a different version of scikit-learn and cannot be opened here. "
                            "Download the file and open it with the version it was trained with.")
    trained_with = sklearn.__version__
    for w in caught:
        orig = getattr(w.message, "original_sklearn_version", None)
        if orig:
            trained_with = str(orig)
    return Loaded(row, pipeline, trained_with, len(data))


def _imputer_values(m: Loaded) -> dict[str, object]:
    """Example value per column from the pipeline's own fitted imputers (median for numbers, most common for text)."""
    out: dict[str, object] = {}
    pre = m.pipeline.named_steps["pre"]
    for name, trans, cols in pre.transformers_:
        if name == "num":
            for c, v in zip(cols, getattr(trans, "statistics_", [])):
                out[c] = None if v != v else float(v)
        elif name == "cat":
            for c, v in zip(cols, getattr(trans.named_steps["imp"], "statistics_", [])):
                out[c] = None if v is None else str(v)
    return out


def _choices(m: Loaded) -> dict[str, list[str]]:
    pre = m.pipeline.named_steps["pre"]
    for name, trans, cols in pre.transformers_:
        if name == "cat":
            cats = trans.named_steps["oh"].categories_
            return {c: [str(x) for x in cs] for c, cs in zip(cols, cats) if len(cs) <= MAX_CHOICES}
    return {}


def _labels(session: Session, llm: LLMClient | None, project: Project, version, m: Loaded,
            examples: dict[str, object], choices: dict[str, list[str]]) -> dict[str, str]:
    """Plain-English labels for the input columns (empty when unknown). Never raises; see services/data/column_labels."""
    if version is None:
        return {}
    samples = {c: (choices.get(c) or [])[:5] or ([] if examples.get(c) is None else [examples[c]]) for c in m.columns}
    cand = datasets_repo.chosen_candidate(session, project.id)
    return column_labels.labels_for(session, llm, version, m.columns, samples, cand.name if cand else None)


def describe(session: Session, storage: Storage, project: Project, label_llm: LLMClient | None = None) -> dict:
    try:
        row = current_model(session, project)
    except NoModel:
        return {"available": False}
    version = datasets_repo.get_version(session, project.chosen_dataset_version_id) if project.chosen_dataset_version_id else None
    q = row.quality or {}
    base = {"available": True, "trained_at": row.created_at, "target": version.target_column if version else None,
            "accuracy": q.get("accuracy"), "simple_guess_accuracy": q.get("simple_guess_accuracy"),
            "is_estimate_note": ESTIMATE_NOTE, "sklearn_version": None, "size_bytes": None, "usable": False,
            "unusable_reason": None, "columns": [], "classes": []}
    try:
        m = load(session, storage, project)
    except ModelUnusable as exc:
        return {**base, "unusable_reason": str(exc)}
    examples, choices = _imputer_values(m), _choices(m)
    labels = _labels(session, label_llm, project, version, m, examples, choices)
    cols = [{"name": c, "label": labels.get(c), "kind": "number" if c in m.num else "text", "example": examples.get(c),
             "choices": choices.get(c)} for c in m.columns]
    classes = [x.item() if hasattr(x, "item") else x for x in getattr(m.pipeline, "classes_", [])]
    return {**base, "sklearn_version": m.trained_with, "size_bytes": m.size, "usable": True, "columns": cols, "classes": classes}


def _plain(x):
    return x.item() if isinstance(x, np.generic) else x


def _frame(m: Loaded, df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the columns the model knows (any order, any extras are ignored), add the missing ones as empty,
    and read number columns as numbers."""
    known = [c for c in m.columns if c in df.columns]
    if not known:
        raise BadInput("None of your columns match what the model was trained on. Expected: " + ", ".join(m.columns[:12]) + ".")
    out = pd.DataFrame(index=df.index)
    for c in m.columns:
        if c not in df.columns:
            out[c] = np.nan
            continue
        col = df[c]
        if c in m.num:
            nums = pd.to_numeric(col.astype(str).str.strip().replace({"": None, "nan": None, "None": None}), errors="coerce")
            had_value = col.notna() & (col.astype(str).str.strip() != "")
            if (had_value & nums.isna()).any():
                raise BadInput(f"'{c}' must be a number.")
            out[c] = nums
        else:
            s = col.astype(object).where(col.notna(), np.nan)
            out[c] = s.map(lambda v: np.nan if isinstance(v, str) and v.strip() == "" else v)
    return out


def _predict_frame(m: Loaded, frame: pd.DataFrame):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            preds = m.pipeline.predict(frame)
            proba = m.pipeline.predict_proba(frame) if hasattr(m.pipeline, "predict_proba") else None
    except Exception:
        raise ModelUnusable("The model could not make a prediction here. It may have been trained with a different version of "
                            "scikit-learn. Download it and open it with the version it was trained with.")
    return preds, proba


def predict_one(session: Session, storage: Storage, project: Project, record: dict) -> dict:
    if not isinstance(record, dict) or not record:
        raise BadInput("Give at least one value, for example {\"column\": value}.")
    m = load(session, storage, project)
    unknown = [k for k in record if k not in m.columns]
    if unknown:
        raise BadInput("The model does not use: " + ", ".join(str(u)[:40] for u in unknown[:5]) + ". Known columns: " + ", ".join(m.columns[:12]) + ".")
    if all(v is None or (isinstance(v, str) and not v.strip()) for v in record.values()):
        raise BadInput("Give at least one value.")
    df = pd.DataFrame([{k: (None if v is None else v) for k, v in record.items()}])
    preds, proba = _predict_frame(m, _frame(m, df))
    out = {"prediction": _plain(preds[0]), "probabilities": None, "note": NOTE}
    if proba is not None:
        out["probabilities"] = {str(c): round(float(p), 4) for c, p in zip(m.pipeline.classes_, proba[0])}
    return out


def predict_batch(session: Session, storage: Storage, project: Project, csv_text: str) -> dict:
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise BadInput("The file is empty.")
    if len(csv_text.encode("utf-8", "ignore")) > MAX_BATCH_BYTES:
        raise BadInput("The file is too big. The limit is 5 MB.")
    try:
        df = pd.read_csv(io.StringIO(csv_text), nrows=MAX_BATCH_ROWS + 1)
    except Exception:
        raise BadInput("We could not read that as a CSV table.")
    if len(df) == 0:
        raise BadInput("The file has no rows.")
    if len(df) > MAX_BATCH_ROWS:
        raise BadInput(f"Too many rows. The limit is {MAX_BATCH_ROWS:,} rows.")
    m = load(session, storage, project)
    preds, proba = _predict_frame(m, _frame(m, df))
    out = df.copy()
    name = "prediction"
    while name in out.columns:
        name = "_" + name
    out[name] = [_plain(p) for p in preds]
    if proba is not None and "confidence" not in out.columns:
        out["confidence"] = np.round(proba.max(axis=1), 4)
    preview = json.loads(out.head(20).to_json(orient="records"))
    return {"rows": int(len(out)), "columns": [str(c) for c in out.columns], "preview": preview, "csv_text": out.to_csv(index=False)}


def download(session: Session, storage: Storage, project: Project) -> tuple[bytes, str]:
    """The saved file and the scikit-learn version it needs (the app's own version when the file cannot be inspected)."""
    row = current_model(session, project)
    try:
        data = storage.get(row.storage_key)
    except Exception:
        raise ModelUnusable("The saved model file could not be found.")
    try:
        trained_with = load(session, storage, project).trained_with
    except ModelUnusable:
        trained_with = None
    return data, trained_with or "unknown"
