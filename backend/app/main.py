from fastapi import FastAPI

from . import models  # noqa: F401
from .db import Base, engine
from .routes import health, payments, projects, webhooks

Base.metadata.create_all(engine)

app = FastAPI(title="AIOAC")
for r in (health.router, projects.router, payments.router, webhooks.router):
    app.include_router(r)
