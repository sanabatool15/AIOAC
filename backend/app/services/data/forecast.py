"""Forecast maths: predict the full-run result from a learning curve, with a band and a confidence.

Pure functions, no database. Everything here is an ESTIMATE. Method, kept simple and conservative on purpose:
  curve        the survivor's error at each pilot size against its real training size.
  prediction   error shrinks as size^-c, fitted on the curve with c limited to 0..0.4 and the error never assumed
               to more than halve.
  uncertainty  cross-validation noise, curve-fit scatter, distance from the pilot to the full size, and the finite
               size of the locked test set, added in quadrature.
  confidence   chance the verified result reaches the target, from a normal approximation.
"""
import math
from dataclasses import dataclass

import numpy as np

from ...config import settings

MAX_EXPONENT = 0.4
MAX_ERROR_SHRINK = 0.5      # the full run is never forecast to cut the error by more than half
MIN_SIGMA = 0.015
EXTRAPOLATION_SIGMA = 0.01  # added per doubling of training size beyond the pilot


def _phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


@dataclass
class Prediction:
    predicted: float
    band_low: float
    band_high: float
    confidence: float


def extrapolate(curve: list[tuple[float, float, float]], full_train_rows: int, locked_rows: int, target: float) -> Prediction:
    """curve = [(training rows, accuracy, standard error)] from the survivor. Pure maths, easy to test."""
    ns = np.array([n for n, _, _ in curve], dtype=float)
    err = np.clip(1 - np.array([a for _, a, _ in curve]), 1e-3, 1.0)
    last_n, last_err, last_se = ns[-1], err[-1], curve[-1][2]
    c, scatter = 0.0, 0.0
    if len(curve) >= 2:
        slope, intercept = np.polyfit(np.log(ns), np.log(err), 1)
        c = float(np.clip(-slope, 0.0, MAX_EXPONENT))
        scatter = float(np.std(np.log(err) - (intercept + slope * np.log(ns)))) * last_err
    growth = max(full_train_rows / last_n, 1.0)
    pred_err = max(last_err * growth ** (-c), last_err * MAX_ERROR_SHRINK)
    pred = 1 - pred_err
    p = min(max(pred, 0.01), 0.99)
    sigma = math.sqrt(max(last_se, MIN_SIGMA) ** 2 + scatter ** 2
                      + (EXTRAPOLATION_SIGMA * math.log2(growth)) ** 2 + p * (1 - p) / max(locked_rows, 1))
    confidence = 1 - _phi((target - pred) / sigma)
    return Prediction(round(pred, 4), round(max(0.0, pred - 1.96 * sigma), 4), round(min(1.0, pred + 1.96 * sigma), 4),
                      round(confidence, 3))


def suggest_target(curve: list[tuple[float, float, float]], full_train_rows: int, locked_rows: int) -> float | None:
    """The highest target (0.50 to 0.99) we could honestly sell: confidence at least forecast_min_confidence. None if none."""
    for pct in range(99, 49, -1):
        t = pct / 100
        if extrapolate(curve, full_train_rows, locked_rows, t).confidence >= settings.forecast_min_confidence:
            return t
    return None


def not_eligible_reason(pred: Prediction | None, target: float, rows: int | None, suggested: float | None = None) -> str | None:
    """Plain-words reason the run should not be sold, or None when it is eligible."""
    if rows is not None and rows < settings.forecast_min_rows:
        return (f"There are only {rows:,} usable rows. That is too little for an honest forecast, "
                "so we cannot sell you a full run.")
    if pred is None:
        return "The test run could not produce a forecast for this data."
    if pred.confidence >= settings.forecast_min_confidence:
        return None
    pct = round(pred.confidence * 100)
    offer = f" We can honestly offer a target of about {round(suggested * 100)} out of 100." if suggested is not None else ""
    if pred.band_high < target:
        return (f"Even in the best case we expect about {round(pred.band_high * 100)} out of 100 right, "
                f"below your target of {round(target * 100)}. The chance of reaching it is about {pct}%." + offer)
    return (f"We are only about {pct}% sure the full run would reach your target of {round(target * 100)} out of 100. "
            "That is not enough to sell you a run. A lower target or better data would help." + offer)
