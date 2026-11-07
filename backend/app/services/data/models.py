"""Model versions: which saved model is "in use". Pure rules, no SQL (specs/model-versions-and-improve.md section 5).

Every finished paid run saves one model. A project has exactly one current model. A newer model that scored worse on
the locked rows never takes the place of a better current one by itself; the owner can switch with `use_version`.
Old rows (before versions) have no version number or flag: they are numbered by creation time and the newest is current.
"""
from ...db import Session
from ...db.tables import Model
from ...repositories import training_runs as runs_repo


def verified_value(row: Model) -> float | None:
    """Score on the locked rows. Old rows keep it inside `quality.verification`."""
    if row.verified_value is not None:
        return row.verified_value
    v = (row.quality or {}).get("verification") or {}
    return v.get("value")


def passed(row: Model) -> bool | None:
    if row.passed is not None:
        return row.passed
    v = (row.quality or {}).get("verification") or {}
    return v.get("passed")


def version_numbers(rows: list[Model]) -> dict[str, int]:
    """model id -> version number. Stored numbers win; rows without one are numbered by creation order."""
    return {m.id: m.version_no or i for i, m in enumerate(rows, start=1)}


def should_promote(current: Model | None, new_value: float | None, new_passed: bool) -> bool:
    """True when a freshly trained model should become current without the owner asking.

    - no current model: yes
    - the new one passed and the current did not: yes
    - the current one passed and the new did not: no
    - same outcome on both: yes only if the new score is at least as good (a tie goes to the newer one)
    """
    if current is None:
        return True
    cur_passed, cur_value = bool(passed(current)), verified_value(current)
    if new_passed != cur_passed:
        return new_passed
    if cur_value is None:
        return True
    if new_value is None:
        return False
    return new_value >= cur_value


def record_new_model(session: Session, project_id: str, run_id: str, storage_key: str, result: dict,
                     dataset_version_id: str | None, forecast_id: str | None, quote_id: str | None) -> Model:
    """Save the model of a finished run as the next version and decide whether it becomes current."""
    v = result.get("verification") or {}
    value, ok = v.get("value"), bool(v.get("passed"))
    current = runs_repo.current_model(session, project_id)
    number = runs_repo.next_version_no(session, project_id)
    row = runs_repo.add_model(session, project_id, run_id, storage_key, result, version_no=number,
                              dataset_version_id=dataset_version_id, forecast_id=forecast_id, quote_id=quote_id,
                              verified_value=value, passed=ok if v else None)
    if should_promote(current, value, ok):
        runs_repo.set_current(session, project_id, row.id)
    elif current is not None and not current.is_current:
        runs_repo.set_current(session, project_id, current.id)  # pin the old row that was current by fallback
    return row
