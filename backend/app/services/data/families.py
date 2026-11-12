"""Model families: ONE place that builds the pipeline for each model type.

The free pilot, the free baseline, the local paid backend and the SageMaker training script all build their model here,
so the family the pilot picked is exactly the family the paid run trains. This file is copied verbatim into the
SageMaker source tarball as `aioac_core.families` (see integrations/aws/sagemaker.SHARED_MODULES), so it must not
import anything from the app: scikit-learn, pandas and the standard library only.

Plain names are for the UI. They name the TYPE that was tested, never a promise of a better result.
"""
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier,
                              RandomForestRegressor)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

FAMILIES = ("logistic", "forest", "boosting")
REGRESSION_FAMILIES = ("ridge", "forest", "boosting")   # a number as the answer
DEFAULT_FAMILY = "forest"
PLAIN_NAMES = {"logistic": "a simple linear model", "forest": "a forest of decision trees", "boosting": "a boosted-trees model"}
REGRESSION_PLAIN_NAMES = {"ridge": "a simple straight-line model", "forest": "a forest of decision trees",
                          "boosting": "a boosted-trees model"}

# Size of the model in each setting: trees for the forest, rounds for boosting, steps for the linear model.
PILOT_SIZE = {"logistic": 300, "forest": 60, "boosting": 60, "ridge": 300}   # small and quick: the free pilot
FULL_SIZE = {"logistic": 300, "forest": 300, "boosting": 200, "ridge": 300}  # what the paid run (and the cost timing) uses


UNSUPERVISED_NAMES = {"kmeans": "a grouping model that puts similar records together",
                      "isolation": "a model that spots records unlike the rest"}
TYPE_NOTE = "This is only the model type we tested, not a promise of a better result."


def type_info(family: str | None) -> dict:
    """What the UI shows: the plain name of the model type and the not-a-promise sentence."""
    if family in UNSUPERVISED_NAMES:   # grouping and unusual: a model type of their own
        return {"family": family, "name": UNSUPERVISED_NAMES[family], "note": TYPE_NOTE}
    fam = family if family in FAMILIES else DEFAULT_FAMILY
    return {"family": fam, "name": PLAIN_NAMES[fam], "note": TYPE_NOTE}


def plain_name(family: str | None, task: str = "classification") -> str:
    names = REGRESSION_PLAIN_NAMES if task == "regression" else PLAIN_NAMES
    return names.get(family or DEFAULT_FAMILY, names[DEFAULT_FAMILY])


def build(family: str, X: pd.DataFrame, size: int | None = None, task: str = "classification") -> Pipeline:
    """A fresh, unfitted pipeline: imputation, encoding (and scaling for the linear models), then the estimator.
    `task` is "classification" (default, the original behaviour) or "regression" (a number as the answer)."""
    if task not in ("classification", "regression"):
        raise ValueError(f"unknown task for model families: {task}")
    if family not in (FAMILIES if task == "classification" else REGRESSION_FAMILIES):
        raise ValueError(f"unknown model family: {family}")
    num = X.select_dtypes(include="number").columns.tolist()
    cat = [c for c in X.columns if c not in num]
    if family in ("logistic", "ridge"):
        num_step = Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())])
    else:
        num_step = SimpleImputer(strategy="median")
    dense = family != "forest"   # boosting needs a dense matrix; the forest keeps a sparse one (as the free baseline always did)
    pre = ColumnTransformer([
        ("num", num_step, num),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=not dense))]), cat),
    ])
    n = size if size is not None else FULL_SIZE[family]
    if task == "regression":
        est = {"ridge": lambda: Ridge(alpha=1.0),
               "forest": lambda: RandomForestRegressor(n_estimators=n, random_state=0, n_jobs=1),
               "boosting": lambda: HistGradientBoostingRegressor(max_iter=n, random_state=0)}[family]()
    else:
        est = {"logistic": lambda: LogisticRegression(max_iter=n),
               "forest": lambda: RandomForestClassifier(n_estimators=n, random_state=0, n_jobs=1),
               "boosting": lambda: HistGradientBoostingClassifier(max_iter=n, random_state=0)}[family]()
    return Pipeline([("pre", pre), ("clf", est)])
