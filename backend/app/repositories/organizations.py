"""Organizations (tenants)."""
from ..db import Session
from ..db.tables import Organization


def create(session: Session, name: str) -> Organization:
    """Adds the row without committing, so signup can create the org and the user in one transaction."""
    org = Organization(name=name)
    session.add(org)
    session.flush()
    return org
