# AIOAC (AI on a Click)

A user describes a prediction problem in plain words. An AI agent checks the data, runs a free baseline, quotes an estimated cost, asks for approval, runs a free pilot and forecasts the result, takes a PayPal (sandbox) hold, trains the model on AWS SageMaker, checks the result once on locked test data, then charges only the actual compute (plus a small success fee if the check passes) and voids the rest of the hold. Built for the PayPal AI Hackathon (submit by Nov 12, 2026, 12:00 pm PT; our internal target is Nov 11).

Detailed specs (read the one you need, not all of them):
- @specs/spec1.md : vision, scope, user journey, system overview, decisions
- @specs/agent.md : agent loop, tools, skills, permission levels, limits
- @specs/cost.md : cost estimation formula, quotes, caps, budget guard
- @specs/data.md : dataset search, storage lifecycle, insights, readiness
- @specs/training.md : training backends, Terraform, SageMaker
- @specs/payments.md : PayPal hold, capture and void flow ("Forecast, then verify"), ledger, webhooks
- @specs/db.md : database schema
- @specs/testing.md : test strategy and demo check
- @specs/status.md : what is built, stubbed or not started, decisions, known gaps (read this first)

## Stack
- Frontend: Next.js (TypeScript) in `frontend/`
- Backend: Python, FastAPI in `backend/`
- ML: scikit-learn, tabular data only (classification first)
- Agent LLM: via OpenRouter
- Training: `TrainingBackend` interface. `local` runs the free baseline. `sagemaker` runs the paid job.
- Payments: PayPal sandbox, REST API (Orders v2 + webhooks), behind a `PaymentProvider` interface with a mock for tests

## Hard rules (never break these)
1. Never start paid training until the SERVER has confirmed the PayPal hold (authorization). A frontend success screen is not proof.
2. Sandbox only. Never use or ask for real money, real cards or real PayPal passwords.
3. Never commit secrets. `.env` is gitignored. Only fake placeholders go in `.env.example`. The repo is public.
4. The ledger is append-only. Webhook handling is idempotent: store event and capture IDs so a repeated webhook can never credit or charge twice.
5. Every job has a hard spend cap. Training stops at the cap. Compute is captured at actual cost, never above the compute cap; the success fee only if the locked-test check passes; the rest of the hold is voided. If our own code or infrastructure fails, the whole hold is voided and the user pays $0. Never promise "pay $0 if the target is missed" (see LESSONS.md).
6. Do not guess PayPal endpoints, fields or event names. Check the current PayPal docs first.
7. Never promise model accuracy. Show a readiness score, a real baseline result on held-out data, and an estimated cost. Label every estimate as an estimate.
8. Plain language in the UI. No jargon like F1 or train/test split in the main flow.

## Human review required
Payment code, webhook verification, the ledger, secrets handling and spend caps. Make small changes there and explain them clearly so a human can review.

## How we work
- One small task at a time. Keep diffs small.
- Write tests for the payment provider, ledger and cost estimate before calling them done.
- Run the tests and the demo check before saying a task is finished.
- Cost estimate = measured baseline time scaled to full data x hourly price of the chosen instance + storage + platform fee. Prices live in one config file.
- UI follows the Figma wireframes: describe, data, readiness, pilot and forecast (4), quote (5), pay, train, result verified (12), result missed (13), receipt (14), not eligible (28), improve round (29). Crowdfunding was removed.

## Commands
Run from `backend/` after `pip install -e '.[dev]'`:
- Run backend: `uvicorn app.main:app --reload`
- Run frontend: TBD (not scaffolded yet)
- Run tests: `pytest`
- Demo check: `pytest tests/test_payments_and_demo.py` (full flow on the mock payment provider, no network)

## Submission checklist
Public repo with LICENSE (MIT) visible in About; README with setup and run steps and sandbox test instructions; demo video under 3 minutes on YouTube; clear text on how PayPal and AI are used.
