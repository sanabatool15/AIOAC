# Next session: one real UI, fully wired to the backend

How to use: start a new session (it gets its own branch made from `main`, which has this file and all the work described below) and say: "Read specs/next-session-prompt.md and do it." The owner speaks Roman Urdu: reply to the owner in Roman Urdu only, short and honest. Tell the owner BEFORE any real Azure, PayPal or AWS use.

## Where things stand (2026-11-06)

- `main` holds everything below, including the real-mode chat (57db718). Backend: about 460 tests pass. Demo check: `pytest tests/e2e/test_payments_and_demo.py`.
- Backend built: login with orgs and owner-scoped routes (404 for others), free path routes (select, readiness, baseline, pilot, quote, approve), PayPal hold/capture/void, background training (inline runner), SageMaker backend, agent with blocks, messages history, `python -m app.db.init --check/--upgrade`.
- Real runs done: PayPal sandbox lifecycle (2026-11-02), SageMaker jobs (scikit-learn 1.9-0), Azure `gpt-5.4` evals 22/22, one real chat on 2026-11-06 (agent found UCI datasets and produced a select card). Never run: PayPal webhook, the whole browser cycle (login to receipt) with real PayPal, Inngest.
- Supabase: schema reset and recreated by the owner, RLS enabled on all tables. It is reachable only from the owner's laptop (this container blocks Postgres ports). The owner runs everything locally on Windows with PowerShell, using `uv`.
- Container env vars hold REAL keys (Azure, AWS, PayPal, DATABASE_URL). For tests always strip them: `env -u AZURE_OPENAI_API_KEY -u AZURE_OPENAI_BASE_URL -u AZURE_OPENAI_MODEL -u LLM_PROVIDER -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN -u PAYPAL_CLIENT_ID -u PAYPAL_CLIENT_SECRET -u DATABASE_URL <command>`. Never print secrets. Real Azure use needs the owner's yes first (credits are limited).

## The problem to solve

There are two UIs. The polished one (about 35 screens, `frontend/components/shell`, etc.) runs on fake data (`lib/mock-api.ts`). The simple one (`frontend/components/real/`, used when `NEXT_PUBLIC_USE_MOCK_API=false`) is wired to the backend but looks plain. The owner wants ONE UI: the polished look, driven by the real backend, and no useless screens.

## Goals, in order

1. **Plan first (short, in a spec).** Decide with subagents how to move the real wiring (`lib/api.ts`, `api-real.ts`, `adapters.ts`, `status.ts`, `lib/chat.ts`, the pay return pages) under the polished screens. Prefer reusing polished components and feeding them through adapters. Write the plan in `specs/frontend-integration.md` before coding.
2. **Demo path on the polished UI, real data only:** login and logout, projects list, describe with chat (agent finds datasets; approval card), data check with readiness findings, free test, target and forecast, not-eligible, quote with approve, pay (PayPal redirect, `/pay/return`, `/pay/cancel`), train with progress and Stop, result (verified or missed), receipt, voided or failed ("you pay $0"). Status decides the screen (api.md section B8).
3. **Remove what has no backend** (owner: "no useless things"): API keys, plans and billing wizard, payment methods, usage, sharing and invites, integrations, OAuth and forgot-password buttons, live view and research steps, fake billing history. Delete screens and nav entries, do not just hide them. Decide whether to keep a tiny dev-only mock for tests, or drop `USE_MOCK_API`; keep the code simpler either way. Then delete the old simple `components/real/` screens once the polished ones cover the path.
4. **Fix known gaps:**
   - Approval card must name the dataset (name, source, rows, answer column), not just "select dataset" (backend card text in the gate/loop plus the UI).
   - Later steps may also use chat (optional; buttons are fine).
   - Receipt must look right: demo uses `TRAINING_BACKEND=sagemaker`, so about 52 cents captured on the sandbox and the rest released. Say "estimate" next to every estimate; never promise accuracy; plain words.
   - 9 stale Playwright specs (old "pay $0" copy): update them if mock mode stays, delete if mock mode goes.
   - `/auth/me` 401 noise in the console; logout `next` redirect; JWT stays valid after logout (known, document).
5. **Inngest (owner wants it).** Inline runner is the default and is tested. Add the Inngest path only as a local check: `JOB_RUNNER=inngest`, `INNGEST_DEV=1`, run the Inngest Dev Server on the owner's laptop (`npx inngest-cli@latest dev -u http://localhost:8000/api/inngest`), prove one training run goes through it, keeps `retries=0` and idempotency, and a restart voids the hold. Write exact Windows commands. If it is shaky, say so and keep `JOB_RUNNER=inline` as the documented path. No Inngest Cloud keys unless the owner creates them.
6. **Optional, ask the owner first:** try-one-record (`POST /projects/{id}/predict` plus a small screen) for the demo video.
7. **Owner does by hand (prepare a checklist, do not do for them):** the full browser cycle with the PayPal sandbox buyer approving; one real-Azure chat session. After it, record results in `specs/integration-testing.md` and `specs/breakpoints.md`.

## Rules

- Read `CLAUDE.md` first. Hard rules 1 to 8 stay. Payment code, webhook, ledger, secrets and caps need small commits and plain explanations for human review.
- Method: subagents for reading, docs, code and the final audit, to save context. Order: read docs, update docs, code, audit again with the stripped env, list what still breaks.
- Small commits, footer lines `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` and `Claude-Session: <the session URL>`. Push to the branch. Push to `main` only after the owner says so; before that run backend `python -m pytest -q`, frontend `npm run typecheck`, `npm run lint`, `npm run test:unit`, `npm run build`, the demo check, and a secret scan (the repo is public).
- Never use real money or real cards. Sandbox only.

## Definition of done

The owner signs up on the polished UI, says "I have no data", approves a dataset card that names the dataset, goes through readiness, free test, target, quote, PayPal sandbox hold, SageMaker training and the receipt, with no fake data anywhere, and the README has exact Windows steps. Then: demo script under 3 minutes, the README text on how PayPal and AI are used, LICENSE visible. Submission deadline: 2026-11-12 12:00 pm PT (internal target 2026-11-11).

## Rotate after submission

The owner showed partial keys in screenshots (AWS, Azure, PayPal sandbox secret, DB URL). Rotate them after submitting.
