from sqlalchemy import select

from ..db import Session
from ..db.tables import Forecast


def get(session: Session, forecast_id: str) -> Forecast | None:
    return session.get(Forecast, forecast_id)


def latest_for_project(session: Session, project_id: str) -> Forecast | None:
    return session.scalar(select(Forecast).where(Forecast.project_id == project_id).order_by(Forecast.created_at.desc()))


def add(session: Session, **fields) -> Forecast:
    fc = Forecast(**fields)
    session.add(fc)
    session.commit()
    return fc
