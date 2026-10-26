# Implementation Status

What has been built, what is stubbed, what has not been started, and what we learned along the way. Updated 2026-10-26 (see section 10 for the money model change). This file describes reality; the other specs describe intent. Where they differ, this file says so.

## 1. Summary

| Area | State |
|---|---|
| Repository setup (license, ignore rules, env template, README) | Done |
| Specs (`specs/`) | Draft 1. Gaps: async training and Stop, SageMaker backend contract, web app (see section 6a) |
| Database schema | Done, matches `db.md` |
| Project lifecycle (state machine) | Done |
| Permission gate | Done |
| Cost estimator and quotes | Done, with placeholder prices |
| Payment orchestration (hold, capture, void), ledger, webhooks | Done on the mock provider (money model changed 2026-10-26, section 10) |
| PayPal sandbox provider | Written against the current PayPal OpenAPI specs and tested on mocked HTTP. Checked against the real sandbox on 2026-10-25: token request and create order work (the order returned a sandbox approval link), and capturing before the buyer approves is correctly refused (422). Not yet checked against the real sandbox: a buyer approving, authorize (hold), partial capture, a second capture on the same hold, void, webhook signature. Needs human review |
| Agent loop, tools, skills, context engineering | Done, tested with scripted model replies only. Conversation memory (stored messages, token-budgeted history), run log, per-project turn lock, generic tool errors, untrusted-text wrapping added 2026-10-24 |
| OpenRouter model client | Written, never run (no API key yet) |
| Agent loop, tools, skills, context engineering | Done, tested with scripted model replies only. Limits (tokens, cost, tool timeout, repeats), run ids in `agent_runs`, schema checks and a false-claim guard added 2026-10-24 |
| OpenRouter model client | Rewritten against the current OpenRouter docs: argument parsing, null content, several calls per reply, retry once, usage and cost. Tested on mocked HTTP only; never run against the real service (no API key yet) |
| Agent evaluation harness (`backend/evals/`) | Built and tested offline (`--fake`). Never run with a real model |
| Agent playground notebook (`backend/notebooks/`) | Built, runs on the fake model |
| Hugging Face dataset tools | Done, verified against the live service |
| Dataset discovery (2026-10-25) | Built: source registry (`hf:`, `uci:`, `oml:`), UCI and OpenML sources (shapes read from the live services, tests use recordings), hand-checked list of 12 (all re-checked live), ranking and copy-collapse pipeline, `discover_datasets` tool (level 0, offered in `described`), `discover-datasets` skill, 4 offline eval cases. Not built: browser tool, Kaggle. Never run with a real model. See `specs/agent/11-dataset-discovery.md` |
| Dataset storage lifecycle | Done (local folder storage) |
| Insights, readiness grade, free baseline | Done, verified on real data |
| Training backends | Local done (reports progress, honours stop). SageMaker is a stub |
| Background training, progress, Stop, crash recovery | Done on the inline runner (tested). Inngest Cloud runner written against SDK 0.5.19, never run against real Inngest Cloud |
| Database | SQLite default. Postgres/Supabase configurable, never connected to a real database |
| Terraform, AWS storage | Not started |
| Training backends | Local done. SageMaker backend, training script and cap math written and tested on mocked boto3 only; never run against AWS |
| Terraform, AWS storage | Written in `infra/terraform/` (bucket, roles, app policy, budget alert). Not validated (terraform not installed) and never applied. No S3 storage provider for the app yet; the SageMaker backend uploads its own job files |
| Web app | Not started (placeholder folder) |
| Login | Not started. Crowdfunding was removed from the product (2026-10-26) |
| Claude Code harness (rules, hooks) | Not started. PayPal plugin installed but needs a sandbox token |

Tests: 281, all passing, no network needed. Run `pytest` in `backend/`.

Agent memory, logging and turn lock (2026-10-24): `conversations` and `messages` tables (delete any old local `aioac.db`), `services/agent/memory.py`, `services/agent/runlog.py`, `evals/show.py`, `evals/replay.py`, `scripts/show_run.py`. See `specs/agent/06` and `10`. Never run against a real model yet.

