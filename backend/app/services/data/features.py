"""Shared feature clean-up for readiness and training: ignore row-ID columns and exact copies of the answer, read numbers stored as text."""
import pandas as pd

ID_SHARE = 0.95          # a column this close to all-unique is a row label, not a signal
NUMERIC_SHARE = 0.90     # share of non-empty values that must parse as numbers


def id_like_columns(df: pd.DataFrame, target: str) -> list[str]:
    n = len(df)
    out = []
    for c in df.columns:
        if c == target or n == 0:
            continue
        text_or_int = not pd.api.types.is_float_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])
        if text_or_int and df[c].nunique(dropna=True) >= ID_SHARE * n:
            out.append(c)
    return out


def leaky_columns(df: pd.DataFrame, target: str) -> list[str]:
    """Columns that are an exact copy of the answer column (compared as text). A model must never see these."""
    if target not in df.columns:
        return []
    answer = df[target].astype(str)
    out = []
    for c in df.columns:
        if c == target:
            continue
        try:
            if df[c].astype(str).equals(answer):
                out.append(c)
        except Exception:
            pass
    return out


def numeric_like_columns(df: pd.DataFrame, target: str) -> list[str]:
    out = []
    for c in df.columns:
        if c == target or pd.api.types.is_numeric_dtype(df[c]):
            continue
        s = df[c].dropna().astype(str).str.strip()
        s = s[s != ""]
        if len(s) and pd.to_numeric(s, errors="coerce").notna().mean() >= NUMERIC_SHARE:
            out.append(c)
    return out


def prepare_features(df: pd.DataFrame, target: str) -> pd.DataFrame:
    """Returns df with ID and answer-copy columns dropped, duplicate rows removed, and numeric-looking text converted to numbers."""
    df = df.drop(columns=id_like_columns(df, target))
    df = df.drop(columns=leaky_columns(df, target)).drop_duplicates()
    for c in numeric_like_columns(df, target):
        df[c] = pd.to_numeric(df[c].astype(str).str.strip().replace("", None), errors="coerce")
    return df
