# AIOAC (AI on a Click)

Describe a prediction problem in plain words. An AI agent checks the data, runs a free baseline test, quotes an estimated cost, takes payment through PayPal (sandbox), trains the model, and refunds any unused amount.

Status: backend and agent core built and tested offline; PayPal sandbox is partly checked live; AWS training and the web app are not run or built. See `specs/status.md`. The web app is not built yet.

## Run the backend

```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp ../.env.example .env      # fake placeholders; put your own sandbox keys here (never commit .env)
uvicorn app.main:app --reload
```

Training runs locally by default (`TRAINING_BACKEND=local`), which costs nothing. Payments always use the PayPal provider (`PAYMENT_PROVIDER=paypal`); there is no mock mode in the app, so real payment calls need PayPal SANDBOX keys in `.env` (`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`). Use sandbox accounts only, never real money or cards. AWS SageMaker is used only with `TRAINING_BACKEND=sagemaker` and the `SAGEMAKER_*` variables. LLM: `LLM_PROVIDER=openrouter` (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`) or `azure`.

## Test

```
cd backend
pytest                                        # unit, contract and e2e tests; offline, no keys; real tests skip
pytest tests/e2e/test_payments_and_demo.py    # demo check: full flow on the mock payment double
RUN_REAL=1 pytest tests/real -v -s            # real checks, uses your .env
python -m evals.run --fake --repeats 1        # agent evals offline (use --model <id> for a real model)
```

Offline tests ignore your `.env` and use a temporary database. The real checks are small: PayPal sandbox token and a 1.00 USD order (not captured), read-only AWS calls (identity, bucket, SageMaker list), one tiny LLM answer, a database connection test, and a live Hugging Face search. Each skips if its keys are missing. Layout: `specs/architecture.md`.

## Background training

`POST /projects/{id}/train` starts training and returns a run id at once. Poll `GET /projects/{id}/training` for the stage, elapsed time, spend so far and an estimated time left. `POST /projects/{id}/training/stop` stops it; unused money is refunded. When the API starts, any run left `running` by a crash is marked failed and refunded in full.

`JOB_RUNNER=inline` (default) runs the job in a thread of the API process. Nothing else is needed.

`JOB_RUNNER=inngest` uses Inngest Cloud (`pip install -e '.[inngest]'`). Set `INNGEST_EVENT_KEY` and `INNGEST_SIGNING_KEY` from your Inngest Cloud environment, leave `INNGEST_DEV=false`, and sync the app in the Inngest dashboard using a PUBLIC url ending in `/api/inngest`. Inngest Cloud calls that url, so a local API needs a tunnel. This path has not been run against real Inngest Cloud yet.

## Use Supabase Postgres (optional)

SQLite is the default. To use Supabase: `pip install -e '.[postgres]'`, then in Supabase open Project Settings > Database > Connection string and copy the pooled string (Supavisor, port 6543). Put it in `.env` as `DATABASE_URL`. The app rewrites `postgresql://` to the psycopg 3 driver, turns off prepared statements and client-side pooling for port 6543 (transaction mode needs that), and creates the tables on start. Never commit the real string. The Supabase path has not been run against a real project yet. Existing local databases need deleting after schema changes (there are no migrations yet).

License: MIT
