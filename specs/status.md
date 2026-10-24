# Implementation Status

What has been built, what is stubbed, what has not been started, and what we learned along the way. Updated 2026-10-23. This file describes reality; the other specs describe intent. Where they differ, this file says so.

## 1. Summary

| Area | State |
|---|---|
| Repository setup (license, ignore rules, env template, README) | Done |
| Specs (`specs/`) | Draft 1. Gaps: async training and Stop, SageMaker backend contract, web app (see section 6a) |
| Database schema | Done, matches `db.md` |
| Project lifecycle (state machine) | Done |
| Permission gate | Done |
| Cost estimator and quotes | Done, with placeholder prices |
| Payment orchestration, ledger, webhooks, refunds | Done on the mock provider |
| PayPal sandbox provider | Written against the current PayPal OpenAPI specs, tested on mocked HTTP only. Never run against the real sandbox (credentials not yet working). Needs human review |
| Agent loop, tools, skills, context engineering | Done, tested with scripted model replies only |
| OpenRouter model client | Written, never run (no API key yet) |
| Hugging Face dataset tools | Done, verified against the live service |
| Dataset storage lifecycle | Done (local folder storage) |
| Insights, readiness grade, free baseline | Done, verified on real data |
| Training backends | Local done (reports progress, honours stop). SageMaker is a stub |
| Background training, progress, Stop, crash recovery | Done on the inline runner (tested). Inngest Cloud runner written against SDK 0.5.19, never run against real Inngest Cloud |
| Database | SQLite default. Postgres/Supabase configurable, never connected to a real database |
| Terraform, AWS storage | Not started |
| Training backends | Local done. SageMaker backend, training script and cap math written and tested on mocked boto3 only; never run against AWS |
| Terraform, AWS storage | Written in `infra/terraform/` (bucket, roles, app policy, budget alert). Not validated (terraform not installed) and never applied. No S3 storage provider for the app yet; the SageMaker backend uploads its own job files |
| Web app | Not started (placeholder folder) |
| Funding stretch, login | Not started |
| Claude Code harness (rules, hooks) | Not started. PayPal plugin installed but needs a sandbox token |

Tests: 136, all passing, no network needed (verified from a fresh clone). Run `pytest` in `backend/`.

## 2. Repository layout

```
CLAUDE.md          project instructions and hard rules
specs/             system specification (this folder)
backend/app/
  models/          database tables
  repositories/    database access (ledger and webhook tables are insert-only)
  services/        business logic
    agent/         loop, tools, skills loader, context building
  providers/       swappable parts: payments, training, storage, datasets, llm
  routes/          HTTP endpoints
  skills/          markdown playbooks the agent loads on demand
backend/tests/     90 tests
frontend/          placeholder only
```

## 3. What each part does

### 3.1 Lifecycle (`services/lifecycle.py`)
States: described, data_chosen, readiness_done, baseline_done, quoted, awaiting_payment, paid, training, done; side exits failed, stopped, refunded. Steps cannot be skipped. `paid` cannot be set unless a verified payment row exists.

### 3.2 Permission gate (`services/gate.py`)
Three levels. L0 runs freely. L1 (choosing a dataset) needs the user's approval. L2 (request payment, start training) needs checks on stored state:
- payment request: an approved, unexpired quote;
- training: a server-verified payment for the current quote, project status `paid`, and room in the global budget.

Every decision, allowed or refused, is written to the trace.

### 3.3 Cost (`services/cost.py`, `prices.py`, `quotes.py`)
Implements the formula in `cost.md`: time the baseline on 5%, 10% and 20% samples, fit a curve on a log scale, project to full size, convert to money, add storage and platform fee, produce estimate, low, high, and cap (cap equals the high end). A quote above the per-job maximum ($7) is refused. Quotes expire after 60 minutes.

Prices in `prices.py` are placeholders (one instance type, 25 cents per hour, 240 seconds of startup, 1 cent storage, 50 cents platform fee).

### 3.4 Payments (`services/payments.py`, `providers/payments/`)
- The user is charged the quote's cap. Unused money is refunded after training (cap minus actual cost). This is the proposal in `payments.md` and is not yet confirmed by you.
- A capture only counts when the provider reports it confirmed and the amount matches.
- The browser route and the webhook route both end in the same idempotent step, so a repeat is harmless.
- Webhooks: signature checked first, event recorded once, then applied.
- Refund and usage are recorded in the ledger with unique keys per training run.
- If the provider fails during a refund, the job still finishes, a `refund_failed` trace step is written, and the owed amount stays visible in the ledger. `POST /projects/{id}/refund/retry` sends it again; repeats are harmless. Provider outages return a plain 502 instead of a crash.
- The PayPal approval link is stored on the payment, so a page reload resumes the same payment. (This added a column: delete any old local `aioac.db` before running.)
- The ledger refuses an entry that would take a project's balance below zero.
- `mock.py` is complete. `paypal.py` implements create order, capture, refund and webhook signature verification (Orders v2, Payments v2, verify-webhook-signature). It refuses any host but the sandbox and sends the webhook body to PayPal byte-for-byte. Tests use a mocked transport (`tests/test_paypal_provider.py`). Not yet exercised against the real sandbox.