How to view a log: `cd backend && python -m evals.run --fake --repeats 1 -v` prints live lines; `python -m evals.show <log id or folder> [--tools] [--md] [--raw] [--level]` reads a past run under `backend/logs/` (git-ignored); `python scripts/show_run.py <agent_run_id or project_id>` reads the app database.

## 2. Repository layout

```
CLAUDE.md          project instructions and hard rules
specs/             system specification (this folder)
backend/app/
  models/          database tables
  repositories/    database access (ledger and webhook tables are insert-only)
  services/        business logic
    agent/         loop, tools, skills loader, context building, memory (stored history), runlog (event log)
  providers/       swappable parts: payments, training, storage, datasets, llm
  routes/          HTTP endpoints
  skills/          markdown playbooks the agent loads on demand
backend/tests/     281 tests
frontend/          placeholder only
```

## 3. What each part does

### 3.1 Lifecycle (`services/lifecycle.py`)
States: described, data_chosen, readiness_done, baseline_done, quoted, awaiting_payment, paid, training, done; side exits failed, stopped, voided (renamed from `refunded` on 2026-10-26). Steps cannot be skipped. `paid` cannot be set unless a server-confirmed hold exists.

### 3.2 Permission gate (`services/gate.py`)
Three levels. L0 runs freely. L1 (choosing a dataset) needs the user's approval. L2 (request payment, start training) needs checks on stored state:
- payment request: an approved, unexpired quote;
- training: a server-verified payment for the current quote, project status `paid`, and room in the global budget.

Every decision, allowed or refused, is written to the trace.

### 3.3 Cost (`services/cost.py`, `prices.py`, `quotes.py`)
Implements the formula in `cost.md`: time the baseline on 5%, 10% and 20% samples, fit a curve on a log scale, project to full size, convert to money, add storage and platform fee, produce estimate, low, high, and cap (cap equals the high end). A quote above the per-job maximum ($7) is refused. Quotes expire after 60 minutes.

Prices in `prices.py` are placeholders (one instance type, 25 cents per hour, 240 seconds of startup, 1 cent storage, 50 cents platform fee).

### 3.4 Payments (`services/payments.py`, `providers/payments/`)
- Money model "Forecast, then verify" (`payments.md`): the buyer approves a PayPal hold for the cap, nothing is charged. After training and one check on locked test data, the actual compute is captured, the success fee only if verified, and the rest of the hold is voided. Our own failure voids everything.
- A hold or capture only counts when the provider reports it confirmed and the amount matches.
- The browser route and the webhook route both end in the same idempotent step, so a repeat is harmless.
- Webhooks: signature checked first, event recorded once, then applied.
- Compute and fee captures are recorded in the ledger (`compute_capture`, `fee_capture`) with unique keys per training run. Every capture and void carries an idempotency key.
- If the provider fails during settle, the job still finishes, a `settle_failed` trace step is written, and the saved hold state shows which step is next. `POST /projects/{id}/settle/retry` resumes it; repeats are harmless. Provider outages return a plain 502 instead of a crash.
- The PayPal approval link is stored on the payment, so a page reload resumes the same payment. (This added a column: delete any old local `aioac.db` before running.)
- The ledger refuses an entry that would take a project's balance below zero.
- `mock.py` is complete. `paypal.py` implements create hold order, authorize, capture, void and webhook signature verification (Orders v2, Payments v2, verify-webhook-signature). It refuses any host but the sandbox and sends the webhook body to PayPal byte-for-byte. Tests use a mocked transport (`tests/test_paypal_provider.py`). Not yet exercised against the real sandbox.

