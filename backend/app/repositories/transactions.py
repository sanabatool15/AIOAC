from ..db import Session


def rollback(session: Session) -> None:
    session.rollback()
