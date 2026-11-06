"""Measurements, readiness grade and plain-language findings (specs/data.md section 4).

Numbers come from code, never from a model. Same input gives the same grade.
"""
import pandas as pd

from .features import id_like_columns, leaky_columns, numeric_like_columns

GRADES = [(95, "A"), (90, "A-"), (85, "B+"), (80, "B"), (75, "B-"), (70, "C+"), (65, "C"), (55, "D")]


def grade_for(score: int) -> str:
    for floor, g in GRADES:
        if score >= floor:
            return g
    return "F"


def analyze(df: pd.DataFrame, target: str) -> dict:
    rows, cols = df.shape
    ids = id_like_columns(df, target)
    texty_numbers = numeric_like_columns(df, target)
    df = df.drop(columns=ids)
    feats = df.drop(columns=[target])
    missing_pct = float(df.isna().sum().sum() / max(df.size, 1) * 100)
    dupes = int(df.duplicated().sum())
    counts = df[target].value_counts(normalize=True)
    minority = float(counts.min()) if len(counts) else 0.0
    constant = [c for c in feats.columns if feats[c].nunique(dropna=True) <= 1]
    leaky = leaky_columns(df, target)

    score, findings = 100, []

    def add(kind, text, penalty=0):
        nonlocal score
        score -= penalty
        findings.append({"kind": kind, "text": text})

    if ids:
        add("NOTE", f"{len(ids)} column(s) look like row labels (such as an ID) and will be ignored")
    if texty_numbers:
        add("NOTE", f"{len(texty_numbers)} column(s) hold numbers stored as text; they are read as numbers")
    if rows < 300:
        add("NOTE", f"Only {rows:,} rows, which is small for a reliable model", 30)
    elif rows < 1000:
        add("NOTE", f"{rows:,} rows is on the small side", 12)
    else:
        add("OK", "Enough rows to train a useful model")
    if dupes:
        add("NOTE", f"{dupes:,} duplicate rows found (removed automatically)", 5)
    else:
        add("OK", "No duplicate rows")
    if missing_pct > 10:
        add("NOTE", f"{missing_pct:.0f}% of values are missing", 20)
    elif missing_pct > 0:
        add("NOTE", f"{missing_pct:.0f}% of values are missing (filled in automatically)", 3)
    if minority < 0.10:
        add("NOTE", f"Only {minority:.0%} of rows are in the smaller group, so results may lean toward the bigger one", 12)
    elif minority < 0.20:
        add("NOTE", f"Only {minority:.0%} of rows are in the smaller group, so results may lean toward the bigger one", 5)
    if constant:
        add("NOTE", f"{len(constant)} column(s) never change and will be ignored", 3)
    if leaky:
        add("NOTE", "A column looks like a copy of the answer and will be ignored", 25)

    return {
        "measurements": {"rows": rows, "columns": cols, "missing_pct": round(missing_pct, 2),
                         "duplicates": dupes, "minority_share": round(minority, 4),
                         "constant_columns": constant, "leaky_columns": leaky,
                         "id_columns": ids, "numbers_stored_as_text": texty_numbers},
        "findings": findings,
        "score": max(score, 0),
        "grade": grade_for(max(score, 0)),
    }


def trust_level(grade: str, accuracy: float, simple_guess: float) -> str:
    """Low / Medium / High. Combines the readiness grade and how far the baseline beats a simple guess."""
    lift = accuracy - simple_guess
    top = grade in {"A", "A-", "B+"}
    ok = grade in {"A", "A-", "B+", "B", "B-", "C+", "C"}
    if top and lift >= 0.15:
        return "High"
    if ok and lift >= 0.05:
        return "Medium"
    return "Low"
