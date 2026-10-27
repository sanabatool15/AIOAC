"""Training script that runs inside the AWS scikit-learn container (script mode).

Inputs (set by SageMaker):
  SM_CHANNEL_TRAIN     folder holding the dataset CSV (channel "train")
  SM_MODEL_DIR         where model.joblib and metrics.json are written (becomes model.tar.gz)
  hyperparameter --target (name of the answer column), optional --n_estimators (default 300)
Outputs: model.joblib (a scikit-learn Pipeline) and metrics.json.

It reuses `aioac_core` (verbatim copies of app/services/features.py and baseline.py, added to the
source tarball at packaging time) so results are comparable with the local free baseline.

Scikit-learn version: the container's version must match the backend's (a pickled model can fail
or warn under another version). The version used is written to metrics.json and the backend
compares it with the local version.

SIGTERM: SageMaker sends it when the cap or Stop is reached and waits up to 120 seconds. The forest
is grown in small batches; on SIGTERM the loop stops after the current batch and saves what exists.
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

from aioac_core.baseline import _pipeline, _split
from aioac_core.features import prepare_features

BATCH_TREES = 25
STOP = {"requested": False}


def _on_sigterm(signum, frame):
    STOP["requested"] = True


def train(train_dir: str, model_dir: str, target: str, n_estimators: int = 300, should_stop=None) -> dict:
    should_stop = should_stop or (lambda: STOP["requested"])
    files = sorted(glob.glob(os.path.join(train_dir, "*.csv")))
    if not files:
        raise FileNotFoundError(f"no CSV file in {train_dir}")
    df = prepare_features(pd.read_csv(files[0]).dropna(subset=[target]), target)
    Xtr, Xte, ytr, yte = _split(df, target)

    pipe = _pipeline(Xtr, n_estimators)
    pre, clf = pipe.named_steps["pre"], pipe.named_steps["clf"]
    clf.set_params(warm_start=True)
    t0 = time.perf_counter()
    Xt = pre.fit_transform(Xtr)
    built = 0
    while built < n_estimators:
        built = min(built + BATCH_TREES, n_estimators)
        clf.set_params(n_estimators=built)
        clf.fit(Xt, ytr)
        if should_stop() and built < n_estimators:
            break
    seconds = time.perf_counter() - t0
    clf.set_params(warm_start=False)

    acc = float(accuracy_score(yte, pipe.predict(Xte)))
    guess = float(accuracy_score(yte, np.full(len(yte), ytr.mode().iloc[0])))
    metrics = {
        "accuracy": acc, "simple_guess_accuracy": guess, "train_seconds": seconds,
        "trees_built": int(built), "trees_planned": int(n_estimators),
        "interrupted": bool(built < n_estimators), "rows": int(len(df)),
        "sklearn_version": sklearn.__version__,
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
    args, _ = ap.parse_known_args(argv)
    target = args.target
    if target is None:  # decoded hyperparameters, as a fallback
        target = json.loads(os.environ.get("SM_HPS", "{}")).get("target")
    if not target:
        raise SystemExit("missing --target")
    signal.signal(signal.SIGTERM, _on_sigterm)
    m = train(os.environ["SM_CHANNEL_TRAIN"], os.environ.get("SM_MODEL_DIR", "/opt/ml/model"), target, args.n_estimators)
    print(json.dumps(m))


if __name__ == "__main__":
    main()
