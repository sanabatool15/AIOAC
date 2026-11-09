"""Phase 4: services/explain.py, the explain_result tool wiring, and the profile / result chat blocks."""
from datetime import datetime, timezone
from app.db.tables import Quote
from app.repositories import training_runs as runs_repo
from app.services import activity, explain
from app.services.agent import blocks, context, guards, memory, tools

BANNED = ("f1", "precision", "recall", "leakage", "train/test", "overfit")


def test_no_run_is_a_plain_error(session, chosen):
    assert "error" in explain.result_facts(session, chosen)
    assert "error" in tools.TOOLS["explain_result"].fn(
        __import__("tests.helpers.builders", fromlist=["ctx"]).ctx(session, None, None, chosen), {})


def finished(session, project, status, result):
    run = runs_repo.create(session, project.id, "local", None, "x", datetime.now(timezone.utc))
    runs_repo.finish_if_running(session, run, status=status, result=result, cost_cents=0)
    return run


def test_failed_and_stopped_runs_say_what_happened_and_no_score(session, chosen):
    finished(session, chosen, "failed", {"error": "boom"})
    f = explain.result_facts(session, chosen)
    assert f["outcome"] == "failed" and "released" in f["what_happened"] and "verified_out_of_100" not in f
    assert "boom" not in str(f)                                    # internal error text is not passed on
    finished(session, chosen, "stopped", {"stopped_by_user": True})
    s = explain.result_facts(session, chosen)
    assert s["outcome"] == "stopped" and "no success fee" in s["what_happened"]


def test_what_could_help_uses_stored_facts_only():
    h = explain.what_could_help
    base = dict(outcome="done", met=False, verified=0.62, guess=0.60, gain=0.0, fixed=False, issues=[])
    assert any("close to what always guessing" in t for t in h(**base))
    flat = h(**{**base, "verified": 0.7, "gain": 0.004})
    assert any("barely changed" in t for t in flat) and not any("close to what always" in t for t in flat)
    rising = h(**{**base, "verified": 0.7, "gain": 0.08})
    assert any("still rising" in t and "not a promise" in t for t in rising)
    assert any("notes that a data fix has not been tried" in t for t in h(**{**base, "verified": 0.7, "issues": ["x"]}))
    assert not any("data fix" in t for t in h(**{**base, "verified": 0.7, "issues": ["x"], "fixed": True}))
    assert "target was reached" in h(**{**base, "met": True})[0]
    assert len(h(**base)) <= 4
    for tip in flat + rising + h(**{**base, "outcome": "failed"}):
        low = tip.lower()
        assert not any(w in low for w in BANNED), tip
        assert not guards.false_claims(tip, "done"), tip          # never reads as a promise to run something


def test_status_wiring_next_step_stub_activity():
    for st in ("done", "stopped", "failed"):
        assert context.tool_names(st) == ["load_skill", "explain_result"]
        n = context.NEXT_STEP[st]
        assert "explain_result" in n and ("never say or offer" in n or "do not offer" in n)
    assert context.tool_names("voided") == ["load_skill"]
    assert activity.TRACE_STEP["explain_result"]
    assert activity._tool_lines("explain_result", {}, {"outcome": "done"}, {}) == [("check", "Looked back at the finished run to explain it")]
    assert "details were shown earlier" in memory.stub_for("explain_result", {"outcome": "done", "target_met": True})


def test_result_block_from_tool_result_only():
    r = {"outcome": "done", "verified_out_of_100": 82, "target_out_of_100": 80, "simple_guess_out_of_100": 70, "target_met": True,
         "model_type": "a forest of decision trees", "money": {"total_charged": "$0.55"}, "what_could_help": ["x"]}
    (b,) = blocks.blocks_from_result("explain_result", r, None)
    assert b == {"type": "result", "outcome": "done", "verified_out_of_100": 82, "target_out_of_100": 80,
                 "simple_guess_out_of_100": 70, "target_met": True, "model_type": "a forest of decision trees"}
    assert blocks.blocks_from_result("explain_result", {"error": "x"}, None) == []
    assert blocks.blocks_from_result("explain_result", {"outcome": "running"}, None) == []


def test_profile_block_unwraps_marked_text_and_caps_suspects():
    result = {"rows": 900, "columns_total": 12,
              "target": context.mark({"name": "churned", "balance_text": "yes 30 in 100, no 70 in 100", "kind": "category"}, 120),
              "suspects": context.mark([{"column": f"c{i}", "reason": "gives the answer away", "strength": "strong" if i % 2 else "odd"} for i in range(8)], 140),
              "columns": context.mark([], 60)}
    (b,) = blocks.blocks_from_result("profile_data", result, None)
    assert b["type"] == "profile" and b["rows"] == 900 and b["columns_total"] == 12
    assert b["target"] == {"name": "churned", "balance": "yes 30 in 100, no 70 in 100"}
    assert len(b["suspects"]) == 5 and {s["strength"] for s in b["suspects"]} <= {"weak", "strong"}
    assert "untrusted" not in str(b)
    assert blocks.blocks_from_result("profile_data", {"error": "no"}, None) == []
