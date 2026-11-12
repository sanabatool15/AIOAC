"""Readiness report and free baseline for a project's chosen dataset."""
import pandas as pd
from ...db import Session
from ...db.tables import BaselineRun, InsightReport, Project
from ...repositories import analysis as repo
from ...repositories import datasets as datasets_repo
from ...repositories import projects as projects_repo
from ...ports import Storage
from .. import lifecycle
from .baseline import run_baseline
from .insights import analyze, analyze_no_answer, trust_level
from . import tasks
from .task_wording import unit_for


def readiness(session: Session, storage: Storage, project: Project) -> InsightReport:
    version = datasets_repo.get_version(session, project.chosen_dataset_version_id)
    df = pd.read_csv(storage.path(version.storage_key))
    kind = tasks.task_of(project)
    config = _series_config(session, project, df, version.target_column) if kind.id == "forecast" else None
    res = analyze_no_answer(df, kind.id) if not kind.needs_target else analyze(df, version.target_column, kind.id, config)
    report = repo.add_insight_report(session, project, dataset_version_id=version.id, measurements=res["measurements"],
                                     findings=res["findings"], grade=res["grade"])
    if project.status == "data_chosen":
        lifecycle.transition(session, project, "readiness_done")
    return report


def baseline(session: Session, storage: Storage, project: Project) -> BaselineRun:
    return baseline_detailed(session, storage, project)[0]


def baseline_detailed(session: Session, storage: Storage, project: Project):
    """Same as baseline(), also returns the outcome (row counts, rare-group catch rate). The extras are NOT stored:
    project.baseline_result is served as-is by the API and keeps its two keys."""
    version = datasets_repo.get_version(session, project.chosen_dataset_version_id)
    kind = tasks.task_of(project)
    if kind.id == "regression":
        return _number_baseline(session, storage, project, version, kind)
    if kind.id == "forecast":
        return _series_baseline(session, storage, project, version, kind)
    if not kind.needs_target:
        return _no_answer_baseline(session, storage, project, version, kind)
    out = run_baseline(storage.path(version.storage_key), version.target_column)
    run = repo.add_baseline_run(session, project,
                                {"accuracy": out.accuracy, "simple_guess_accuracy": out.simple_guess_accuracy},
                                trust_level(project.readiness_grade or "F", out.accuracy, out.simple_guess_accuracy),
                                dataset_version_id=version.id, accuracy=out.accuracy,
                                simple_guess_accuracy=out.simple_guess_accuracy, samples=[list(s) for s in out.samples])
    if project.status == "readiness_done":
        lifecycle.transition(session, project, "baseline_done")
    return run, out


def _number_baseline(session: Session, storage: Storage, project: Project, version, kind):
    """The free test when the answer is a number. `accuracy` and `simple_guess_accuracy` hold the score and the guess's
    score (0) as aliases, so old clients and the share page keep working (specs/ml-tasks/01 section 3)."""
    out = kind.free_test(storage.path(version.storage_key), version.target_column, unit_for(version.target_column))
    result = {"accuracy": out.score, "simple_guess_accuracy": 0.0, "task_type": "regression", "metric": "error_reduction",
              "score": out.score, "simple_guess_score": 0.0, "extras": out.extras}
    run = repo.add_baseline_run(session, project, result, trust_level(project.readiness_grade or "F", out.score, 0.0),
                                dataset_version_id=version.id, accuracy=out.score, simple_guess_accuracy=0.0,
                                samples=[list(s) for s in out.samples])
    if project.status == "readiness_done":
        lifecycle.transition(session, project, "baseline_done")
    return run, out


def _series_config(session: Session, project: Project, df: pd.DataFrame, target: str) -> dict | None:
    """The settings of a number over time (date column, how often, how far ahead, season), read from the data once and
    kept on the project. What the user or agent chose earlier wins. A file with no usable dates saves nothing (the
    readiness findings then say so in plain words)."""
    try:
        cfg = tasks.forecast.resolve_config(df, target, project.task_config)
    except tasks.forecast.ForecastDataError:
        return project.task_config
    if cfg != project.task_config:
        projects_repo.set_task_config(session, project, cfg)
    return cfg


def _series_baseline(session: Session, storage: Storage, project: Project, version, kind):
    """The free test for a number over time. Stored like the one for a plain number (the two `accuracy` keys are aliases
    of the score and the simple repeat's score, 0), with the time-specific facts in `extras`."""
    out = kind.free_test(storage.path(version.storage_key), version.target_column, project.task_config or {}, unit_for(version.target_column))
    result = {"accuracy": out.score, "simple_guess_accuracy": 0.0, "task_type": "forecast", "metric": "error_reduction",
              "score": out.score, "simple_guess_score": 0.0, "extras": out.extras}
    run = repo.add_baseline_run(session, project, result, trust_level(project.readiness_grade or "F", out.score, 0.0),
                                dataset_version_id=version.id, accuracy=out.score, simple_guess_accuracy=0.0,
                                samples=[list(s) for s in out.samples])
    if project.status == "readiness_done":
        lifecycle.transition(session, project, "baseline_done")
    return run, out


def _no_answer_baseline(session: Session, storage: Storage, project: Project, version, kind):
    """The free test for grouping and unusual records: how steady the result is on rows it was not fitted on. The two
    `accuracy` keys hold the score and the simple guess's score (0), like the other types. The chosen number of groups
    (or the flagged share) is kept on the project so the paid run uses the same one."""
    out = kind.free_test(storage.path(version.storage_key), None, project.task_config or {})
    ex = out.extras
    cfg = {**(project.task_config or {}), **({"n_clusters": ex["groups"]} if kind.id == "grouping" else {"contamination": ex["flag_share"]})}
    if cfg != (project.task_config or {}):
        projects_repo.set_task_config(session, project, cfg)
    result = {"accuracy": out.score, "simple_guess_accuracy": 0.0, "task_type": kind.id, "metric": "steadiness",
              "score": out.score, "simple_guess_score": 0.0, "extras": ex}
    run = repo.add_baseline_run(session, project, result, trust_level(project.readiness_grade or "F", out.score, 0.0),
                                dataset_version_id=version.id, accuracy=out.score, simple_guess_accuracy=0.0,
                                samples=[list(s) for s in out.samples])
    if project.status == "readiness_done":
        lifecycle.transition(session, project, "baseline_done")
    return run, out
