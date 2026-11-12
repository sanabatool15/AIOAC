"""Task types: the registry, how a project's type is read, and a pure guess of the type from the data and the goal.

Only `classification` and `regression` (free test only so far) are built. A project row with no task type (everything made before task types existed) reads as
classification. The other ids are known names so the guess can say what a goal needs; they have no TaskKind yet
(`get` raises UnknownTask), and nothing calls `infer_task_type` to change behaviour in this slice."""
import re

import pandas as pd

from .base import Score, TaskKind
from .classification import ClassificationTask
from .forecast import ForecastTask
from .regression import RegressionTask
from .unsupervised import GroupingTask, UnusualTask

DEFAULT_TASK = "classification"
TASK_IDS = ("classification", "regression", "forecast", "grouping", "unusual")
TASKS: dict[str, TaskKind] = {"classification": ClassificationTask(), "regression": RegressionTask()}
TASKS["forecast"] = ForecastTask()
TASKS["grouping"], TASKS["unusual"] = GroupingTask(), UnusualTask()

MAX_CATEGORY_TARGET = 20   # the same rule as profile.MAX_CATEGORY_TARGET: at most 20 distinct values is a few groups


class UnknownTask(ValueError):
    pass


def get(task_type: str | None) -> TaskKind:
    """The TaskKind for an id; None reads as classification."""
    key = task_type or DEFAULT_TASK
    if key not in TASKS:
        raise UnknownTask(f"task type '{key}' is not built yet" if key in TASK_IDS else f"unknown task type '{key}'")
    return TASKS[key]


def task_of(project) -> TaskKind:
    """The TaskKind of a project (a null `task_type` is classification)."""
    return get(getattr(project, "task_type", None))


_UNUSUAL = re.compile(r"\b(unusual|odd|strange|anomal\w*|outliers?|suspicious|fraud\w*|weird)\b", re.I)
_FUTURE = re.compile(r"\b(forecast|next (?:week|month|quarter|year|day)|over time|in the future|future)\b", re.I)


def _is_date_like(s: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(s):
        return False
    sample = s.dropna().astype(str).head(50)
    if sample.empty or not sample.str.contains(r"\d{4}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}", regex=True).mean() > 0.9:
        return False
    return pd.to_datetime(sample, errors="coerce").notna().mean() > 0.9


def infer_task_type(df: pd.DataFrame, target: str | None, goal_text: str = "") -> str:
    """Pure guess of the task type. No answer column: unusual records if the goal says so, else groups. A date column,
    a number answer and a goal about the future: forecast. A number answer with more than 20 distinct values:
    regression. Everything else: classification (0/1, 1 to 5 stars and text answers are groups)."""
    if not target or target not in df.columns:
        return "unusual" if _UNUSUAL.search(goal_text or "") else "grouping"
    y = df[target].dropna()
    numeric = pd.api.types.is_numeric_dtype(y) or pd.to_numeric(y, errors="coerce").notna().mean() >= 0.9
    if numeric and y.nunique() > MAX_CATEGORY_TARGET:
        if _FUTURE.search(goal_text or "") and any(_is_date_like(df[c]) for c in df.columns if c != target):
            return "forecast"
        return "regression"
    return "classification"


__all__ = ["DEFAULT_TASK", "TASK_IDS", "TASKS", "Score", "TaskKind", "UnknownTask", "get", "task_of", "infer_task_type"]
