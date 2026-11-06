# AIOAC (AI on a Click)

Describe a prediction problem in plain words. An AI agent checks the data, runs a free baseline test, runs a free pilot and forecasts the result, quotes an estimated cost, places a PayPal (sandbox) hold, trains the model, checks it once on locked test data, then charges the actual compute (plus a small success fee only if the check passes) and voids the rest of the hold. If our own code or infrastructure fails, the hold is voided and you pay nothing.

Status (2026-11-06): the backend, the agent and the web app are built and tested offline, and the web app has browser tests against a test server. Checked live earlier: PayPal sandbox hold, capture and void; SageMaker training jobs; the Azure model on the eval set. **Not yet done:** one full click-through with the real PayPal sandbox and a real SageMaker run (the owner does this by hand), the PayPal webhook, and Inngest. See `specs/status.md` and `specs/breakpoints.md`.

## How PayPal is used

Money model "forecast, then verify" (sandbox only; no real money, cards or passwords anywhere). The app uses PayPal's REST API (Orders v2 and Payments v2):

1. You approve a price estimate. The server creates an **authorization** order for the cap (the most you can be charged). You approve it as a PayPal sandbox buyer. Nothing is charged yet.
2. **The server confirms the hold with PayPal itself**; a success screen in the browser is never proof. Paid training starts only after that.
3. After training, the model is checked once on test data it never saw. Then the server **captures** the compute actually used (always), captures the 5% success fee **only if the check passed**, and **voids** the rest of the hold. If our own code or infrastructure fails, the whole hold is voided and you pay $0.
4. Every capture and void carries an idempotency key, the ledger is append-only, and a repeated webhook can never charge twice. Payment code: `backend/app/integrations/paypal/`, `backend/app/services/payments.py`. Spec: `specs/payments.md`.

## How AI is used

- **An agent** (a tool-calling loop on a hosted model: Azure AI Foundry or OpenRouter) talks to you in plain words, finds open datasets (UCI, OpenML, Hugging Face, a hand-checked list), looks at them and proposes one. It cannot spend money or start paid work: ordinary code (the permission gate) checks every paid step against stored state, and you approve each choice on a card.
- **Numbers come from code, never from the model.** The readiness grade, the free test, the free pilot and forecast, the price estimate and the final check on locked test data are all computed by our own code (scikit-learn). The model only chooses what to try and words the result.
- **We never promise accuracy.** You see a readiness grade, a measured free test on held-out data, a forecast labelled as an estimate, and an estimated price. Spec: `specs/agent.md`.

## Features in one paragraph each

- **Improve.** If the verified result misses your target you paid compute only (no success fee) and the project offers a free "Improve" round: a new free pilot, starting at the suggested target. A new price needs a new PayPal hold.
- **Sharing.** On a finished project, Share creates a public read-only link (`/s/<token>`, no login). It shows the goal, data name, free test and verified result against the target; never money, email or payment details. Stop sharing turns the link off at once. The link is the only secret, so share it only with people you trust.
- **Using the model.** The Model tab of a finished project lets you try the model on one record, run it on a CSV (up to 5,000 rows, download the answers) or download the model file. Answers are estimates, not promises. A model trained under another scikit-learn version may not run in the app; it can still be downloaded.

## Run it on Windows (PowerShell)

Needs Python 3.11 or newer, Node.js 20 or newer, and Git. Do the backend first, in one PowerShell window; use a second window for the frontend.

```powershell
cd AIOAC          # the folder you cloned
cd backend
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass     # only for this window, so the next line may run
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,postgres]"
Copy-Item ..\.env.example .env                                 # backend/.env is git-ignored; put your own values here
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste the output into SECRET_KEY in backend\.env
uvicorn app.main:app --reload --port 8000
```

With `uv` instead: `uv venv`, `.\.venv\Scripts\Activate.ps1`, `uv pip install -e ".[dev,postgres]"`.

```powershell
cd frontend
Copy-Item .env.example .env.local        # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm install
npm run dev                              # http://localhost:3000
```

Open http://localhost:3000, sign up, and describe a goal (for example "which customers may stop buying", then "I have no data").

### Keys in `backend\.env` (names only; never commit values)

| Name | What for |
|---|---|
| `SECRET_KEY` | signs login cookies; at least 32 random characters. Without it login answers 503 |
| `DATABASE_URL` | empty = local SQLite. For Supabase see below |
| `LLM_PROVIDER` | `azure` or `openrouter` |
| `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_MODEL` | when `LLM_PROVIDER=azure` |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | when `LLM_PROVIDER=openrouter` |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID` | PayPal SANDBOX app keys. `PAYPAL_RETURN_URL` and `PAYPAL_CANCEL_URL` must point at the frontend (`http://localhost:3000/pay/return` and `/pay/cancel`) |
| `CORS_ORIGINS` | browser origin of the frontend (`http://localhost:3000`) |
| `TRAINING_BACKEND` | `local` (free, default) or `sagemaker` (paid, capped) |
| `SAGEMAKER_REGION`, `SAGEMAKER_BUCKET`, `SAGEMAKER_ROLE_ARN`, `SAGEMAKER_INSTANCE_TYPE`, `SAGEMAKER_SKLEARN_VERSION` | when `TRAINING_BACKEND=sagemaker`. AWS credentials come from the normal AWS chain (`aws configure` or `AWS_*` variables), not from this file |
| `JOB_RUNNER` | `inline` (default) or `inngest` |

Frontend `frontend\.env.local`: `NEXT_PUBLIC_API_BASE_URL` (backend address, default `http://localhost:8000`), optional `NEXT_PUBLIC_DEMO_LOGIN`.

