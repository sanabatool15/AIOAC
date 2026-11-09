"""Plain facts about the latest finished run, for the agent's `explain_result` tool. Read-only: stored rows only, no
training, no files, no payment calls. Money comes from the stored payment row exactly as the receipt shows it.

Everything here is a fact or a clue built by code. The model words them; it must not add numbers.
"""
from ..db import Session
from ..db.tables import Project
from ..repositories import datasets as datasets_repo
from ..repositories import forecasts as forecasts_repo
from ..repositories import payments as payments_repo
from ..repositories import training_runs as runs_repo
from .data import families, models as model_versions

FLAT_CURVE = 0.01      # accuracy gain over the pilot's learning curve below which more rows barely help
STEEP_CURVE = 0.03     # gain above which more rows probably help
NEAR_GUESS = 0.03      # verified result within this of the simple guess: the columns may not answer the question


def _usd(cents) -> str:
    return f"${(cents or 0) / 100:,.2f}"


def _out_of_100(x) -> int | None:
    return None if x is None else round(float(x) * 100)


def _money(session: Session, project: Project) -> dict | None:
    pay = payments_repo.latest_for_project(session, project.id)
    if pay is None:
        return None
    charged = pay.compute_captured_cents + pay.fee_captured_cents
    return {"state": pay.state, "held": _usd(pay.amount_cents), "compute_charged": _usd(pay.compute_captured_cents),
            "success_fee_charged": _usd(pay.fee_captured_cents), "released": _usd(pay.released_cents), "total_charged": _usd(charged)}


def _data_changes(session: Session, version_id: str | None) -> list[str]:
    """Notes of the fixed versions in the chain that ends at the data the run used (newest first)."""
    out: list[str] = []
    seen: set[str] = set()
    v = datasets_repo.get_version(session, version_id) if version_id else None
    while v is not None and v.id not in seen and len(out) < 3:
        seen.add(v.id)
        if v.parent_id and v.notes:
            out.append(v.notes)
        v = datasets_repo.get_version(session, v.parent_id) if v.parent_id else None
    return out


def _curve_gain(forecast) -> float | None:
    curve = ((forecast.pilot or {}).get("learning_curve") or []) if forecast else []
    if len(curve) < 2:
        return None
    return float(curve[-1]["accuracy"]) - float(curve[0]["accuracy"])


def what_could_help(*, outcome: str, met: bool | None, verified: float | None, guess: float | None, gain: float | None,
                    fixed: bool, issues: list[str]) -> list[str]:
    """Short, honest pointers built only from stored facts. Clues, not promises; none says anything will be run."""
    tips: list[str] = []
    if outcome == "failed":
        return ["Nothing was lost: the whole hold was released. A new project or a new price estimate starts again."]
    if outcome == "stopped":
        return ["The run was stopped, so no final check was made and no success fee applies."]
    if met:
        return ["The target was reached on the rows kept aside. Trying the model on a few real records is a good next check."]
    if verified is not None and guess is not None and verified - guess <= NEAR_GUESS:
        tips.append("The result is close to what always guessing the most common answer would get. The columns may say little about the answer, so other information about each record may matter more than a different model.")
    elif gain is not None and gain <= FLAT_CURVE:
        tips.append("In the small test, more rows barely changed the result. The columns may say little about the answer; other information about each record could help more than more data.")
    elif gain is not None and gain >= STEEP_CURVE:
        tips.append("In the small test, the result was still rising as the rows grew, so more rows could help (an estimate, not a promise).")
    if issues and not fixed:
        tips.append("The data check left notes that a data fix has not been tried on yet.")
    tips.append("A lower target you would be happy with is another way forward; the Improve button on the result screen starts a free new test.")
    return tips[:4]


def result_facts(session: Session, project: Project) -> dict:
    run = runs_repo.latest_for_project(session, project.id)
    if run is None or run.status == "running":
        return {"error": "there is no finished run to explain yet"}
    from .agent.context import mark   # dataset-derived text is wrapped as untrusted data

    result = run.result or {}
    model = next(iter(runs_repo.models_for_run(session, run.id)), None)
    forecast = forecasts_repo.latest_for_project(session, project.id)
    fam = (model.family if model else None) or (forecast.family if forecast else None)
    out: dict = {"label": "facts from the stored run; the scores are measured, everything about the future is an estimate",
                 "outcome": run.status, "money": _money(session, project)}
    if run.status == "failed":
        out["what_happened"] = "the run failed on our side; the whole hold was released, so nothing was charged"
        out["what_could_help"] = what_could_help(outcome="failed", met=None, verified=None, guess=None, gain=None, fixed=False, issues=[])
        return out
    if run.status == "stopped":
        out["what_happened"] = "the run was stopped by the user; only the compute used so far is charged and there is no success fee"
        out["what_could_help"] = what_could_help(outcome="stopped", met=None, verified=None, guess=None, gain=None, fixed=False, issues=[])
        return out

    v = result.get("verification") or {}
    verified, target = v.get("value"), v.get("target")
    guess = result.get("simple_guess_accuracy")
    free = (project.baseline_result or {}).get("accuracy")
    met = bool(v.get("passed")) if v else None
    out.update(verified_out_of_100=_out_of_100(verified), target_out_of_100=_out_of_100(target), target_met=met,
               simple_guess_out_of_100=_out_of_100(guess), free_test_out_of_100=_out_of_100(free),
               model_type=families.plain_name(fam))
    if model is not None:
        out["version"] = model_versions.version_numbers(runs_repo.models_for_project(session, project.id)).get(model.id)
    if verified is not None and free is not None:
        diff = _out_of_100(verified) - _out_of_100(free)
        out["verified_vs_free_test"] = (f"the final check scored {abs(diff)} out of 100 {'higher' if diff > 0 else 'lower'} than the free test" if diff
                                        else "the final check matched the free test") + "; they use different rows, so a small gap is normal"
    version = datasets_repo.get_version(session, run.dataset_version_id) if run.dataset_version_id else None
    if version is not None:
        out["rows_in_data"] = version.rows
        changes = _data_changes(session, version.id)
        out["data_changes"] = mark(changes, 160) if changes else []
    out["what_could_help"] = what_could_help(
        outcome="done", met=met, verified=verified, guess=guess, gain=_curve_gain(forecast), fixed=bool(out.get("data_changes")),
        issues=list(((forecast.pilot or {}).get("issues") or []) if forecast else []))
    out["next"] = ("explain plainly: the final score against the target and the simple guess, what was charged and released, and one thing that could help; "
                   "never promise a better result and never offer to run or start anything: the Improve or Try a higher target button does that")
    return out