### 3.5 Training (`services/training.py`, `providers/training/`)
After the gate allows it: run the backend, cap the cost at the quote's cap, store the model, add the cost to the global spend, settle and refund. If the backend fails, the project goes to failed and then refunded, with the full amount returned. By default the backend is `local`, which costs nothing, so the default demo refunds the entire cap. The `sagemaker` backend is implemented against mocked clients (see `training.md` section 2b) and has never talked to AWS.

Training runs in the background (see `training.md` section 7): `/train` returns a run id, `GET /projects/{id}/training` shows progress, `POST /projects/{id}/training/stop` stops it. Exception: the agent's `start_training` tool still blocks on `training.run_training`.

### 3.6 Datasets (`services/datasets.py`, `providers/storage/`, `providers/datasets/`)
- Candidates are stored temporarily with an expiry time. Selecting one copies it to permanent storage and deletes the others. Expired candidates are purged by a function that nothing calls on a schedule yet. An orphan report lists stored files the database does not know about.
- Storage is a local folder behind an interface. There is no S3 implementation yet.
- Hugging Face is the only live source. Search runs a tabular-classification filter first and an unfiltered search second, then merges. Limits: 50,000 rows and 50 MB. Gated and non-table datasets are refused. Dataset names are validated because they go into URLs.
- A bundled synthetic churn dataset is the offline fallback.

### 3.6a Cleaning
`datasets.clean()` exists (creates a new version without duplicates) but no agent tool or route calls it. In practice, cleaning happens inside `features.prepare_features`, which is used for readiness and training: it drops ID-like columns, converts numbers stored as text, and drops duplicate rows.

### 3.7 Insights and baseline (`insights.py`, `baseline.py`, `analysis.py`)
Readiness grade from a documented scoring (rows, duplicates, missing values, lopsided answer, constant columns, copy-of-answer columns). Trust level combines the grade and how far the baseline beats a simple guess. The baseline is a scikit-learn random forest on 80% of rows, tested on the other 20%.

### 3.8 Agent (`services/agent/`)
- A custom tool-calling loop. The model client is OpenRouter (OpenAI-style tool format). A scripted fake client is used in tests.
- Tools: search_datasets, look_at_dataset, fetch_dataset, inspect_candidate, select_dataset, run_readiness, run_baseline, create_quote, request_payment, start_training, load_skill.
- Context engineering: short base prompt, state block rebuilt every step, skill index only, tools offered by project status, trimmed tool results, last 20 messages only.
- The gate runs before every tool. A tool not offered for the current status is refused even if the model asks for it.
- Loop limit: 12 steps per turn.
- Skills (`backend/app/skills/`): dataset-search, data-insights, cost-quote, plain-language.
- Not used yet: `agent_runs` table (steps are traced with no run id).

### 3.9 HTTP endpoints
- `GET /health`
- `POST /projects`, `GET /projects/{id}`
- `POST /projects/{id}/chat` (runs the agent; accepts approvals)
- `POST /projects/{id}/data` (upload CSV text)
- `POST /projects/{id}/quote/approve`
- `POST /projects/{id}/train`
- `POST /projects/{id}/refund/retry`
- `POST /projects/{id}/train` (background; returns run id)
- `GET /projects/{id}/training`, `POST /projects/{id}/training/stop`
- `GET /projects/{id}/trace`
- `POST /payments/orders`, `POST /payments/{id}/capture`
- `POST /webhooks/paypal`

There is no login. Anyone who can reach the API can call everything. That is a deliberate deferral.

## 4. Decisions made so far

| Decision | Choice |
|---|---|
| Agent runtime | Custom loop, no framework |
| Model access | OpenRouter only. LiteLLM not added |
| Dataset tools | Direct API calls, not MCP |
| Dataset sources for the MVP | Hugging Face plus bundled sample. Kaggle later |
| First paid job | CPU, scikit-learn on SageMaker |
| Database | SQLite for the demo, Postgres-compatible |
| Branching | Work on the session branch, merged to `main` when reviewed |
| Frontend | Placeholder until the API is stable |
| AWS money | $160 of new-account promotional credit (check expiry in the Billing console) |
| Where the app runs for the demo | Locally. AWS used only for S3 and SageMaker |
| Training on SageMaker | AWS scikit-learn image plus our script, no custom Docker image |
| Instance type | CPU only for the MVP; GPU later |
| Cap enforcement | Cap becomes SageMaker's maximum runtime, enforced by AWS |

