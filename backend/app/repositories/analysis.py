"""Readiness reports and free-baseline runs."""
from sqlalchemy import select

from ..db import Session
from ..db.tables import BaselineRun, InsightReport, Project


def add_insight_report(session: Session, project: Project, **fields) -> InsightReport:
    report = InsightReport(**fields)
    session.add(report)
    project.readiness_grade = fields["grade"]
    session.commit()
    return report


def add_baseline_run(session: Session, project: Project, baseline_result: dict, trust_level: str, **fields) -> BaselineRun:
    run = BaselineRun(project_id=project.id, **fields)
    session.add(run)
    project.baseline_result = baseline_result
    project.trust_level = trust_level
    session.commit()
    return run


def latest_baseline_run(session: Session, project_id: str) -> BaselineRun | None:
    return session.scalar(select(BaselineRun).where(BaselineRun.project_id == project_id).order_by(BaselineRun.created_at.desc()))
