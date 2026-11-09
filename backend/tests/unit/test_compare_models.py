"""Phase 5: services/data/compare.py (pure), the compare_models tool, its clues block and wiring."""
import re
import time

import numpy as np
import pandas as pd
import pytest

from app.services import activity, compare_models as compare_service
from app.services.agent import blocks, context, memory, tools
from app.services.data import compare, verification
from tests.helpers.builders import ctx

BANNED = re.compile(r"f1|precision|recall|permutation|importance|feature|leakage|train/test|split|overfit", re.I)


def frame(n=900, seed=0):
    rng = np.random.RandomState(seed)
    a, b = rng.normal(size=n), rng.normal(size=n)
    noise = rng.normal(size=n)
    plan = rng.choice(["x", "y", "z"], n)
    y = ((2.0 * a + 0.5 * b + rng.normal(scale=0.7, size=n)) > 0).astype(int)
    return pd.DataFrame({"strong_col": a, "weak_col": b, "noise_col": noise, "plan": plan, "answer": y})


def kinds(*scores):
    return [{"family": f"f{i}", "name": f"kind {i}", "right_out_of_100": s} for i, s in enumerate(scores)]


def test_verdict_both_branches():
    same = compare.verdict(kinds(80, 79, 81))
    assert "within 2 points of each other" in same and "not the problem" in same
    clear = compare.verdict(kinds(90, 80, 79))
    assert "clearly better" in clear and "kind 0" in clear and "10 points" in clear
    assert "matters a little" in compare.verdict(kinds(85, 84, 80))
    assert "could not compare" in compare.verdict(kinds(80))


def test_compare_shape_clues_order_and_determinism():
    df = frame()
    a = compare.compare(df, "answer")
    assert {k["family"] for k in a["kinds"]} == set(("logistic", "forest", "boosting"))
    assert a["is_estimate"] and a["best"]["family"] in ("logistic", "forest", "boosting")
    cols = [c["column"] for c in a["top_clues"]]
    assert cols[0] == "strong_col" and a["top_clues"][0]["how_much"] == "a lot"
    assert "noise_col" not in cols[:1] and len(cols) <= 5 and "clues, not causes" in a["clues_note"]
    assert all(c["how_much"] in ("a lot", "some", "a little") for c in a["top_clues"])
    b = compare.compare(df, "answer")
    for r in (a, b):
        r.pop("seconds")
    assert a == b                                                    # same input, same numbers (the repeat guard needs this)


def test_rare_group_only_when_lopsided():
    df = frame(1200)
    assert all("rare_group_caught_out_of_100" not in k for k in compare.compare(df, "answer")["kinds"])
    lop = df.copy()
    lop["answer"] = (np.random.RandomState(1).rand(len(lop)) < 0.05).astype(int)
    lop.loc[lop["answer"] == 1, "strong_col"] += 3
    r = compare.compare(lop, "answer")
    assert all("rare_group_caught_out_of_100" in k for k in r["kinds"])


def test_more_data_effect_words():
    rising = compare.more_data_effect([{"training_rows": 100, "accuracy": 0.60}, {"training_rows": 400, "accuracy": 0.72}])
    flat = compare.more_data_effect([{"training_rows": 100, "accuracy": 0.70}, {"training_rows": 400, "accuracy": 0.703}])
    assert rising["trend"] == "rising" and flat["trend"] == "flat"
    assert compare.more_data_effect(None)["trend"] == "unknown" and compare.more_data_effect([])["trend"] == "unknown"
    assert "not a promise" in rising["text"]


def test_runtime_is_bounded_and_rows_are_capped():
    big = frame(20000)
    t0 = time.perf_counter()
    r = compare.compare(big, "answer")
    assert r["rows_used"] == compare.MAX_ROWS and time.perf_counter() - t0 < 25
    # a spent budget still answers: at least one kind is fitted, the rest are skipped
    tight = compare.compare(frame(), "answer", budget_s=0.0)
    assert len(tight["kinds"]) >= 1 and tight["top_clues"] == []


def test_too_little_data_and_one_answer_are_plain_errors():
    assert "error" in compare.compare(frame(30), "answer")
    one = frame(200)
    one["answer"] = 1
    assert "error" in compare.compare(one, "answer")


def test_no_jargon_in_strings():
    r = compare.compare(frame(), "answer")
    strings = [r["verdict"], r["clues_note"], r["note"], r["effect_of_more_data"]["text"]] + [c["plain_effect"] for c in r["top_clues"]] + [k["name"] for k in r["kinds"]]
    for s in strings:
        assert not BANNED.search(s), s
    for verdict in (compare.verdict(kinds(80, 80, 80)), compare.verdict(kinds(90, 70, 69)), compare.verdict(kinds(85, 84, 80))):
        assert not BANNED.search(verdict)


