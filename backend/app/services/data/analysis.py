"""Readiness report and free baseline for a project's chosen dataset."""
import pandas as pd
from ...db import Session
from ...db.tables import BaselineRun, InsightReport, Project
from ...repositories import analysis as repo
from ...repositories import datasets as datasets_repo
from ...ports import Storage
from .. import lifecycle
from .baseline import run_baseline
from .insights import analyze, trust_level


def readiness(session: Session, storage: Storage, project: Project) -> InsightReport:
    version = datasets_repo.get_version(session, project.chosen_dataset_version_id)
    res = analyze(pd.read_csv(storage.path(version.storage_key)), version.target_column)
    report = repo.add_insight_report(session, project, dataset_version_id=version.id, measurements=res["measurements"],
                                     findings=res["findings"], grade=res["grade"])
    if project.status == "data_chosen":
        lifecycle.transition(session, project, "readiness_done")
    return report


def baseline(session: Session, storage: Storage, project: Project) -> BaselineRun:
    version = datasets_repo.get_version(session, project.chosen_dataset_version_id)
    out = run_baseline(storage.path(version.storage_key), version.target_column)
    run = repo.add_baseline_run(session, project,
                                {"accuracy": out.accuracy, "simple_guess_accuracy": out.simple_guess_accuracy},
                                trust_level(project.readiness_grade or "F", out.accuracy, out.simple_guess_accuracy),
                                dataset_version_id=version.id, accuracy=out.accuracy,
                                simple_guess_accuracy=out.simple_guess_accuracy, samples=[list(s) for s in out.samples])
    if project.status == "readiness_done":
        lifecycle.transition(session, project, "baseline_done")
    return run
