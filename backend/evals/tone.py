"""Tone evaluation (specs/agent-data-scientist.md Phase 0): python -m evals.tone --model <id> --repeats 3

Measures how the agent TALKS, not what it does. Each case in evals/tone_cases/*.json gives the user's message and what
the tools have measured. The agent's real system prompt (context.BASE) plus those facts go to the model, and the reply is
checked two ways: cheap word checks (must-contain-any groups, must-not-contain, jargon, promise) and an LLM judge that
scores five things from 1 to 5. It needs a real model and costs tokens, so it never runs in the offline test suite
(`judge_reply` and `evaluate` are tested with a scripted model).

Pass: mean of all judged scores >= 4 and no single score below 3. The judge has no temperature setting in our client
interface; it is asked for strict JSON and a fixed rubric. A hand-rated gold set (evals/tone_gold.json) is kept by a human to
check that the judge agrees with a person; it is not generated.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from app.ports import LLMClient
from app.services.agent.context import BASE
from evals.run import JARGON, makes_promise

CASES_DIR = Path(__file__).parent / "tone_cases"
DIMENSIONS = ("plain_words", "structure", "honest_uncertainty", "warmth", "insight")
RUBRIC = (
    "You grade a reply written by an assistant to a person who has never built a prediction model. Score each from 1 (poor) to 5 (excellent):\n"
    "plain_words: everyday language, no jargon, numbers as 'about N out of 100'.\n"
    "structure: says what was found, what it means for the person, and one recommendation or question, in that order.\n"
    "honest_uncertainty: separates what was measured from what is guessed; never promises a result.\n"
    "warmth: kind and encouraging; bad news is said gently with a way forward.\n"
    "insight: shows real data-science judgement, such as a good question about the person's situation and the WHY behind the number.\n"
    "Use only the facts given. Answer with JSON only: {\"plain_words\":n,\"structure\":n,\"honest_uncertainty\":n,\"warmth\":n,\"insight\":n}"
)


def load_cases(only: list[str] | None = None) -> list[dict]:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES_DIR.glob("*.json"))]
    return [c for c in cases if not only or c["id"] in only]


def case_system(case: dict) -> str:
    """The real prompt shape: BASE + a state block (status, goal, next step) + the skill index, plus what the tools measured.

    Without a state block the model thinks no data has been chosen yet and falls back to 'pick one of the 3 choices'
    (seen in the first real run). A case may set `status` (default baseline_done: the free test already ran).
    """
    from app.services.agent import skills
    from app.services.agent.context import NEXT_STEP
    status = case.get("status", "baseline_done")
    state = f"Goal: {case['user']}\nStatus: {status}\nNext: {NEXT_STEP.get(status, 'Reply helpfully.')}"
    return (f"{BASE}\nCurrent state:\n{state}\n\nSkills (use load_skill):\n{skills.index()}\n\n"
            "What the tools have measured so far (the only numbers you may use):\n" + case["tool_results"])


def generate_reply(llm: LLMClient, case: dict) -> str:
    system = case_system(case)
    r = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": case["user"]}], [])
    return (r.text or "").strip()


def word_checks(case: dict, reply: str) -> dict[str, bool]:
    low = reply.lower()
    return {
        "has_required_content": all(any(w.lower() in low for w in group) for group in case.get("must_contain_any", [])),
        "has_no_forbidden_words": not any(w.lower() in low for w in case.get("must_not_contain", [])),
        "plain_language": JARGON.search(reply) is None,
        "no_accuracy_promise": not makes_promise(reply),
    }


def judge_reply(judge: LLMClient, case: dict, reply: str) -> dict[str, int] | None:
    """Scores 1-5 per dimension, or None when the judge did not return usable JSON."""
    prompt = f"Facts the assistant had:\n{case['tool_results']}\n\nPerson wrote:\n{case['user']}\n\nAssistant replied:\n{reply}"
    r = judge.chat([{"role": "system", "content": RUBRIC}, {"role": "user", "content": prompt}], [])
    m = re.search(r"\{.*\}", r.text or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
        scores = {k: int(data[k]) for k in DIMENSIONS}
    except (ValueError, KeyError, TypeError):
        return None
    return scores if all(1 <= v <= 5 for v in scores.values()) else None


def evaluate(llm: LLMClient, judge: LLMClient, cases: list[dict], repeats: int) -> dict:
    runs = []
    for case in cases:
        for n in range(repeats):
            reply = generate_reply(llm, case)
            runs.append({"case": case["id"], "repeat": n + 1, "reply": reply, "checks": word_checks(case, reply),
                         "scores": judge_reply(judge, case, reply)})
    scored = [r["scores"] for r in runs if r["scores"]]
    all_scores = [v for s in scored for v in s.values()]
    mean = sum(all_scores) / len(all_scores) if all_scores else 0.0
    per_dim = {d: (sum(s[d] for s in scored) / len(scored) if scored else 0.0) for d in DIMENSIONS}
    unjudged = sum(1 for r in runs if not r["scores"])
    words_ok = all(all(r["checks"].values()) for r in runs)
    return {"runs": runs, "mean": mean, "lowest": min(all_scores, default=0), "per_dimension": per_dim, "unjudged": unjudged,
            "word_checks_ok": words_ok, "passed": bool(scored) and unjudged == 0 and mean >= 4 and min(all_scores) >= 3 and words_ok}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals.tone", description=__doc__.split("\n\n")[0])
    ap.add_argument("--model", required=True, help="model id or Azure deployment name (also used as the judge unless --judge-model is given)")
    ap.add_argument("--judge-model")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--cases", nargs="*")
    ap.add_argument("--report-dir", default=str(Path(__file__).parent / "reports"))
    args = ap.parse_args(argv)
    from app.integrations.factory import get_llm
    result = evaluate(get_llm(model=args.model), get_llm(model=args.judge_model or args.model), load_cases(args.cases), args.repeats)
    for r in result["runs"]:
        bad = [k for k, v in r["checks"].items() if not v]
        print(f"{r['case']} #{r['repeat']}: scores={r['scores']} word-check failures={bad or '-'}")
        print("   " + r["reply"].replace("\n", "\n   "))
    print(f"mean {result['mean']:.2f}, lowest {result['lowest']}, per dimension {result['per_dimension']}, unjudged {result['unjudged']}, "
          f"{'PASS' if result['passed'] else 'FAIL'}")
    out = Path(args.report_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "tone-latest.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