## 5. What real-data testing found

On 2026-10-23 the real tools ran against `scikit-learn/churn-prediction` from Hugging Face (7,043 rows, the same size as the wireframe's Telco example).

1. A unique `customerID` column was one-hot encoded and hurt the baseline. The data still got an "A" grade. Fixed: ID-like columns are detected, reported, and ignored. Baseline time dropped from about 11 seconds to 1.5 seconds.
2. `TotalCharges` is numbers stored as text. Fixed: detected, reported, converted.
3. A finding said duplicates were "removed automatically" when nothing removed them. Fixed.
4. My first synthetic sample dataset had almost no signal, so the model could not beat the "always say stay" guess. Fixed by strengthening the signal.

Current result on the real data: about 78% right against 73.5% for a simple guess, so the trust level is Low. That is an honest result for this dataset.

## 6. Known gaps and risks

1. **Quotes are not realistic yet.** With placeholder prices and a small dataset, the quote is about 53 cents with a 52 to 53 cent range, because fixed fees dominate. The wireframe's "about 2 hours, $5" cannot appear until we choose a demo job that really takes 10 to 15 minutes, and measure real SageMaker timings and prices.
2. **Estimator accuracy is unknown.** There is no real cloud measurement to compare against, so the speed factor and startup time are guesses.
3. **The OpenRouter client has never been run.** The loop is tested only with scripted replies. Real models may call tools in ways we have not seen.
4. **No agent evaluation set yet** (a fixed list of goals with expected outcomes, run repeatedly).
5. **Search quality is untested at scale.** For "customer churn" the top Hugging Face results were mostly Telco copies with no stated license.
6. **Inngest Cloud and Supabase are unverified.** The Inngest runner needs a public API URL (tunnel) and real keys; Postgres support is tested only by building the engine and compiling the schema for Postgres. Neither can be checked from this container.
7. **No scheduled cleanup** for expired candidates or leftover cloud resources.
8. **Stop on the local backend** only takes effect between stages. The web app has no Stop button yet. The agent tool `start_training` is still blocking.
9. **No authentication.** Anyone can call any endpoint.
10. **Charging the cap** is a proposal, not yet confirmed.
11. **Unused tables** exist for funding, users and agent runs.
12. **Hugging Face rate limits** apply, and we send no token unless one is configured.

## 6a. Spec gaps found by audit (2026-10-24)

- `stopped` is a lifecycle state but nothing can set it yet (see `training.md` section 7).
- `agent.md` lists tools that do not exist: web search, a sandboxed analysis-code runner, a Terraform plan tool, a clean tool, a PayPal skill. Data analysis uses fixed functions, not model-written scripts.
- Agent limits for tokens per project, per-tool timeout and LLM cost ceiling are not implemented. Only the 12-step limit is.
- The cost backstop timer in `cost.md` and `training.md` is not implemented.
- No web app spec exists yet: screens, endpoints per screen, approval card payload, PayPal return and cancel pages.
- No SageMaker backend contract yet: script inputs and outputs, S3 layout, cost from billable time.

## 7. Next steps

AWS architecture is decided (section 4 and `training.md` section 2a). Remaining: verify the SageMaker SDK details in current AWS docs, write the Terraform (bucket, expiry rules, roles, budget alert), write the SageMaker training backend with mocked tests, then run the calibration jobs. Terraform cannot be applied from this cloud session: it needs AWS credentials you create yourself, ideally a limited IAM user, never the root account.

## 8. SageMaker backend update (2026-10-24)

Built without AWS credentials: `providers/training/sagemaker.py`, `sagemaker_script/train.py`, `services/sagemaker_cost.py` (cap to `MaxRuntimeInSeconds`, cost from billable seconds), `services/cost_report.py`, `infra/terraform/`, `backend/scripts/sagemaker_smoke.py`, and 28 mocked tests. Contract in `training.md` section 2b. Everything touching real AWS is unverified. A human must: create a limited IAM user (not root), review and apply the Terraform, check the `ml.m5.xlarge` training quota, pick the scikit-learn image version available in the region (default `1.4-2` does not match local 1.9.x), then run the smoke script once and use its output to calibrate `prices.py`. The backend expects the new `run(..., on_progress, should_stop)` signature; `services/training.py` and the interface in `base.py` are not changed here. With placeholder prices, caps under about 53 cents are refused as too small to run.
