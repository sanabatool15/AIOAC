# Next session: one real UI, fully wired to the backend

How to use: start a new session (it gets its own branch made from `main`, which has this file and all the work described below) and say: "Read specs/next-session-prompt.md and do it." The owner speaks Roman Urdu: reply to the owner in Roman Urdu only, short and honest. Tell the owner BEFORE any real Azure, PayPal or AWS use.

## Where things stand (2026-11-06)

- `main` holds everything below, including the real-mode chat (57db718). Backend: about 460 tests pass. Demo check: `pytest tests/e2e/test_payments_and_demo.py`.
- Backend built: login with orgs and owner-scoped routes (404 for others), free path routes (select, readiness, baseline, pilot, quote, approve), PayPal hold/capture/void, background training (inline runner), SageMaker backend, agent with blocks, messages history, `python -m app.db.init --check/--upgrade`.
- Real runs done: PayPal sandbox lifecycle (2026-11-02), SageMaker jobs (scikit-learn 1.9-0), Azure `gpt-5.4` evals 22/22, one real chat on 2026-11-06 (agent found UCI datasets and produced a select card). Never run: PayPal webhook, the whole browser cycle (login to receipt) with real PayPal, Inngest.
- Supabase: schema reset and recreated by the owner, RLS enabled on all tables. It is reachable only from the owner's laptop (this container blocks Postgres ports). The owner runs everything locally on Windows with PowerShell, using `uv`.
- Container env vars hold REAL keys (Azure, AWS, PayPal, DATABASE_URL). For tests always strip them: `env -u AZURE_OPENAI_API_KEY -u AZURE_OPENAI_BASE_URL -u AZURE_OPENAI_MODEL -u LLM_PROVIDER -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN -u PAYPAL_CLIENT_ID -u PAYPAL_CLIENT_SECRET -u DATABASE_URL <command>`. Never print secrets. Real Azure use needs the owner's yes first (credits are limited).

## Done since this file was written (2026-11-06)

- One polished UI on the real backend; mock mode and `components/real` are gone (`frontend-integration.md` sections 9 and 10).
- Approval card names the dataset; unused frontend code removed; `/auth/me` noise and logout redirect handled earlier.
- Restored screens on real data: project detail, Model tab (one record, CSV, download), Usage, Billing history, sharing and public page, Welcome.
- Activity feed built from stored rows plus the trace.
- 11 real-mode Playwright tests (`npm run test:e2e`) against the test launcher; README with Windows PowerShell steps and "How PayPal is used" / "How AI is used".

## What remains (in order)

1. **Owner, by hand (do not do for them):** the full browser cycle with the PayPal sandbox buyer approving and `TRAINING_BACKEND=sagemaker`, and one real-Azure chat session. Then record the results in `specs/integration-testing.md` and `specs/breakpoints.md` (F2). Tell the owner before any real Azure, PayPal or AWS use.
2. **Inngest decision.** Inline runner is the default and tested. If the owner wants Inngest, prove one run through the local Dev Server (`JOB_RUNNER=inngest`, `INNGEST_DEV=1`, `npx inngest-cli@latest dev -u http://localhost:8000/api/inngest`), keep `retries=0` and idempotency, check that a restart voids the hold. Not verified so far; otherwise keep `inline` and say so.
3. **Demo money step (D2, D3):** a believable SageMaker demo job and measured prices, so the receipt shows real captured cents.
4. **E6** shared rate limiter (only if the API runs on several processes).
5. **Submission:** demo script and video under 3 minutes, README text (done), LICENSE visible. Deadline 2026-11-12 12:00 pm PT (internal target 2026-11-11).

## Rules

- Read `CLAUDE.md` first. Hard rules 1 to 8 stay. Payment code, webhook, ledger, secrets and caps need small commits and plain explanations for human review.
- Method: subagents for reading, docs, code and the final audit, to save context. Order: read docs, update docs, code, audit again with the stripped env, list what still breaks.
- Small commits, footer lines `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` and `Claude-Session: <the session URL>`. Push to the branch. Push to `main` only after the owner says so; before that run backend `python -m pytest -q`, frontend `npm run typecheck`, `npm run lint`, `npm run test:unit`, `npm run build`, the demo check, and a secret scan (the repo is public).
- Never use real money or real cards. Sandbox only.

## Definition of done

The owner signs up on the polished UI, says "I have no data", approves a dataset card that names the dataset, goes through readiness, free test, target, quote, PayPal sandbox hold, SageMaker training and the receipt, with no fake data anywhere, and the README has exact Windows steps. Then: demo script under 3 minutes, the README text on how PayPal and AI are used, LICENSE visible. Submission deadline: 2026-11-12 12:00 pm PT (internal target 2026-11-11).

## Rotate after submission

The owner showed partial keys in screenshots (AWS, Azure, PayPal sandbox secret, DB URL). Rotate them after submitting.
