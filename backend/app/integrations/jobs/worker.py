"""The job body with real dependencies. Used by every runner. Opens its own database session."""
from ...db import SessionLocal
from ..factory import get_payment_provider, get_storage, get_training_backend
from ...services import training


def run_job(run_id: str) -> None:
    with SessionLocal() as session:
        training.execute_run(session, run_id, get_training_backend(), get_storage(), get_payment_provider())
