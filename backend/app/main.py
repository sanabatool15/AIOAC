from fastapi import FastAPI

from .db import Base, engine
from . import models  # noqa: F401
from .routes import health, jobs, payments, webhooks

Base.metadata.create_all(engine)

app = FastAPI(title="AIOAC")
for r in (health.router, jobs.router, payments.router, webhooks.router):
    app.include_router(r)
