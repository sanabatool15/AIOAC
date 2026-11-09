"""Phase 3 of specs/agent-data-scientist.md: the profile_data tool and services/data/profile.py."""
import json
import time

import numpy as np
import pandas as pd
import pytest

from app.services import activity
from app.services.agent import context, memory, tools
from app.services.data import datasets, profile
from tests.helpers.builders import ctx

BANNED = ("f1", "precision", "recall", "leakage", "leak", "feature", "skew", "train/test")


def churn(rows=1000, seed=0):
    rng = np.random.default_rng(seed)
    y = np.where(rng.random(rows) < 0.3, "yes", "no")
    df = pd.DataFrame({
        "customer": [f"c{i}" for i in range(rows)],
        "age": rng.integers(18, 80, rows),
        "plan": rng.choice(["basic", "plus", "pro"], rows),
        "cancel_reason": np.where(y == "yes", rng.choice(["price", "moved"], rows), None),
        "perfect": np.where(y == "yes", rng.normal(10, 1, rows), rng.normal(0, 1, rows)),
        "spend_text": [str(round(v, 2)) for v in rng.random(rows) * 100],
        "flat": 7,
        "income": np.where(rng.random(rows) < 0.05, 1e7, rng.normal(50, 5, rows)),
        "churned": y})
    return df


def sus(p):
    return {s["column"]: s for s in p["suspects"]}


def test_target_balance_in_plain_words():
    p = profile.profile(churn(), "churned")
    t = p["target"]
    assert t["kind"] == "category" and set(t["groups_out_of_100"]) == {"yes", "no"}
    assert sum(t["groups_out_of_100"].values()) == 100 and "in 100" in t["balance_text"]
    lop = churn().assign(churned=lambda d: np.where(np.arange(len(d)) % 50 == 0, "yes", "no"))
    assert "lopsided" in profile.profile(lop, "churned")["target"]["balance_text"]


def test_after_the_fact_column_and_name_hint():
    s = sus(profile.profile(churn(), "churned"))
    assert s["cancel_reason"]["strength"] == "strong"
    assert "after" in s["cancel_reason"]["reason"]


def test_near_perfect_single_column():
    s = sus(profile.profile(churn(), "churned"))
    assert s["perfect"]["strength"] == "strong" and "alone" in s["perfect"]["reason"]


def test_text_numbers_outliers_id_constant():
    df = churn()
    one = lambda *cols: sus(profile.profile(df[list(cols) + ["churned"]], "churned"))
    assert "numbers stored as text" in one("spend_text")["spend_text"]["reason"]
    assert "income" not in one("income")            # extreme values are a fact about the column, never a suspect
    assert "label" in one("customer")["customer"]["reason"]
    assert "same value" in one("flat")["flat"]["reason"]
    assert len(profile.profile(df, "churned")["suspects"]) <= profile.MAX_SUSPECTS
    by = {c["name"]: c for c in profile.profile(churn(), "churned", columns=["customer", "spend_text", "plan", "age"])["columns"]}
    assert by["customer"]["kind"] == "id" and by["spend_text"]["kind"] == "number" and by["plan"]["kind"] == "category"
    assert set(by["plan"]["top_values"]) <= {"basic", "plus", "pro"} and by["age"]["min"] == 18


def test_dates_are_recognised_and_clean_columns_are_not_suspects():
    df = churn()
    df["signed_up"] = pd.date_range("2020-01-01", periods=len(df), freq="h").strftime("%Y-%m-%d")
    p = profile.profile(df, "churned", columns=["signed_up", "age"])
    assert {c["name"]: c["kind"] for c in p["columns"]}["signed_up"] == "date"
    assert "age" not in sus(profile.profile(df, "churned")) and "plan" not in sus(profile.profile(df, "churned"))


def test_chosen_columns_default_to_suspects_first_and_cap():
    p = profile.profile(churn(), "churned")
    assert len(p["columns"]) <= 7 and p["columns"][0]["name"] in sus(p)
    assert len(profile.profile(churn(), "churned", columns=list(churn().columns[:9]))["columns"]) <= 8


