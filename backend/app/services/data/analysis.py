"""Readiness report and free baseline for a project's chosen dataset."""
import pandas as pd
from sqlalchemy.orm import Session

from ...db.tables import BaselineRun, DatasetVersion, InsightReport, Project
from ...ports import Storage
from .. import lifecycle
from .baseline import run_baseline
from .insights import analyze, trust_level


def readiness(session: Session, storage: Storage, project: Project) -> InsightReport:
    version = session.get(DatasetVersion, project.chosen_dataset_version_id)
    res = analyze(pd.read_csv(storage.path(version.storage_key)), version.target_column)
    report = InsightReport(dataset_version_id=version.id, measurements=res["measurements"], findings=res["findings"], grade=res["grade"])
    session.add(report)
    project.readiness_grade = res["grade"]
    session.commit()
    if project.status == "data_chosen":
        lifecycle.transition(session, project, "readiness_done")
    return report


def baseline(session: Session, storage: Storage, project: Project) -> BaselineRun:
    version = session.get(DatasetVersion, project.chosen_dataset_version_id)
    out = run_baseline(storage.path(version.storage_key), version.target_column)
    run = BaselineRun(project_id=project.id, dataset_version_id=version.id, accuracy=out.accuracy,
                      simple_guess_accuracy=out.simple_guess_accuracy, samples=[list(s) for s in out.samples])
    session.add(run)
    project.baseline_result = {"accuracy": out.accuracy, "simple_guess_accuracy": out.simple_guess_accuracy}
    project.trust_level = trust_level(project.readiness_grade or "F", out.accuracy, out.simple_guess_accuracy)
    session.commit()
    if project.status == "readiness_done":
        lifecycle.transition(session, project, "baseline_done")
    return run