### PayPal sandbox test (the real cycle)

1. In the PayPal developer dashboard (Sandbox) create an app and copy its client id and secret into `backend\.env`. You also need a sandbox **buyer** account (Sandbox > Accounts). Use sandbox accounts only; never your real PayPal login, real cards or real money.
2. Run both servers, sign up, go through goal, dataset, data check, free test, target and price, then click "Approve and pay". PayPal opens: sign in with the **sandbox buyer** and approve. You return to the app, the server confirms the hold, and training starts.
3. At the end the receipt shows held, compute charged, success fee (only if verified) and released. With `TRAINING_BACKEND=local` the compute is $0, so the whole hold is released; with `sagemaker` about 52 cents is captured. Check the same amounts in the sandbox dashboard.

### Supabase Postgres (optional)

SQLite is the default and needs nothing. For Supabase set `DATABASE_URL` to the pooled connection string (Project Settings > Database > Connection string, port 6543) in `backend\.env`, then from `backend\` (venv active):

```powershell
python -m app.db.init              # first time: creates the tables (never drops anything)
python -m app.db.init --check      # read-only: lists missing tables, columns, indexes (exit code 1 if any)
python -m app.db.init --upgrade    # dry run of the SQL that adds what is missing
python -m app.db.init --upgrade --yes
```

The new `shares` table (public result links) is created by `init`/`--upgrade`. The API runs as the table owner, so enable row level security on every table (no policies: nobody can read tables through Supabase's public API). Run this once in the Supabase SQL editor, and again after new tables appear:

```sql
DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
  END LOOP;
END $$;
```

## Background training

`POST /projects/{id}/train` starts training and returns a run id at once; the screen polls `GET /projects/{id}/training`. `POST /projects/{id}/training/stop` stops it (you pay the compute used so far, no success fee). On start-up, a run left `running` by a crash is failed and its whole hold voided.

`JOB_RUNNER=inline` (default) runs the job in a thread of the API process; nothing else is needed. `JOB_RUNNER=inngest` is optional (`pip install -e ".[inngest]"`, `INNGEST_EVENT_KEY`, `INNGEST_SIGNING_KEY`; for local use `INNGEST_DEV=1` with the Inngest Dev Server). **The Inngest path, including the Dev Server, has not been verified**; keep `inline` for the demo.

## Known limits

- Not run end to end against the real PayPal sandbox plus real SageMaker in the browser; the PayPal webhook has never run; Inngest is unverified.
- Estimates are estimates: prices in `backend/app/services/cost/prices.py` are placeholders checked against one small real job; forecasts on real datasets are not validated at scale.
- Tabular data and classification only. One CPU instance type. Datasets up to 50,000 rows / 50 MB.
- Login: no password reset, no email check; the session token stays valid until it expires even after Log out; rate limits are per process and in memory.
- Stopping a local run takes effect only between stages. Prediction runs in the API process and needs the same scikit-learn minor version as the training job.
- The activity feed shows settlement lines with the end time of the last run (the payment row has no per-step time).

## Test

```
cd backend
pytest                                        # unit, contract and e2e tests; offline, no keys; integration tests skip
pytest tests/e2e/test_payments_and_demo.py    # demo check: full flow on the mock payment double
RUN_REAL=1 pytest tests/integration -v -s            # integration checks (live services), uses your .env
python -m evals.run --fake --repeats 1        # agent evals offline (use --model <id> for a real model)
```

Browser tests (from `frontend\`, needs a Chrome or `npx playwright install chromium`): `npm run test:e2e` builds the frontend, starts the TEST backend (`backend/tests/browser_server.py`: scripted model, mock PayPal, local training, throwaway SQLite; it never reads real keys) and the frontend, then runs 6 specs. `npm test` runs the unit tests.

Offline tests ignore your `.env` and use a temporary database. The real checks are small: PayPal sandbox token and a 50 cent hold order (not approved, nothing charged), read-only AWS calls (identity, bucket, SageMaker list), one tiny LLM answer, a database connection test, and a live Hugging Face search. Each skips if its keys are missing. Layout: `specs/architecture.md`.

### PayPal sandbox: hold, capture, void

The full money check needs a sandbox buyer to approve in a browser, so it has two steps (sandbox money only, 25 cents captured): `RUN_REAL=1 pytest tests/integration/test_paypal_sandbox.py -k create -v -s` prints an approval link and an order id; approve it as the sandbox BUYER account; then `PAYPAL_APPROVED_ORDER_ID=<order id> RUN_REAL=1 pytest tests/integration/test_paypal_sandbox.py -k lifecycle -v -s`. If you used an older version, delete the local `aioac.db` (the schema changed; there are no migrations).

## Login (required)

Every screen's API call needs a signed-in user; each project belongs to one user and one organization, and nobody else can see it (other users get 404). Set `SECRET_KEY` in `.env` to at least 32 random characters (`python -c "import secrets; print(secrets.token_urlsafe(48))"`), otherwise `/auth/*` and the project routes answer 503 "login is not set up" and `/health` shows `auth.configured: false`. Other settings: `JWT_TTL_MINUTES` (720), `COOKIE_SECURE` (true behind https), `COOKIE_SAMESITE` (lax; `none` needs secure), `DEMO_LOGIN_ENABLED` (false; true adds `POST /auth/demo` for the video). Delete any old `aioac.db` after pulling this change: the schema gained `organizations`, user passwords and project owners, and projects created before login have no owner and cannot be reached.

License: MIT
