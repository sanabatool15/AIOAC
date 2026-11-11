"""Classification (a yes/no or a few groups) behind the TaskKind interface. Behaviour is exactly what the free test,
pilot and locked-rows check did before: stratified splits, accuracy, a simple guess that always says the common answer.
It delegates to baseline.py and families.py, which are also shipped to SageMaker and must not import this package."""
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.model_selection import KFold, StratifiedKFold, train_test_split

from .. import baseline, families
from .base import Score


class ClassificationTask:
    id = "classification"
    plain_name = "yes/no or a few groups"
    needs_target = True
    supports_fee = True
    families = families.FAMILIES

    def split(self, df, target, share=0.2, seed=0):
        X, y = df.drop(columns=[target]), df[target]
        try:
            return train_test_split(X, y, test_size=share, random_state=seed, stratify=y)
        except ValueError:  # a class with too few rows to stratify
            return train_test_split(X, y, test_size=share, random_state=seed)

    def locked_split(self, df, target, share, seed):
        try:
            return train_test_split(df, test_size=share, random_state=seed, stratify=df[target])
        except ValueError:  # a class with too few rows to stratify
            return train_test_split(df, test_size=share, random_state=seed)

    def folds(self, X, y, n, seed=0):
        try:
            return list(StratifiedKFold(n, shuffle=True, random_state=seed).split(X, y))
        except ValueError:
            return list(KFold(n, shuffle=True, random_state=seed).split(X))

    def build(self, family, X, size=None):
        return families.build(family, X, size)

    def score(self, y_true, y_pred, y_train=None):
        acc = float(accuracy_score(y_true, y_pred))
        guess = None
        if y_train is not None:
            guess = float(accuracy_score(y_true, np.full(len(y_true), pd.Series(y_train).mode().iloc[0])))
        return Score(acc, guess if guess is not None else 0.0)

    def finite_test_variance(self, score, locked_rows):
        p = min(max(score, 0.01), 0.99)
        return p * (1 - p) / max(locked_rows, 1)

    def rare_group_recall(self, y_all, y_true, y_pred):
        return baseline.rare_group_recall(y_all, y_true, y_pred)