def test_locked_rows_are_never_used(session, storage, chosen, monkeypatch):
    version = __import__("app.repositories.datasets", fromlist=["x"]).get_version(session, chosen.chosen_dataset_version_id)
    work_key, locked_key = verification.split_for(session, storage, version)
    locked = pd.read_csv(storage.path(locked_key))
    seen = {}
    real = compare.compare

    def spy(work, target, curve=None, budget_s=12.0, max_rows=5000):
        seen["work"] = work
        return real(work, target, curve, budget_s, max_rows)

    monkeypatch.setattr(compare, "compare", spy)
    out = compare_service.for_project(session, storage, chosen)
    assert "kinds" in out
    cols = [c for c in locked.columns if c in seen["work"].columns]
    assert len(seen["work"]) == len(pd.read_csv(storage.path(work_key)))
    assert not set(verification.row_keys(seen["work"], cols)) & set(verification.row_keys(locked, cols))
    # a distinct marker on the locked rows never reaches the comparison: the service only opens the work file
    opened = []
    orig = pd.read_csv
    monkeypatch.setattr(compare_service.pd, "read_csv", lambda p, *a, **k: (opened.append(str(p)), orig(p, *a, **k))[1])
    compare_service.for_project(session, storage, chosen)
    assert opened and all(p.endswith("work.csv") for p in opened) and not any(p.endswith("locked.csv") for p in opened)


def test_tool_marks_columns_is_small_and_writes_nothing(session, storage, provider, chosen):
    before = chosen.status
    out = tools.TOOLS["compare_models"].fn(ctx(session, storage, provider, chosen), {})
    assert "kinds" in out and "untrusted_dataset_text" in out["top_clues"]
    assert len(str(out)) < 1800, len(str(out))
    assert chosen.status == before
    again = tools.TOOLS["compare_models"].fn(ctx(session, storage, provider, chosen), {})
    assert again == out                                              # stable across repeated calls


def test_tool_is_free_and_offered_only_when_work_split_and_forecast_exist():
    from app.services import gate
    assert tools.TOOLS["compare_models"].action == gate.Action.ANALYZE and gate.LEVEL[gate.Action.ANALYZE] == 0
    for st in ("baseline_done", "quoted"):
        assert "compare_models" in context.tool_names(st)
    for st in ("described", "data_chosen", "readiness_done", "awaiting_payment", "paid", "training", "done", "stopped", "failed", "voided"):
        assert "compare_models" not in context.tool_names(st)


def test_tool_timeout_gives_a_plain_error(session, storage, provider, chosen, monkeypatch):
    monkeypatch.setattr(tools, "_compare_deadline", lambda: 0.2)
    monkeypatch.setattr(compare_service, "for_project", lambda *a, **k: time.sleep(1.5))
    out = tools.TOOLS["compare_models"].fn(ctx(session, storage, provider, chosen), {})
    assert out == {"error": out["error"]} and "still working on your data" in out["error"]


def test_clues_block_unwraps_and_ignores_errors():
    r = {"kinds": [{}], "verdict": "One kind is clearly better.", "effect_of_more_data": {"text": "More rows barely helped."},
         "top_clues": context.mark([{"column": f"c{i}", "how_much": "some" if i else "a lot", "plain_effect": "x"} for i in range(8)], 160),
         "clues_note": "These are clues, not causes."}
    (b,) = blocks.blocks_from_result("compare_models", r, None)
    assert b["type"] == "clues" and len(b["clues"]) == 5 and b["clues"][0] == {"column": "c0", "how_much": "a lot", "plain_effect": "x"}
    assert b["is_estimate"] and "not causes" in b["note"] and b["more_data"] == "More rows barely helped."
    assert blocks.blocks_from_result("compare_models", {"error": "x"}, None) == []
    assert blocks.blocks_from_result("compare_models", {"kinds": [{}], "top_clues": []}, None)[0]["clues"] == []


def test_wiring_stub_activity_and_skill():
    assert "compare_models" in activity.IN_PROGRESS and activity.TRACE_STEP["compare_models"]
    assert activity._tool_lines("compare_models", {}, {"kinds": []}, {})
    assert "details were shown earlier" in memory.stub_for("compare_models", {"kinds": [1, 2], "verdict": "v"})
    skill = open("app/skills/why-accuracy-is-low-and-what-helps.md").read()
    assert "compare_models" in skill and len(skill.splitlines()) < 60
    assert not re.search(r"\$|PayPal|charge|capture|refund|hold", skill, re.I)
