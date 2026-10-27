"""Forecast maths: pure functions, no database."""
from app.config import settings
from app.services.data import forecast

CURVE = [(100, 0.70, 0.02), (200, 0.74, 0.02), (400, 0.77, 0.02)]


def test_extrapolation_is_conservative_and_ordered():
    p = forecast.extrapolate(CURVE, 4000, 800, 0.80)
    assert 0.77 <= p.predicted <= 0.77 + 0.5 * (1 - 0.77)  # never assumes the error more than halves
    assert 0 <= p.band_low <= p.predicted <= p.band_high <= 1 and 0 <= p.confidence <= 1


def test_confidence_falls_as_the_target_rises():
    c = [forecast.extrapolate(CURVE, 4000, 800, t).confidence for t in (0.7, 0.8, 0.9, 0.99)]
    assert c == sorted(c, reverse=True) and c[0] > 0.9 and c[-1] < 0.05


def test_band_widens_with_distance_from_the_pilot():
    near, far = forecast.extrapolate(CURVE, 800, 800, 0.8), forecast.extrapolate(CURVE, 80_000, 800, 0.8)
    assert far.band_high - far.band_low > near.band_high - near.band_low


def test_no_learning_in_the_curve_means_no_improvement_is_assumed():
    flat = [(100, 0.70, 0.02), (200, 0.70, 0.02), (400, 0.69, 0.02)]
    assert forecast.extrapolate(flat, 4000, 800, 0.8).predicted <= 0.70 + 1e-9


def test_ineligible_reasons_are_plain_and_honest():
    low = forecast.Prediction(0.70, 0.62, 0.78, 0.05)
    assert "best case" in forecast.not_eligible_reason(low, 0.9, 5000) and "5%" in forecast.not_eligible_reason(low, 0.9, 5000)
    unsure = forecast.Prediction(0.80, 0.60, 0.95, 0.40)
    assert "40%" in forecast.not_eligible_reason(unsure, 0.8, 5000)
    assert forecast.not_eligible_reason(forecast.Prediction(0.9, 0.8, 0.95, 0.9), 0.8, 5000) is None
    assert "too little" in forecast.not_eligible_reason(None, 0.8, 100)
    for text in (forecast.not_eligible_reason(low, 0.9, 5000), forecast.not_eligible_reason(None, 0.8, 100)):
        assert not any(w in text.lower() for w in ("f1", "precision", "train/test", "instance"))


def test_suggest_target_is_sellable_and_the_highest_such_target():
    t = forecast.suggest_target(CURVE, 4000, 800)
    assert t is not None and 0.5 <= t <= 0.99
    assert forecast.extrapolate(CURVE, 4000, 800, t).confidence >= settings.forecast_min_confidence
    if t < 0.99:
        assert forecast.extrapolate(CURVE, 4000, 800, round(t + 0.01, 2)).confidence < settings.forecast_min_confidence


def test_suggest_target_is_none_when_nothing_is_sellable():
    assert forecast.suggest_target([(100, 0.30, 0.02), (200, 0.30, 0.02), (400, 0.30, 0.02)], 4000, 800) is None


def test_reason_offers_the_suggested_target():
    low = forecast.Prediction(0.70, 0.62, 0.78, 0.05)
    assert "about 74 out of 100" in forecast.not_eligible_reason(low, 0.9, 5000, 0.74)
    assert "honestly offer" not in forecast.not_eligible_reason(low, 0.9, 5000)
