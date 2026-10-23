import pandas as pd

from app.samples import churn_csv
from app.services.insights import analyze, grade_for, trust_level
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
