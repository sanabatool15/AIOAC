"""Look at a dataset column by column, the way a data scientist would. Pure: reads a DataFrame, no SQL, no storage.

Output is small on purpose (it goes into the model's context) and uses plain words. Column names and values in it
come from the user's file, so the caller must mark them as untrusted text.
"""
import re
import time

import pandas as pd

MAX_ROWS = 20_000          # work on a sample of at most this many rows
MAX_COLUMNS = 8            # columns described per call
TIME_BUDGET_S = 1.5        # the single-column predictiveness check stops when this is used up
MAX_SUSPECTS = 5
MAX_TARGET_GROUPS = 6
ID_SHARE = 0.95
OUTLIER_SHARE = 0.03
MAX_CATEGORY_TARGET = 20   # a target with this many distinct values or fewer is a few groups, even if they look like numbers
SPARSE_SHARE = 0.80        # "almost always empty"
ONE_SIDED_SHARE = 0.90     # filled values that fall in one answer group
MISSING_MARKERS = frozenset({"?", "na", "n/a", "null", "none", "-"})

NAME_HINTS = re.compile(r"cancel|refund|outcome|result|resolution|churn|status_after|after_|post_|_after|final_|settled|terminat|closed_(on|date)", re.I)
DATE_VALUE = re.compile(r"^\s*(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.]\d{1,2}[/.]\d{2,4})")
# after-the-fact names that are common words elsewhere (contract duration), so only a weak question for the user
DURATION_HINTS = re.compile(r"duration|call_?length|call_?time|length_?of_?stay|talk_?time|time_?spent", re.I)
STRENGTH = {"weak": 1, "strong": 2}


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """A sample (a copy, the caller's frame is never changed) with empty strings and placeholders like '?' or 'NA' counted as missing."""
    if len(df) > MAX_ROWS:
        df = df.sample(MAX_ROWS, random_state=0)
    df = df.copy()
    for c in df.columns:
        if isinstance(df[c].dtype, pd.CategoricalDtype):
            df[c] = df[c].astype(object)
        if pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_bool_dtype(df[c]) or pd.api.types.is_datetime64_any_dtype(df[c]):
            continue
        s = df[c].astype("string").str.strip()
        df[c] = s.mask(s.str.lower().isin(MISSING_MARKERS) | (s == "")).astype(object)
    return df


def _num(x):
    return float(f"{float(x):.3g}")


