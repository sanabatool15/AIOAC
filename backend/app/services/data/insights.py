"""Measurements, readiness grade and plain-language findings (specs/data.md section 4).

Numbers come from code, never from a model. Same input gives the same grade.
"""
import re

import pandas as pd

from .features import id_like_columns, leaky_columns, numeric_like_columns

GRADES = [(95, "A"), (90, "A-"), (85, "B+"), (80, "B"), (75, "B-"), (70, "C+"), (65, "C"), (55, "D")]


def grade_for(score: int) -> str:
    for floor, g in GRADES:
        if score >= floor:
            return g
    return "F"


def _names(cols: list, limit: int = 5) -> str:
    """Column names for a plain sentence: quoted, short, no control characters or tags (names come from the user's file)."""
    clean = []
    for c in cols[:limit]:
        t = re.sub(r"</?\s*untrusted_dataset_text\s*>", "", str(c), flags=re.I)
        t = "".join(ch for ch in t if ch >= " ")
        clean.append('"' + (t if len(t) <= 40 else t[:40] + "...") + '"')
    more = f" and {len(cols) - limit} more" if len(cols) > limit else ""
    return ", ".join(clean) + more


def _col_word(n: int) -> str:
    return "column" if n == 1 else "columns"


def _look(n: int) -> str:
    return "looks" if n == 1 else "look"


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
        add("NOTE", f"{len(ids)} {_col_word(len(ids))} {_look(len(ids))} like row labels (such as an ID) and will be ignored: {_names(ids)}")
    if texty_numbers:
        add("NOTE", f"{len(texty_numbers)} {_col_word(len(texty_numbers))} hold numbers stored as text and are read as numbers: {_names(texty_numbers)}")
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
        add("NOTE", f"{len(constant)} {_col_word(len(constant))} never change and will be ignored: {_names(constant)}", 3)
    if leaky:
        add("NOTE", f"{_names(leaky)} looks like a copy of the answer and will be ignored" if len(leaky) == 1 else f"{len(leaky)} columns look like copies of the answer and will be ignored: {_names(leaky)}", 25)

    return {
        "measurements": {"rows": rows, "columns": cols, "missing_pct": round(missing_pct, 2),
                         "duplicates": dupes, "minority_share": round(minority, 4),
                         "constant_columns": constant, "leaky_columns": leaky,
                         "id_columns": ids, "numbers_stored_as_text": texty_numbers},
        "findings": findings,
        "score": max(score, 0),
        "grade": grade_for(max(score, 0)),
    }


def summarize(df: pd.DataFrame, target: str, top: int = 5) -> dict:
    """A small, plain summary of what analyze() looked at, for the agent. Column names and group labels are raw
    dataset text: the caller must wrap them (context.mark). Lists are cut to `top` items."""
    rows = len(df)
    ids = id_like_columns(df, target)
    kept = df.drop(columns=ids)
    feats = kept.drop(columns=[target])
    miss = (kept.isna().mean() * 100).round(1)
    miss = miss[miss > 0].sort_values(ascending=False)
    dupes = int(kept.duplicated().sum())
    counts = kept[target].dropna().value_counts(normalize=True)
    balance = None
    if len(counts) >= 2:
        label, share = str(counts.index[-1]), float(counts.iloc[-1])
        balance = {"groups": int(len(counts)), "smallest_group": label[:60], "smallest_group_out_of_100": round(share * 100),
                   "text": f"about {round(share * 100)} in 100 rows are '{label[:60]}', the smallest of {len(counts)} groups"}
    return {
        "rows": rows,
        "missing_columns": [{"column": str(c)[:60], "missing_percent": float(v)} for c, v in miss.head(top).items()],
        "duplicates": {"count": dupes, "out_of_100": round(dupes / rows * 100, 1) if rows else 0.0},
        "balance": balance,
        "ignored_row_label_columns": [str(c)[:60] for c in ids[:top]],
        "ignored_constant_columns": [str(c)[:60] for c in feats.columns if feats[c].nunique(dropna=True) <= 1][:top],
        "ignored_copy_of_answer_columns": [str(c)[:60] for c in leaky_columns(kept, target)[:top]],
        "numbers_stored_as_text_columns": [str(c)[:60] for c in numeric_like_columns(df, target)[:top]],
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
