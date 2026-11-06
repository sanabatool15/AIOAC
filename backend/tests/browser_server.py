"""TEST-ONLY launcher: the real FastAPI app (app.main) wired to doubles, so a browser (Playwright) can click through
the whole flow with no keys and no network.

    cd backend && python -m tests.browser_server --port 8765 --frontend http://localhost:3000

What is real: the app, the routes, login (signed cookie), the database layer (a throwaway SQLite file), local storage
(a temp folder), the gate, the ledger, local training, the cost and forecast code.
What is a double: the model (doubles.llm.ReactiveFake: finds a dataset, fetches it, then proposes select_dataset and
waits for the approval card), the dataset source (doubles.datasets.OfflineSource), and PayPal (MockPaymentProvider).
The mock hold's approve_url is `<frontend>/pay/return?token=<order id>`, the same shape PayPal's return link has,
so the frontend return page can call POST /payments/{id}/authorize and the mock confirms the hold.

This is NOT the app. `app/` never imports this file (tests/unit/test_architecture.py). It never reads real keys and
refuses to start if DATABASE_URL points at Postgres.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass, field

# Variables that could carry real credentials; the launcher clears them before anything is imported.
SECRET_ENV = ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_MODEL", "OPENROUTER_API_KEY", "HF_TOKEN",
              "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET",
              "PAYPAL_WEBHOOK_ID", "INNGEST_EVENT_KEY", "INNGEST_SIGNING_KEY", "SAGEMAKER_BUCKET", "SAGEMAKER_ROLE_ARN")

# What the scripted model does: look for data, fetch it, then propose select_dataset (the user approves the card).
FAKE_CASE = {"fake": {"behavior": "discover", "goal_summary": "predict which subscription customers will leave",
                      "queries": ["customer churn", "subscription cancel"], "target": "left",
                      "final_text": "I chose that dataset. Next I will check it is ready to use."}}
AGENT_STAGES = ["discover_datasets", "look_at_dataset", "fetch_dataset", "select_dataset"]


class RefuseToStart(Exception):
    pass


def prepare_environment(frontend: str, workdir: str, env=os.environ) -> None:
    """Point the app's settings at throwaway resources. Must run BEFORE `app` is imported."""
    if (env.get("DATABASE_URL") or "").lower().startswith(("postgres", "postgresql")):
        raise RefuseToStart("DATABASE_URL points at Postgres. This launcher only uses a throwaway SQLite file.")
    for name in SECRET_ENV:
        env[name] = ""
    env.update({
        "DATABASE_URL": f"sqlite:///{workdir}/browser.db", "STORAGE_DIR": f"{workdir}/storage",
        "SECRET_KEY": "browser-test-only-secret-" + os.urandom(16).hex(), "CORS_ORIGINS": frontend,
        "PAYMENT_PROVIDER": "mock", "TRAINING_BACKEND": "local", "JOB_RUNNER": "inline", "LLM_PROVIDER": "openrouter",
        "DEMO_LOGIN_ENABLED": "false", "COOKIE_SECURE": "false",
    })


@dataclass
class Handle:
    app: object
    provider: object
    restore: list = field(default_factory=list)

    def close(self) -> None:
        for undo in reversed(self.restore):
            undo()
        self.restore.clear()


def install(frontend: str = "http://localhost:3000", threaded: bool = True) -> Handle:
    """Swap the app's outside systems for doubles. Returns a handle; `close()` puts everything back."""
    import sys as _sys
    from fastapi.middleware.cors import CORSMiddleware  # noqa: F401  (the app already adds CORS from CORS_ORIGINS)

    from app import deps
    from app.config import settings
    from app.integrations import factory
    from app.integrations.jobs.inline import InlineJobRunner
    from app.integrations.jobs.worker import run_job
    from app.integrations.storage.local import LocalStorage
    from app.integrations.training_local.backend import LocalBackend
    from app.main import app
    from app.ports import Order
    from doubles.datasets import OfflineSource
    from doubles.llm import ReactiveFake
    from doubles.payments import MockPaymentProvider
    from app.integrations.factory import build_registry

    class BrowserPayments(MockPaymentProvider):
        def create_hold(self, amount_cents, project_id):
            order = super().create_hold(amount_cents, project_id)
            return Order(order.order_id, f"{frontend.rstrip('/')}/pay/return?token={order.order_id}")

    provider = BrowserPayments()
    storage = LocalStorage(settings.storage_dir)
    backend = LocalBackend()
    runner = InlineJobRunner(run_job, threaded=threaded)
    registry = build_registry(hf=OfflineSource(), uci=OfflineSource(), oml=OfflineSource())
    handle = Handle(app, provider)

    replacements = {"get_payment_provider": lambda: provider, "get_storage": lambda: storage,
                    "get_training_backend": lambda: backend, "get_job_runner": lambda: runner,
                    "get_dataset_source": lambda: registry, "llm_configured": lambda: True}
    for modname, mod in list(_sys.modules.items()):
        if modname != "app" and not modname.startswith("app."):
            continue
        for name, fn in replacements.items():
            if hasattr(mod, name):
                old = getattr(mod, name)
                setattr(mod, name, fn)
                handle.restore.append(lambda m=mod, n=name, o=old: setattr(m, n, o))

    models: dict[str, ReactiveFake] = {}

    def scripted_model(pid: str):
        """One scripted model per project, so two browser sessions do not share a script position."""
        if pid not in models:
            fake = ReactiveFake(FAKE_CASE)
            fake.stages = list(AGENT_STAGES)
            models[pid] = fake
        return models[pid]

    app.dependency_overrides[deps.get_llm_client] = scripted_model
    handle.restore.append(lambda: app.dependency_overrides.pop(deps.get_llm_client, None))
    return handle


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--frontend", default=os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000"),
                    help="browser origin allowed by CORS and used for the PayPal return link")
    args = ap.parse_args(argv)
    workdir = tempfile.mkdtemp(prefix="aioac-browser-")
    try:
        prepare_environment(args.frontend, workdir)
    except RefuseToStart as exc:
        print(f"Refusing to start: {exc}", file=sys.stderr)
        return 2
    handle = install(args.frontend, threaded=True)
    import uvicorn
    print(f"Browser test server on http://{args.host}:{args.port} (throwaway data in {workdir}; scripted model, mock PayPal)")
    uvicorn.run(handle.app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
