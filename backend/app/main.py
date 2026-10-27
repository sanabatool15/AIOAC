import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .db import Base, SessionLocal, engine, tables  # noqa: F401  (importing tables registers them)
from .integrations.factory import get_job_runner, get_payment_provider
from .routes import health, payments, projects, webhooks
from .services import training

Base.metadata.create_all(engine)
log = logging.getLogger("uvicorn")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Crash recovery: runs left `running` with no live worker are failed and refunded in full."""
    try:
        runner = get_job_runner()
        with SessionLocal() as session:
            done = training.recover_stale_runs(session, get_payment_provider(), runner.is_active, runner.stale_after_seconds)
        if done:
            log.warning("recovered %d interrupted training run(s): %s", len(done), done)
    except Exception:  # never block API start because recovery failed
        log.exception("training run recovery failed")
    yield


app = FastAPI(title="AIOAC", lifespan=lifespan)
for r in (health.router, projects.router, payments.router, webhooks.router):
    app.include_router(r)

if settings.job_runner == "inngest":
    get_job_runner().serve(app)  # adds /api/inngest, the endpoint Inngest Cloud calls
