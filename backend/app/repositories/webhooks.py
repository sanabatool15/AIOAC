from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.tables import WebhookEvent


class WebhookRepository:
    def __init__(self, session: Session):
        self.s = session

    def record_once(self, event_id: str, event_type: str, payload: dict) -> bool:
        """True if new, False if this event was already processed."""
        try:
            self.s.add(WebhookEvent(event_id=event_id, event_type=event_type, payload=payload))
            self.s.commit()
            return True
        except IntegrityError:
            self.s.rollback()
            return False
