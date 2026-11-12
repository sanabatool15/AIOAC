"""Loading a saved model file, wherever it was trained.

A model trained on SageMaker is pickled by the training script, where our shared code lives in a package called
`aioac_core` (see integrations/aws/sagemaker.build_source_tarball). The app has no such package, so before a file is
opened the same names are pointed at the app's own modules. Plain scikit-learn pipelines do not need this; the forecast
model and the other task kinds do. Only files our own training wrote are opened."""
import importlib
import io
import sys
import types

import joblib

_ALIASES = {"baseline": "app.services.data.baseline", "features": "app.services.data.features",
            "families": "app.services.data.families"}
_TASK_ALIASES = {n: f"app.services.data.tasks.{n}" for n in ("base", "regression", "forecast", "unsupervised")}


def _package(name: str) -> types.ModuleType:
    mod = sys.modules.get(name)
    if mod is None:
        mod = types.ModuleType(name)
        mod.__path__ = []   # marks it as a package
        sys.modules[name] = mod
    return mod


def ensure_aliases() -> None:
    _package("aioac_core")
    _package("aioac_core.tasks")
    for short, real in _ALIASES.items():
        sys.modules.setdefault(f"aioac_core.{short}", importlib.import_module(real))
    for short, real in _TASK_ALIASES.items():
        sys.modules.setdefault(f"aioac_core.tasks.{short}", importlib.import_module(real))


def load_model(data: bytes):
    ensure_aliases()
    return joblib.load(io.BytesIO(data))
