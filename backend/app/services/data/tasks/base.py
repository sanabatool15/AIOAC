"""The task-type interface (specs/ml-tasks/01-backend-ml-core.md section 4.1).

A TaskKind says how ONE kind of prediction problem is split, built, scored and compared with a simple guess. The
pilot, the forecast maths and the locked-rows check call it instead of assuming "classification". Every kind returns a
higher-is-better `score` in [0, 1] plus a simple-guess score on the same held-out rows, so the money code only ever
compares `value >= target`.

Pure: pandas and scikit-learn only. No app, database or storage imports (a later slice ships this folder to SageMaker).
"""
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class Score:
    value: float                    # higher is better, 0 to 1, measured on held-out rows
    simple_guess: float             # the same measure for a simple guess on the same rows
    extras: dict = field(default_factory=dict)   # plain-unit numbers for wording (never used by the money code)


class TaskKind(Protocol):
    id: str
    plain_name: str                 # words for the user, no jargon
    needs_target: bool              # False for the kinds with no answer column
    supports_fee: bool              # False: compute only, no success fee
    families: tuple[str, ...]

    def split(self, df: pd.DataFrame, target: str, share: float, seed: int):
        """(X_train, X_test, y_train, y_test) holding out `share` of the rows."""

    def locked_split(self, df: pd.DataFrame, target: str, share: float, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        """(work rows, locked rows). The locked rows are scored once, after the paid run."""

    def folds(self, X: pd.DataFrame, y: pd.Series, n: int, seed: int) -> list:
        """Cross-validation (train index, test index) pairs for the free pilot."""

    def build(self, family: str, X: pd.DataFrame, size: int | None = None):
        """A fresh unfitted model for `family`."""

    def score(self, y_true, y_pred, y_train=None) -> Score:
        """Score predictions on held-out rows; `y_train` is what a simple guess is based on."""

    def finite_test_variance(self, score: float, locked_rows: int) -> float:
        """Variance of the locked-rows score from the finite number of locked rows (added to the forecast's noise)."""
