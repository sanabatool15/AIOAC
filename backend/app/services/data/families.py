"""Model families: ONE place that builds the pipeline for each model type.

The free pilot, the free baseline, the local paid backend and the SageMaker training script all build their model here,
so the family the pilot picked is exactly the family the paid run trains. This file is copied verbatim into the
SageMaker source tarball as `aioac_core.families` (see integrations/aws/sagemaker.SHARED_MODULES), so it must not
import anything from the app: scikit-learn, pandas and the standard library only.

Plain names are for the UI. They name the TYPE that was tested, never a promise of a better result.
"""
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

FAMILIES = ("logistic", "forest", "boosting")
DEFAULT_FAMILY = "forest"
PLAIN_NAMES = {"logistic": "a simple linear model", "forest": "a forest of decision trees", "boosting": "a boosted-trees model"}

# Size of the model in each setting: trees for the forest, rounds for boosting, steps for the linear model.
PILOT_SIZE = {"logistic": 300, "forest": 60, "boosting": 60}   # small and quick: the free pilot
FULL_SIZE = {"logistic": 300, "forest": 300, "boosting": 200}  # what the paid run (and the cost timing) uses


TYPE_NOTE = "This is only the model type we tested, not a promise of a better result."


def type_info(family: str | None) -> dict:
    """What the UI shows: the plain name of the model type and the not-a-promise sentence."""
    fam = family if family in FAMILIES else DEFAULT_FAMILY
    return {"family": fam, "name": PLAIN_NAMES[fam], "note": TYPE_NOTE}


def plain_name(family: str | None) -> str:
    return PLAIN_NAMES.get(family or DEFAULT_FAMILY, PLAIN_NAMES[DEFAULT_FAMILY])


def build(family: str, X: pd.DataFrame, size: int | None = None) -> Pipeline:
    """A fresh, unfitted pipeline: imputation, encoding (and scaling for the linear model), then the classifier."""
    if family not in FAMILIES:
        raise ValueError(f"unknown model family: {family}")
    num = X.select_dtypes(include="number").columns.tolist()
    cat = [c for c in X.columns if c not in num]
    if family == "logistic":
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
    clf = {"logistic": lambda: LogisticRegression(max_iter=n),
           "forest": lambda: RandomForestClassifier(n_estimators=n, random_state=0, n_jobs=1),
           "boosting": lambda: HistGradientBoostingClassifier(max_iter=n, random_state=0)}[family]()
    return Pipeline([("pre", pre), ("clf", clf)])
