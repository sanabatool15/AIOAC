"""Inngest Cloud job runner.

Checked against the Inngest Python SDK 0.5.19 (client constructor, create_function, step.run, send_sync,
fast_api.serve) and the docs at inngest.com/docs/reference/python.

How it works: enqueue() sends the event `aioac/training.requested` to Inngest Cloud. Inngest Cloud then calls
our function over HTTP at /api/inngest, so Inngest Cloud must be able to reach a PUBLIC URL of this API (for
example a tunnel). The function runs the same job body as the inline runner.

Cost safety: retries=0. A retry could start a second paid run for the same payment. A run that fails is failed
and refunded in full instead (training.fail_run), and a lost run is caught by crash recovery.
"""
import logging

import inngest
import inngest.fast_api
from fastapi import FastAPI

from ..config import settings
from .worker import run_job

EVENT_NAME = "aioac/training.requested"
FUNCTION_ID = "run-training"


def make_client() -> inngest.Inngest:
    # INNGEST_DEV=true means the local dev server. Inngest Cloud needs is_production=True plus both keys.
    return inngest.Inngest(
        app_id="aioac",
        event_key=settings.inngest_event_key or None,
        signing_key=settings.inngest_signing_key or None,
        is_production=not settings.inngest_dev,
        logger=logging.getLogger("uvicorn"),
    )


def make_function(client: inngest.Inngest, execute=run_job):
    # idempotency: Inngest runs this function at most once per run_id (24 hours); concurrency: one paid job at a time
    # (cost.md). Both are backed by the database claim in training.execute_run, which is what the tests prove.
    @client.create_function(fn_id=FUNCTION_ID, trigger=inngest.TriggerEvent(event=EVENT_NAME), retries=0,
                            idempotency="event.data.run_id", concurrency=[inngest.Concurrency(limit=1)])
    def run_training_fn(ctx: inngest.ContextSync) -> str:
        run_id = ctx.event.data["run_id"]
        ctx.step.run("train", execute, run_id)
        return run_id

    return run_training_fn


class InngestJobRunner:
    stale_after_seconds = settings.run_stale_seconds

    def __init__(self, client: inngest.Inngest | None = None):
        self.client = client or make_client()

    def enqueue(self, run_id: str) -> None:
        # The event id makes Inngest drop a duplicate send for the same run.
        self.client.send_sync(inngest.Event(name=EVENT_NAME, id=f"train-{run_id}", data={"run_id": run_id}))

    def is_active(self, run_id: str) -> bool:
        return False  # we cannot see Inngest's workers from here; the run heartbeat decides

    def serve(self, app: FastAPI, execute=run_job) -> None:
        inngest.fast_api.serve(app, self.client, [make_function(self.client, execute)])
