"""Glue for the `compare_models` tool: loads the WORK rows and the stored forecast, runs data/compare.py. Reads only:
no database writes, no status change. The locked test rows are never opened (only the work file is read)."""
import pandas as pd

from ..db import Session
from ..db.tables import Project
from ..ports import Storage
from ..repositories import datasets as datasets_repo
from ..repositories import forecasts as forecasts_repo
from .data import compare, verification


def for_project(session: Session, storage: Storage, project: Project, budget_s: float = compare.BUDGET_S) -> dict:
    version = datasets_repo.get_version(session, project.chosen_dataset_version_id) if project.chosen_dataset_version_id else None
    if version is None:
        return {"error": "no dataset has been chosen yet"}
    work_key, _locked_key = verification.split_for(session, storage, version)   # the locked file is not opened here
    work = pd.read_csv(storage.path(work_key))
    fc = forecasts_repo.latest_for_project(session, project.id)
    curve = ((fc.pilot or {}).get("learning_curve")) if fc is not None else None
    return compare.compare(work, version.target_column, curve, budget_s)