### 3.5 Training (`services/training.py`, `providers/training/`)
After the gate allows it: run the backend, cap the cost at the quote's cap, store the model, add the cost to the global spend, verify once on the locked test set, then settle (capture, then void the rest). If the backend fails, the project goes to failed and then voided, and the whole hold is released. By default the backend is `local`, which costs nothing, so the default demo voids most of the hold. The `sagemaker` backend is implemented against mocked clients (see `training.md` section 2b) and has never talked to AWS.

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
- Skills (`backend/app/skills/`): dataset-search, data-insights, cost-quote, plain-language, plus data-leakage, lopsided-classes, choosing-the-target-column, suspiciously-good-baseline, too-little-data, explaining-results-plainly. No money rules in skills.
- `agent_runs` is used: one row per turn with steps, tokens, model cost and stop reason. Added columns (`tokens_used`, `llm_cost_micros`, `stop_reason`, `ended_at`): delete any old local `aioac.db`. Gate steps get the run id when the turn ends.
- Limits: 12 steps, 80,000 tokens per turn, 600,000 per project, USD 1.00 model cost per project (only when the service reports cost), 60 s per free tool, repeat guard. Plain-language messages when hit.
- The state block now lists fetched candidate ids, because tool results are not kept between turns and the model needs the id to propose `select_dataset` again after the user approves.
- Reply guard: replies that claim payment, training or a settlement the state does not support are replaced with a correction (keyword-based, imperfect).

### 3.9 HTTP endpoints
- `GET /health`
- `POST /projects`, `GET /projects/{id}`
- `POST /projects/{id}/chat` (runs the agent; accepts approvals)
- `POST /projects/{id}/data` (upload CSV text)
- `POST /projects/{id}/quote/approve`
- `POST /projects/{id}/train`
- `POST /projects/{id}/settle/retry`
- `POST /projects/{id}/cancel` (before the run: voids the whole hold)
- `POST /chats/{id}/pilot`, `GET /jobs/{id}/forecast`, `POST /agreements/{id}/quote` (aliases of the project id)
- `POST /projects/{id}/train` (background; returns run id)
- `GET /projects/{id}/training`, `POST /projects/{id}/training/stop`
- `GET /projects/{id}/trace`
- `POST /payments/orders`, `POST /payments/{id}/authorize` (the server confirms the hold), `GET /payments/{id}` (receipt)
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
3. **The OpenRouter client has never been run for real.** It is tested on mocked HTTP, including malformed outputs. Real models may behave in ways we have not seen. Run `python -m evals.run --model <id> --repeats 3` with a key.
4. **Agent evaluation set exists but has no real results yet.** 7 cases in `backend/evals/cases/`. Real pass rates are unknown, and the keyword checks will need tuning after the first real runs.
5. **Search quality is untested at scale.** For "customer churn" the top Hugging Face results were mostly Telco copies with no stated license.
6. **Inngest Cloud and Supabase are unverified.** The Inngest runner needs a public API URL (tunnel) and real keys; Postgres support is tested only by building the engine and compiling the schema for Postgres. Neither can be checked from this container.
7. **No scheduled cleanup** for expired candidates or leftover cloud resources.
8. **Stop on the local backend** only takes effect between stages. The web app has no Stop button yet. The agent tool `start_training` is still blocking.
9. **No authentication.** Anyone can call any endpoint.
10. **Money model** is decided (2026-10-26) but only tested on the mock; PayPal's limits on captures per authorization and hold duration are unchecked.
11. **Unused tables** exist for funding (removed feature), users and agent runs.
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

## 9. Future work note (2026-10-26)

Instance selection from data size and a GPU / deep learning extension are written up as future work in `specs/future-instances-and-gpu.md`. Nothing is built; the demo uses the single CPU instance.

## 10. Money model changed (2026-10-26)

The old model "charge the cap, then refund the unused amount" and the crowdfunding stretch are gone. The new model is "Forecast, then verify" (`specs/payments.md`, `LESSONS.md`): free baseline, free pilot on about 5-10% of the data, forecast with confidence (below 0.60 is not sold), one quote (estimated compute plus a success fee of 5% of compute, and a hard cap), a PayPal hold for the cap, full run, one check on a locked test set, capture of actual compute always, capture of the success fee only if verified, void of the rest. Our own failure voids the whole hold. Unused holds expire after 24 hours. Project status `refunded` is now `voided`; payments became `payment_holds`; endpoints changed as listed in section 3.9.

State: the code for this exists and is tested on the mock provider and mocked HTTP only. The PayPal sandbox has not been tried for authorize, partial capture, second capture, void or webhook. Not designed yet: the "change of engineering approach" step that lifts a low forecast (see `payments.md` section 2a). Older rows in this file that mention charging the cap or refunds describe the previous model and have been updated where they were wrong.
