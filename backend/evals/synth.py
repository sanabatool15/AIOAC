"""Synthetic CSV files for the skill cases (evals/cases with an "upload" entry).

Each kind is built so one situation from a skill file is present: lopsided answers, very few rows, a column that
gives the answer away, and a baseline that is suspiciously good. Seeded, so every run sees the same file.
"""
import io

import numpy as np
import pandas as pd

KINDS = ("lopsided", "tiny", "leak", "too_good")


def make_csv(kind: str, seed: int = 0) -> bytes:
    rng = np.random.default_rng(seed)
    if kind == "lopsided":      # 3% of customers left
        n = 3000
        a = rng.normal(size=n)
        left = (rng.random(n) < 0.03 + 0.02 * (a > 1)).astype(int)
    elif kind == "tiny":        # 80 rows, balanced, real signal
        n = 80
        a = rng.normal(size=n)
        left = (a + rng.normal(scale=0.8, size=n) > 0).astype(int)
    elif kind in ("leak", "too_good"):
        n = 1500
        a = rng.normal(size=n)
        left = (a + rng.normal(scale=1.0, size=n) > 0).astype(int)
    else:
        raise ValueError(f"unknown kind '{kind}', expected one of {KINDS}")
    df = pd.DataFrame({
        "months_active": rng.integers(1, 60, size=n),
        "orders_this_year": rng.integers(0, 30, size=n),
        "support_tickets": rng.integers(0, 6, size=n),
        "plan": rng.choice(["basic", "plus", "pro"], size=n),
        "activity_score": a.round(3),
    })
    if kind == "leak":          # a column that is the answer under another name
        df["cancelled_flag"] = left
    if kind == "too_good":      # a column that nearly decides the answer (99.5% agreement)
        flip = rng.random(n) < 0.005
        df["refund_requested"] = np.where(flip, 1 - left, left)
    df["left"] = left
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()