def wide(cols=60, rows=30000):
    rng = np.random.default_rng(1)
    df = pd.DataFrame({f"column_number_{i}": rng.normal(size=rows) for i in range(cols)})
    df["note_x"] = np.where(rng.random(rows) < 0.5, None, "abc")
    df["y"] = np.where(rng.random(rows) < 0.2, "yes", "no")
    return df


def test_wide_file_is_small_and_fast_and_plain():
    df = wide()
    t = time.monotonic()
    p = profile.profile(df, "y")
    took = time.monotonic() - t
    text = json.dumps(p, separators=(",", ":"))
    assert len(text) < 1800 and took < 3.0, (len(text), took)
    assert not any(w in text.lower() for w in BANNED)
    assert p["rows"] == 30000 and p["columns_total"] == 62


def test_suspect_reasons_use_no_jargon():
    text = json.dumps(profile.profile(churn(), "churned")).lower()
    assert not any(w in text for w in BANNED)


def test_number_target_has_no_groups():
    df = pd.DataFrame({"x": np.arange(100.0), "copy": np.arange(100.0) * 2, "price": np.arange(100.0) * 3 + np.random.default_rng(0).normal(size=100)})
    p = profile.profile(df, "price")
    assert p["target"]["kind"] == "number" and "groups_out_of_100" not in p["target"]
    assert "x" in sus(p)


# ------------------------------------------------------------------ the tool

@pytest.fixture
def chosen(session, storage, project):
    c = datasets.add_candidate(session, storage, project, "churn", "bundled", churn().to_csv(index=False).encode())
    datasets.select_candidate(session, storage, project, c.id, "churned")
    return project


def test_tool_marks_dataset_text_and_stays_small(session, storage, provider, chosen):
    out = tools.TOOLS["profile_data"].fn(ctx(session, storage, provider, chosen), {})
    for k in ("target", "columns", "suspects"):
        assert context.UNTRUSTED_TAG in out[k]
    assert out["rows"] == 1000
    assert len(context.compact(out)) == len(json.dumps(out)) and len(json.dumps(out)) < 2500


def test_tool_rejects_unknown_columns_and_unchosen_data(session, storage, provider, chosen, project):
    out = tools.TOOLS["profile_data"].fn(ctx(session, storage, provider, chosen), {"columns": ["age", "nope"]})
    assert "error" in out and "nope" in out["error"]
    ok = tools.TOOLS["profile_data"].fn(ctx(session, storage, provider, chosen), {"columns": ["age"]})
    assert [c for c in ok["columns"][context.UNTRUSTED_TAG]][0]["name"] == "age"


def test_tool_without_chosen_dataset(session, storage, provider, project):
    assert "error" in tools.TOOLS["profile_data"].fn(ctx(session, storage, provider, project), {})


def test_tool_is_level_zero_and_offered_only_at_the_right_steps():
    from app.services import gate
    t = tools.TOOLS["profile_data"]
    assert t.action == gate.Action.ANALYZE and gate.LEVEL[t.action] == 0
    for st in ("data_chosen", "readiness_done", "baseline_done", "quoted"):
        assert "profile_data" in context.tool_names(st)
    for st in ("described", "awaiting_payment", "paid", "training", "done", "failed", "stopped", "voided"):
        assert "profile_data" not in context.tool_names(st)
    assert t.parameters["properties"]["columns"]["maxItems"] == 8


def test_stub_and_activity_sentence():
    assert memory.stub_for("profile_data", {"rows": 5, "columns_total": 3, "suspects": [], "columns": []}).startswith("profile_data: ok")
    assert activity.TRACE_STEP["profile_data"]
    lines = activity._tool_lines("profile_data", {}, {"rows": 5}, {})
    assert lines == [("check", "Looked at the columns of your data")]


