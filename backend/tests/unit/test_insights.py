import pandas as pd

from app.services.data.samples import churn_csv
from app.services.data.insights import analyze, grade_for, trust_level
import io


def test_same_input_same_grade():
    df = pd.read_csv(io.BytesIO(churn_csv(1500)))
    assert analyze(df, "left")["grade"] == analyze(df, "left")["grade"]


def test_small_dataset_grades_lower():
    big = analyze(pd.read_csv(io.BytesIO(churn_csv(1500))), "left")["score"]
    small = analyze(pd.read_csv(io.BytesIO(churn_csv(150))), "left")["score"]
    assert small < big


def test_detects_leaky_and_constant_columns():
    df = pd.DataFrame({"a": [1, 2, 3, 4] * 100, "same": [1] * 400, "copy": ["x", "y"] * 200, "y": ["x", "y"] * 200})
    m = analyze(df, "y")["measurements"]
    assert m["leaky_columns"] == ["copy"] and m["constant_columns"] == ["same"]


def test_grade_bands_and_trust():
    assert grade_for(96) == "A" and grade_for(86) == "B+" and grade_for(10) == "F"
    assert trust_level("B+", 0.9, 0.7) == "High"
    assert trust_level("C", 0.76, 0.7) == "Medium"
    assert trust_level("B+", 0.7, 0.7) == "Low"


def test_row_id_and_text_numbers_are_detected_and_ignored():
    n = 400
    df = pd.DataFrame({"customerID": [f"C{i}" for i in range(n)], "total": [str(i % 50) if i % 40 else " " for i in range(n)],
                       "plan": ["a", "b"] * (n // 2), "y": ["x", "y"] * (n // 2)})
    r = analyze(df, "y")
    assert r["measurements"]["id_columns"] == ["customerID"] and r["measurements"]["numbers_stored_as_text"] == ["total"]
    from app.services.data.features import prepare_features
    prep = prepare_features(df, "y")
    assert "customerID" not in prep.columns and pd.api.types.is_numeric_dtype(prep["total"])


def test_duplicates_reported_are_actually_removed_before_training():
    from app.services.data.features import prepare_features
    df = pd.DataFrame({"a": [1, 1, 2, 3], "y": ["x", "x", "y", "x"]})
    assert analyze(df, "y")["measurements"]["duplicates"] == 1 and len(prepare_features(df, "y")) == 3