def _text_numbers(s: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
        return False
    v = s.dropna().astype(str)
    return len(v) > 0 and pd.to_numeric(v, errors="coerce").notna().mean() >= 0.9


def _kind(s: pd.Series) -> tuple[str, str | None]:
    """(kind, looks_like). kind is number, category, text, date or id."""
    n = len(s)
    v = s.dropna()
    distinct = int(v.nunique())
    if pd.api.types.is_datetime64_any_dtype(s):
        return "date", "date"
    if pd.api.types.is_bool_dtype(s):
        return "category", None
    if pd.api.types.is_numeric_dtype(s):
        whole = pd.api.types.is_integer_dtype(s) or bool((v % 1 == 0).all())
        if n and whole and distinct >= ID_SHARE * n and n >= 20:
            return "id", "id"
        if distinct <= 2:
            return "category", None
        return "number", None
    if len(v) == 0:
        return "category", None
    sample = v.astype(str).iloc[:200]
    if sample.map(lambda x: bool(DATE_VALUE.match(x))).mean() >= 0.9:
        return "date", "date"
    if _text_numbers(s):
        return "number", None
    if n >= 20 and distinct >= ID_SHARE * n:
        return "id", "id"
    avg_words = sample.str.split().str.len().mean()
    if avg_words >= 4 and distinct > 0.5 * max(len(v), 1):
        return "text", "free_text"
    if distinct <= 50:
        return "category", None
    short_codes = sample.str.len().max() <= 12 and not sample.str.contains(" ").any()
    return "text", ("code" if short_codes else "free_text")


def _short(x, n: int = 24) -> str:
    x = str(x)
    return x if len(x) <= n else x[:n] + "..."


def _shares(y: pd.Series) -> dict[str, int]:
    vc = y.value_counts(normalize=True, dropna=True).head(MAX_TARGET_GROUPS)
    return {_short(k): int(round(v * 100)) for k, v in vc.items()}


def _target_part(df: pd.DataFrame, target: str) -> dict:
    y = df[target]
    distinct = int(y.nunique(dropna=True))
    if pd.api.types.is_bool_dtype(y) or distinct <= MAX_CATEGORY_TARGET:
        kind = "category"          # '0'/'1', 1/2 and the like are groups, whatever they look like
    elif pd.api.types.is_numeric_dtype(y) or _text_numbers(y):
        kind = "number"
    else:
        kind = "category"
    out: dict = {"name": target, "kind": kind}
    if kind == "number":
        out["balance_text"] = "a number, not a few groups"
        return out
    vc = y.value_counts(normalize=True, dropna=True)
    if vc.empty:
        out["balance_text"] = "the answer column is empty"
        return out
    out["groups_out_of_100"] = _shares(y)
    big, small = vc.index[0], vc.index[-1]
    if len(vc) == 1:
        out["balance_text"] = f"every row has the same answer ({_short(big)})"
    else:
        txt = f"{_short(big)} is the biggest group, about {round(vc.iloc[0] * 100)} in 100 rows; the smallest, {_short(small)}, is about {round(vc.iloc[-1] * 100)} in 100"
        out["balance_text"] = txt + (" (lopsided)" if vc.iloc[-1] < 0.2 else "")
    return out


def _add(suspects: dict, col: str, reason: str, strength: str) -> None:
    cur = suspects.get(col)
    if cur is None:
        suspects[col] = {"column": col, "reason": reason, "strength": strength}
    else:
        if STRENGTH[strength] > STRENGTH[cur["strength"]]:
            cur["strength"] = strength
        if reason not in cur["reason"] and len(cur["reason"]) < 90:
            cur["reason"] += "; " + reason


def _predictive_accuracy(s: pd.Series, y: pd.Series, kind: str) -> float | None:
    """How often the best guess from this one column alone is right (numbers are cut into 10 bands)."""
    if kind == "number":
        v = pd.to_numeric(s, errors="coerce")
        try:
            key = pd.qcut(v.rank(method="first"), 10, labels=False, duplicates="drop")
        except ValueError:
            return None
        key = key.astype("float").fillna(-1)
    elif kind == "category":
        key = s.astype(str).where(s.notna(), "__missing__")
    else:
        return None
    ct = pd.crosstab(key, y)
    return float(ct.max(axis=1).sum() / max(ct.values.sum(), 1))


def _suspects(df: pd.DataFrame, target: str, kinds: dict, target_part: dict) -> list[dict]:
    sus: dict[str, dict] = {}
    n = len(df)
    y = df[target]
    cat_target = target_part["kind"] == "category" and "groups_out_of_100" in target_part
    started = time.monotonic()
    groups = []
    if cat_target:
        vc = y.value_counts(normalize=True)
        groups = [g for g in vc.index[:MAX_TARGET_GROUPS] if vc[g] >= 0.02]
    base = float(y.value_counts(normalize=True).iloc[0]) if cat_target and len(y.dropna()) else None

    for c in df.columns:
        if c == target:
            continue
        s = df[c]
        kind, _ = kinds[c]
        miss = float(s.isna().mean())
        if NAME_HINTS.search(str(c)):
            _add(sus, c, "its name suggests it is filled in after the answer is known", "weak")
        elif DURATION_HINTS.search(str(c)):
            _add(sus, c, "from its name: is this only known after the answer? worth checking with you", "weak")
        if kind == "id":
            _add(sus, c, "different for almost every row, so it is a label and I would ignore it", "weak")
            continue
        if s.dropna().nunique() <= 1:
            _add(sus, c, "the same value in every row, so it tells us nothing", "weak")
            continue
        if _text_numbers(s):
            _add(sus, c, "numbers stored as text; I read them as numbers", "weak")
        if cat_target and miss >= SPARSE_SHARE and miss < 1.0:
            filled = y[s.notna()].value_counts(normalize=True)
            if len(filled) and (~s.isna()).sum() >= 5 and filled.iloc[0] >= ONE_SIDED_SHARE and filled.iloc[0] - float((y == filled.index[0]).mean()) >= 0.15:
                _add(sus, c, "almost always empty, and filled in only for one kind of answer, so it may be written after the fact", "strong")
        if cat_target and len(groups) >= 2 and 0.0 < miss < 1.0:
            rates = [float(s[y == g].isna().mean()) for g in groups]
            spread = max(rates) - min(rates)
            lo = groups[rates.index(min(rates))]
            if spread >= 0.35:
                # filled in mostly for one answer group: often written down after the outcome is known
                reason = f"filled in mostly when the answer is {_short(lo, 16)}, so it may be written after the fact"
                _add(sus, c, reason, "strong" if spread >= 0.6 else "weak")
        if time.monotonic() - started > TIME_BUDGET_S:
            continue
        if cat_target and kind in ("number", "category") and base is not None:
            if kind == "category" and s.nunique() > min(50, max(n // 20, 2)):
                continue
            acc = _predictive_accuracy(s, y, kind)
            if acc is not None:
                if acc >= 0.97 and acc - base >= 0.10:
                    _add(sus, c, f"this one column alone gets about {int(acc * 100)} in 100 right, so it may give away the answer", "strong")
                elif acc >= 0.90 and acc - base >= 0.15:
                    _add(sus, c, f"this one column alone gets about {int(acc * 100)} in 100 right, which is unusually high", "weak")
        elif target_part["kind"] == "number" and kind == "number":
            both = pd.concat([pd.to_numeric(s, errors="coerce"), pd.to_numeric(y, errors="coerce")], axis=1).dropna()
            if len(both) >= 20:
                r = both.iloc[:, 0].corr(both.iloc[:, 1], method="spearman")
                if pd.notna(r) and abs(r) >= 0.98:
                    _add(sus, c, "it moves almost exactly with the answer, so it may give the answer away", "strong")
    ranked = sorted(sus.values(), key=lambda d: (-STRENGTH[d["strength"]], d["column"]))
    return ranked[:MAX_SUSPECTS]


def _describe(df: pd.DataFrame, c: str, kinds: dict, hinted: bool) -> dict:
    s = df[c]
    kind, looks = kinds[c]
    if looks is None and NAME_HINTS.search(str(c)) and hinted:
        looks = "outcome_word"
    miss = round(float(s.isna().mean()) * 100, 1)
    d: dict = {"name": c, "kind": kind, "missing_percent": int(miss) if miss == int(miss) else miss, "distinct": int(s.nunique(dropna=True))}
    if kind == "category":
        vc = s.value_counts(normalize=True).head(3)
        d["top_values"] = {_short(k, 20): int(round(v * 100)) for k, v in vc.items()}
    elif kind == "number":
        v = pd.to_numeric(s, errors="coerce").dropna()
        if len(v):
            d.update(min=_num(v.min()), median=_num(v.median()), max=_num(v.max()))
            if len(v) >= 20:
                q1, q3 = v.quantile(0.25), v.quantile(0.75)
                if q3 > q1 and float((v > q3 + 3 * (q3 - q1)).mean()) > OUTLIER_SHARE:
                    d["note"] = "a few very large values"
    if looks:
        d["looks_like"] = looks
    return d


def profile(df: pd.DataFrame, target: str, columns: list[str] | None = None, limit: int = MAX_COLUMNS) -> dict:
    """Small, plain-language picture of a dataset. `columns` picks which ones to describe (at most `limit`)."""
    total_rows = len(df)
    df = _clean(df)
    kinds = {c: _kind(df[c]) for c in df.columns}
    tpart = _target_part(df, target)
    suspects = _suspects(df, target, kinds, tpart)
    sus_names = [s["column"] for s in suspects]
    others = [c for c in df.columns if c != target]
    if columns:
        chosen = [c for c in columns if c in df.columns and c != target][:limit]
    else:
        missing = sorted((c for c in others if c not in sus_names), key=lambda c: -float(df[c].isna().mean()))
        chosen = (sus_names + missing)[: max(limit - 1, 1)]
    hinted = set(sus_names)
    return {"rows": total_rows, "columns_total": len(df.columns), "target": tpart,
            "columns": [_describe(df, c, kinds, c in hinted) for c in chosen], "suspects": suspects}
