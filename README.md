# AIOAC (AI on a Click)

Describe a prediction problem in plain words. An AI agent checks the data, runs a free baseline test, quotes an estimated cost, takes payment through PayPal (sandbox), trains the model, and refunds any unused amount.

Status: backend and agent core built and tested; AWS training, PayPal sandbox and the web app are not. See `specs/status.md`. The web app is not built yet.

## Run the backend

```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp ../.env.example .env      # fake placeholders; defaults use the mock payment provider
uvicorn app.main:app --reload
pytest                       # no network needed
```

By default payments use a mock provider and training runs locally, so nothing here spends money. PayPal sandbox and AWS SageMaker are not wired up yet.

## Background training

`POST /projects/{id}/train` starts training and returns a run id at once. Poll `GET /projects/{id}/training` for the stage, elapsed time, spend so far and an estimated time left. `POST /projects/{id}/training/stop` stops it; unused money is refunded. When the API starts, any run left `running` by a crash is marked failed and refunded in full.

`JOB_RUNNER=inline` (default) runs the job in a thread of the API process. Nothing else is needed.

`JOB_RUNNER=inngest` uses Inngest Cloud (`pip install -e '.[inngest]'`). Set `INNGEST_EVENT_KEY` and `INNGEST_SIGNING_KEY` from your Inngest Cloud environment, leave `INNGEST_DEV=false`, and sync the app in the Inngest dashboard using a PUBLIC url ending in `/api/inngest`. Inngest Cloud calls that url, so a local API needs a tunnel. This path has not been run against real Inngest Cloud yet.

## Use Supabase Postgres (optional)

SQLite is the default. To use Supabase: `pip install -e '.[postgres]'`, then in Supabase open Project Settings > Database > Connection string and copy the pooled string (Supavisor, port 6543). Put it in `.env` as `DATABASE_URL`. The app rewrites `postgresql://` to the psycopg 3 driver, turns off prepared statements and client-side pooling for port 6543 (transaction mode needs that), and creates the tables on start. Never commit the real string. The Supabase path has not been run against a real project yet. Existing local databases need deleting after schema changes (there are no migrations yet).

License: MIT
