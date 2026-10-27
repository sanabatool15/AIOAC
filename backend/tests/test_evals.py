"""The evaluation harness itself, tested offline with scripted models."""
import json

from app.config import settings
from app.ports import LLMResponse, ToolCall
from doubles.llm import FakeLLM
from evals import run as evals_run
from doubles.datasets import OfflineSource


def test_cases_are_well_formed():
    cases = evals_run.load_cases()
    assert 6 <= len(cases) <= 12  # 7 original cases + 4 discovery cases
    ids = [c["id"] for c in cases]
    assert len(set(ids)) == len(ids)
    for c in cases:
        assert c["goal"] and c["expected_dataset_kind"] and "expected_first_tools" in c and "must_not" in c


def test_fake_mode_passes_every_case_and_writes_a_report(tmp_path, capsys):
    code = evals_run.main(["--fake", "--repeats", "2", "--report-dir", str(tmp_path), "--log-dir", str(tmp_path / "logs")])
    out = capsys.readouterr().out
    assert code == 0 and "ALL" in out
    report = json.loads(next(tmp_path.glob("eval-*.json")).read_text())
    assert report["summary"]["pass_rate"] == 1.0 and report["summary"]["runs"] == 2 * len(evals_run.load_cases())
    assert report["summary"]["safety_violations"] == 0
    churn = next(r for r in report["runs"] if r["case"] == "churn-subscription")
    assert churn["tools"][:3] == ["search_datasets", "look_at_dataset", "fetch_dataset"] and "select_dataset" in churn["tools"]
    assert churn["final_status"] == "quoted" and churn["gates"]


def test_pressure_case_never_reaches_paid_work(tmp_path):
    evals_run.main(["--fake", "--repeats", "1", "--cases", "pressure-to-pay", "--report-dir", str(tmp_path), "--log-dir", str(tmp_path / "logs")])
    run = json.loads(next(tmp_path.glob("eval-*.json")).read_text())["runs"][0]
    assert {"start_training", "request_payment"} <= set(run["tools"])  # the model tried
    assert run["checks"]["no_paid_work_ran"] is True and run["final_status"] == "quoted"


def test_refuses_without_a_real_key(monkeypatch, capsys, tmp_path):
    for key in ("", "your-openrouter-key"):
        monkeypatch.setattr(settings, "openrouter_api_key", key)
        assert evals_run.main(["--model", "x/y", "--report-dir", str(tmp_path)]) == 2
    assert "OPENROUTER_API_KEY" in capsys.readouterr().err
    assert not list(tmp_path.glob("*.json"))


def test_refuses_without_a_model_id(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-fake-for-test")
    assert evals_run.main(["--report-dir", str(tmp_path)]) == 2


def _case(**extra):
    return {"id": "t", "goal": "predict churn", "expected_dataset_kind": "x", "expected_first_tools": [], "must_not": [],
            "stop_after_first_reply": True, **extra}


def test_checks_catch_a_model_that_lies_about_payment():
    res = evals_run.run_case(_case(), lambda c: FakeLLM([LLMResponse(text="Your payment was received and training has started!")]), OfflineSource)
    assert not res["passed"] and "no_false_claims" in res["failed_checks"]


def test_checks_catch_jargon_and_promises():
    llm = lambda c: FakeLLM([LLMResponse(text="The F1 is high and I guarantee 95% accuracy.")]) # noqa: E731
    res = evals_run.run_case(_case(), llm, OfflineSource)
    assert {"plain_language", "no_accuracy_promise"} <= set(res["failed_checks"])


def test_checks_catch_a_forbidden_tool_and_wrong_tool_order():
    llm = lambda c: FakeLLM([LLMResponse(tool_calls=[ToolCall("1", "fetch_dataset", {"dataset_id": "sample-churn"})]), LLMResponse(text="ok")]) # noqa: E731
    res = evals_run.run_case(_case(must_not=["fetch_dataset"], expected_first_tools=["search_datasets"]), llm, OfflineSource)
    assert "must_not_call" in res["failed_checks"] and "expected_tool_order" in res["failed_checks"]


def test_a_model_that_crashes_is_a_failed_run_not_a_failed_harness():
    class Boom:
        def chat(self, m, t):
            raise RuntimeError("boom")

    res = evals_run.run_case(_case(), lambda c: Boom(), OfflineSource)
    assert not res["passed"] and "no_crash" in res["failed_checks"]


def test_clarifying_question_check():
    ok = evals_run.run_case(_case(expect_clarifying_question=True), lambda c: FakeLLM([LLMResponse(text="Which customers?")]), OfflineSource)
    bad = evals_run.run_case(_case(expect_clarifying_question=True), lambda c: FakeLLM([LLMResponse(text="Sure.")]), OfflineSource)
    assert ok["passed"] and "asked_a_question" in bad["failed_checks"]
