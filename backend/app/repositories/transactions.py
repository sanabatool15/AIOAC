from ..db import Session


def rollback(session: Session) -> None:
    session.rollback()


def commit(session: Session) -> None:
    session.commit()