# ------------------------------------------------------------------ real-dataset fixes

def frame(n=400, seed=3, **cols):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 2, n)
    d = {"noise": rng.normal(size=n), "kind": rng.choice(["a", "b", "c"], n)}
    d.update({k: (v(y, rng) if callable(v) else v) for k, v in cols.items()})
    return pd.DataFrame(d), y


@pytest.mark.parametrize("labels", [("0", "1"), ("1", "2"), (0, 1), (True, False)])
def test_numeric_looking_target_is_groups(labels):
    df, y = frame(gone=lambda y, r: np.where(y == 1, r.choice([1.0, np.nan], len(y), p=[0.95, 0.05]), np.nan))
    df["t"] = [labels[i] for i in y]
    t = profile.profile(df, "t")["target"]
    assert t["kind"] == "category" and "groups_out_of_100" in t and "in 100" in t["balance_text"]
    # target based checks are on again: a column filled only for one answer is flagged
    assert "gone" in sus(profile.profile(df, "t"))


def test_many_valued_target_is_still_a_number():
    n = 300
    df = pd.DataFrame({"x": np.arange(n, dtype=float), "price": np.arange(n) * 3.5})
    assert profile.profile(df, "price")["target"]["balance_text"] == "a number, not a few groups"
    df["price"] = df["price"].astype(str)          # numbers stored as text
    assert profile.profile(df, "price")["target"]["kind"] == "number"


def test_extreme_values_are_not_suspects_but_a_column_fact():
    n = 500
    rng = np.random.default_rng(0)
    v = rng.normal(50, 5, n)
    v[:40] = 1e6
    df = pd.DataFrame({"fare": v, "y": rng.choice(["a", "b"], n)})
    p = profile.profile(df, "y")
    assert "fare" not in sus(p)
    assert {c["name"]: c for c in p["columns"]}["fare"]["note"] == "a few very large values"


def test_one_sided_missing_column_is_a_strong_suspect():
    n = 500
    rng = np.random.default_rng(1)
    y = rng.choice(["lived", "died"], n, p=[0.6, 0.4])
    body = np.where((y == "died") & (rng.random(n) < 0.45), rng.integers(1, 300, n).astype(float), np.nan)
    df = pd.DataFrame({"body": body, "age": rng.normal(30, 5, n), "y": y})
    assert (df.body.isna().mean()) >= 0.8
    s = sus(profile.profile(df, "y"))["body"]
    assert s["strength"] == "strong" and "empty" in s["reason"] and "one kind of answer" in s["reason"]
    # empty for everyone alike is not one-sided
    df["body"] = np.where(rng.random(n) < 0.1, rng.normal(size=n), np.nan)
    assert "body" not in sus(profile.profile(df, "y"))


def test_placeholder_markers_count_as_missing_and_input_is_untouched():
    n = 100
    df = pd.DataFrame({"a": ["?", "NA", "N/A", "n/a", "null", "None", "-", " ", "x"] + ["x"] * (n - 9),
                       "b": ["1"] * 50 + ["?"] * 50, "y": ["p", "q"] * 50})
    before = df.copy()
    cols = {c["name"]: c for c in profile.profile(df, "y", columns=["a", "b"])["columns"]}
    assert cols["a"]["missing_percent"] == 8 and cols["b"]["missing_percent"] == 50
    pd.testing.assert_frame_equal(df, before)


def test_duration_name_is_only_a_weak_question():
    n = 300
    rng = np.random.default_rng(2)
    df = pd.DataFrame({"contract_duration": rng.integers(1, 70, n), "call_length": rng.normal(size=n), "y": rng.choice(["a", "b"], n)})
    s = sus(profile.profile(df, "y"))
    for c in ("contract_duration", "call_length"):
        assert s[c]["strength"] == "weak" and "?" in s[c]["reason"] and "after the answer" in s[c]["reason"]
    assert not any(w in json.dumps(s).lower() for w in BANNED)
