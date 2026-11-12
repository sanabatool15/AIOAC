"""Training script that runs inside the AWS scikit-learn container (script mode).

Inputs (set by SageMaker):
  SM_CHANNEL_TRAIN     folder holding the dataset CSV (channel "train")
  SM_MODEL_DIR         where model.joblib and metrics.json are written (becomes model.tar.gz)
  hyperparameter --target (name of the answer column), optional --family (logistic | forest | boosting, default forest),
  optional --task_type (classification | regression, default classification; regression families: ridge | forest | boosting),
  optional --n_estimators (forest size, default 300)
Outputs: model.joblib (a scikit-learn Pipeline) and metrics.json.

It reuses `aioac_core` (verbatim copies of app/services/features.py and baseline.py, added to the
source tarball at packaging time) so results are comparable with the local free baseline.

Scikit-learn version: the container's version must match the backend's (a pickled model can fail
or warn under another version). The version used is written to metrics.json and the backend
compares it with the local version.

SIGTERM: SageMaker sends it when the cap or Stop is reached and waits up to 120 seconds. The forest
is grown in small batches; on SIGTERM the loop stops after the current batch and saves what exists. The other
families (linear, boosted trees) are short: they are fitted in one call and saved at the end.
"""
import argparse
import glob
import json
import os
import signal
import time

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from aioac_core import families
from aioac_core.baseline import _split
from aioac_core.features import prepare_features

BATCH_TREES = 25
STOP = {"requested": False}


def _on_sigterm(signum, frame):
    STOP["requested"] = True


def _number(s: pd.Series) -> pd.Series:
    """The answer column as numbers ("$1,200" and "12%" are read as numbers). Same rule as tasks/regression.to_number."""
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(float)
    t = s.astype(str).str.strip().str.replace(r"[$,%\s]", "", regex=True).str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    return pd.to_numeric(t, errors="coerce")


def train(train_dir: str, model_dir: str, target: str, n_estimators: int = 300, should_stop=None, family: str = "forest",
          task_type: str = "classification") -> dict:
    should_stop = should_stop or (lambda: STOP["requested"])
    if task_type not in ("classification", "regression"):
        raise ValueError(f"unknown task type: {task_type}")
    regression = task_type == "regression"
    if family not in (families.REGRESSION_FAMILIES if regression else families.FAMILIES):
        raise ValueError(f"unknown model family: {family}")
    files = sorted(glob.glob(os.path.join(train_dir, "*.csv")))
    if not files:
        raise FileNotFoundError(f"no CSV file in {train_dir}")
    raw = pd.read_csv(files[0])
    if regression:
        raw[target] = _number(raw[target])
    df = prepare_features(raw.dropna(subset=[target]), target)
    if regression:   # same 80/20 split as the local backend (tasks/regression.py), no stratifying on a number
        Xtr, Xte, ytr, yte = train_test_split(df.drop(columns=[target]), df[target], test_size=0.2, random_state=0)
    else:
        Xtr, Xte, ytr, yte = _split(df, target)

    t0 = time.perf_counter()
    if family == "forest":
        pipe = families.build("forest", Xtr, n_estimators, task=task_type)
        pre, clf = pipe.named_steps["pre"], pipe.named_steps["clf"]
        clf.set_params(warm_start=True)
        Xt = pre.fit_transform(Xtr)
        built = 0
        while built < n_estimators:
            built = min(built + BATCH_TREES, n_estimators)
            clf.set_params(n_estimators=built)
            clf.fit(Xt, ytr)
            if should_stop() and built < n_estimators:
                break
        clf.set_params(warm_start=False)
        planned = n_estimators
    else:  # no partial model: fitted in one call (a short job), saved at the end
        pipe = families.build(family, Xtr, task=task_type)
        pipe.fit(Xtr, ytr)
        built = planned = 1
    seconds = time.perf_counter() - t0

    extra = {}
    if regression:   # error reduction against always guessing the training average; the money check re-scores on the locked rows
        error = float(np.mean(np.abs(yte.to_numpy() - pipe.predict(Xte))))
        ref = float(np.mean(np.abs(ytr.to_numpy() - ytr.mean())))
        acc = float(np.clip(1 - error / ref, 0, 1)) if ref > 0 else 0.0
        guess = 0.0
        extra = {"score": acc, "error": error, "guess_error": float(np.mean(np.abs(yte.to_numpy() - ytr.mean()))), "task_type": "regression"}
    else:
        acc = float(accuracy_score(yte, pipe.predict(Xte)))
        guess = float(accuracy_score(yte, np.full(len(yte), ytr.mode().iloc[0])))
    metrics = {
        **extra,
        "accuracy": acc, "simple_guess_accuracy": guess, "train_seconds": seconds,
        "trees_built": int(built), "trees_planned": int(planned),
        "interrupted": bool(built < planned), "rows": int(len(df)),
        "sklearn_version": sklearn.__version__, "family": family,
    }
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(pipe, os.path.join(model_dir, "model.joblib"))
    with open(os.path.join(model_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f)
    return metrics


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=None)
    ap.add_argument("--n_estimators", type=int, default=300)
    ap.add_argument("--family", default=None)
    ap.add_argument("--task_type", default=None)
    args, _ = ap.parse_known_args(argv)
    target = args.target
    if target is None:  # decoded hyperparameters, as a fallback
        target = json.loads(os.environ.get("SM_HPS", "{}")).get("target")
    if not target:
        raise SystemExit("missing --target")
    signal.signal(signal.SIGTERM, _on_sigterm)
    family = args.family or json.loads(os.environ.get("SM_HPS", "{}")).get("family") or "forest"
    task_type = args.task_type or json.loads(os.environ.get("SM_HPS", "{}")).get("task_type") or "classification"
    m = train(os.environ["SM_CHANNEL_TRAIN"], os.environ.get("SM_MODEL_DIR", "/opt/ml/model"), target, args.n_estimators,
              family=family, task_type=task_type)
    print(json.dumps(m))


if __name__ == "__main__":
    main()
