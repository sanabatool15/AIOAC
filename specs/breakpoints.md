# Known Breakpoints and Fix Plan

Status: 2026-11-04. Found by audits and re-checked against the code. Paths are under `backend/app/` unless noted; line numbers are approximate and will move. Rows are `open` unless marked. The API target is in `specs/api.md` section B.

## 1. UI cannot drive the backend

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| U1 | No CORS: the browser blocks calls from `localhost:3000` | `main.py` (no middleware) | Add `CORSMiddleware`, setting `CORS_ORIGINS` (api.md B1) | done |
| U2 | No routes to select a dataset, run readiness or run the baseline. Only the agent can, through chat | `routes/projects.py` | Add the three routes as thin wrappers over `datasets.select_candidate`, `analysis.readiness`, `analysis.baseline` (api.md B2, B3) | done |
| U3 | `GET /projects/{id}` is thin: no dataset, forecast, payment, run or readiness findings; no list of projects | `routes/projects.py:48-56` | Fuller read and `GET /projects` (api.md B4, B5) | done |
| U4 | No message history route, though messages are stored | `routes/projects.py`; tables `conversations`, `messages` | `GET /projects/{id}/messages` (api.md B6) | done |
| U5 | Chat reply is `{status, text, card}`: no `blocks`, no `approve_url` | `routes/projects.py:59-66` | Add `blocks` built from stored state (api.md B6) | done (re-audit 2026-11-04: `/chat` and `/messages` return `blocks`; `tests/e2e/test_chat_blocks.py` passes; `approve_url` comes from the payment lookup) |
| U6 | No payment lookup by project, so a reload cannot find `payment_id`; receipt lacks `approve_url` | `routes/payments.py:272-281` | `GET /projects/{id}/payment`; add `approve_url` (api.md B7) | done |
| U7 | Wrong-status errors use 403 on `/train` and `/payments/orders`; `/training` is 404 before a run; `quote/approve` fails on a repeat | `routes/projects.py:103,117,87`, `routes/payments.py:249` | 409, `not_started`, idempotent approve (api.md B6) | done (409 for not-ready cases via `gate.NotReady`; 403 stays for the budget guard; pilot message accurate per status) |
| U8 | Frontend has no HTTP client, no status-to-screen mapper and no quote-approve step. All calls go to `frontend/lib/mock-api.ts` | `frontend/lib/` | `lib/api.ts` plus adapters and a status mapper (api.md B8, B9) | done for the demo path (2026-11-04): `lib/api.ts`, `api-real.ts`, `adapters.ts`, `status.ts`, quote-approve step in the Pay button |
| U9 | Units, ids and metrics differ: dollars vs cents, percent vs 0-1, precision/recall vs accuracy, chat/job/agreement ids vs one project id, camelCase vs snake_case | `frontend/lib/types.ts`, `mock-api.ts` | One adapter layer (api.md B9); see `frontend-integration.md` section 4 | done for the demo path: real-mode screens (`components/real/`) use cents-to-dollars, 0-1 to out-of-100, one project id, accuracy only. Mock screens still use the old units |

### 1b. Frontend wiring left over (F rows, 2026-11-04)

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| F1 | Real mode has no chat: the describe step is goal text plus a CSV upload. Dataset discovery and the agent's explanations are not shown | `frontend/components/real/` | Render `GET /projects/{id}/messages`, `POST /chat` and approval cards once the chat route is stable (api.md A0, U5) | open |
| F2 | Paid steps (hold, authorize, train, settle) were never clicked through against real PayPal sandbox. Screens were checked only with intercepted responses | `components/real/pay-return.tsx`, `steps-run.tsx` | One manual run after D1 | open (re-audit: no run against the real sandbox; `POST /payments/orders` without credentials answers a clean 502, no stack trace) |
| F3 | After a missed target the Improve round reuses the free pilot form. No dedicated screen 29, and no explanation of the new hold | `steps-run.tsx` `ResultStep` | Optional polish | open |
| F4 | Try-one-record, CSV predictions, model download, sharing, usage, keys, plans, login are still mock-only (no backend routes) | mock screens | Hide or build, see section 3 of `frontend-integration.md` | open |
| F5 | The demo path is only reachable at `/` and `/c/{id}`; the old mock routes (`/c/{id}/pay`, projects, billing, keys) still render mock screens that fail in real mode | `app/(app)/` | Redirect or hide in real mode | partly (re-audit: old mock routes show a "real backend only" notice via `mock-notice.tsx` instead of failing; they are not redirected) |
| F6 | `Stop` on the local backend takes effect only between stages (D2); the screen says "Stopping..." until the run ends | `TrainingStep` | Backend side | open |
| F7 | Frontend unit tests (`npm run test:unit`) use `tsx`; no component tests and no Playwright test for real mode | `frontend/unit/` | Add a real-mode Playwright run when a fake PayPal exists | partly (re-audit: `npm run test:unit` has 22 passing tests; still no real-mode Playwright run) |

## 2. Payments (HUMAN REVIEW REQUIRED for every item, CLAUDE.md)

Small changes only, each with a test on the mock provider, each explained to the reviewer.

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| P1 | `confirm_hold` returns early when the payment is already `held` or later. If the hold was saved but the move to `paid` failed or was skipped, the project stays `awaiting_payment` for good | `services/payments.py:66-84` | On the early return, also move an `awaiting_payment` project to `paid` (same check as line 82) | done |
| P2 | A new quote after a hold exists is allowed at any status. The latest quote changes, the old hold is no longer found by `current_payment`, and it is never voided | `services/cost/quotes.py:47` and `19-49` | Refuse a new quote while a non-terminal hold exists, or void that hold first | done |
| P3 | `_settle` catches only `ProviderError`. A `PaymentError` (for example "provider did not confirm") leaves the project in `training`. `retry_settle` never moves the project to `done` | `services/training.py:68-77`, `119-149`, `213-222` | Catch `PaymentError` too and trace `settle_failed`; after a successful retry move the project to its final status | done |
| P4 | `cancel` moves the project to `stopped` before `void_all`. If the void fails the project is stuck in `stopped` with a live hold | `services/payments.py:167-177` | Void first, then transition; or keep status until the void succeeded | done |
| P5 | A late `authorize` after a cancel can place a new hold that nothing voids. `confirm_hold` does not check the project status | `services/payments.py:66-84` | Refuse (and void at PayPal) when the payment is `voided` or the project is no longer `awaiting_payment` | done |
| P6 | On an amount mismatch the hold exists at PayPal but is saved nowhere and not voided | `services/payments.py:78-79` | Void the authorization, then raise | done |
| P7 | `create_order` returns an `expired` or `declined` payment forever for that quote. `expire_stale_holds` only marks the row; it does not void at PayPal | `services/payments.py:53-57`, `180-188` | Create a new order (new quote or new payment row) after a dead payment; void at PayPal on expiry | done (a dead payment is refused with 409 and a new quote makes a new payment; the row is not reused because its idempotency keys come from its id) |
| P8 | Races on `/train` and `/payments/orders`: no compare-and-swap on the status. Two requests can both pass the check; a second order hits the unique `quote_id` and raises `IntegrityError` (500) | `routes/projects.py:96-110`, `services/payments.py:55-63`, `db/tables.py:113` | Atomic status change (`UPDATE ... WHERE status='paid'`); catch `IntegrityError` and return the existing payment | done |

## 3. Agent

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| A1 | The `start_training` tool blocks until the job ends and holds the project's turn lock the whole time | `services/agent/tools.py:243-245` | Call `training.start_training` plus the job runner and return the run id | done |
| A2 | No tools or next step for `awaiting_payment` with an expired quote, a declined hold, or the terminal states (`done`, `failed`, `stopped`, `voided`). Only `load_skill` is offered | `services/agent/context.py:70-95` | Add status-specific guidance and, where needed, a read-only tool | fixed: `create_quote` offered at `awaiting_payment`; expired-quote note in the state block; failed/stopped/voided get plain next-step text and no tools |
| A3 | A missing LLM key returns HTTP 200 with `status: "error"` | `integrations/llm/openrouter.py:120-122`, `services/agent/loop.py:153-158` | Return a clear 503 on a missing key, or show the error state in the UI | fixed: `/chat` 503, `/health` `llm.configured` |
| A4 | `check_args` only checks required keys and non-empty strings. Wrong types for numbers and arrays pass | `services/agent/guards.py:37-48` | Check types from the tool's JSON schema | fixed: string, number, integer, boolean, array (items, min/max), object |
| A5 | If the user approves a card and the model then replies with text only, the approval is spent without running the tool | `services/agent/loop.py:173-186` | After an approval, run the approved call from the stored card, not from the model | fixed: the server runs the card's call (see agent.md); turn deadline `AGENT_TURN_DEADLINE_S` (120) ends a turn with `limit/timeout` |

## 4. Demo and project risks

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| D1 | PayPal sandbox hold, capture, second capture and void have never run for real | `integrations/paypal/provider.py`, `tests/integration/test_paypal_sandbox.py` | Run the two-step live check; record PayPal's limits | done 2026-11-02: authorize, repeated authorize, partial capture, second capture, repeated capture/void with same request id, void of remainder and refused capture after void all passed on the real sandbox. Still unchecked: webhook signature, more than two captures per hold, hold lifetime |
| D2 | The local backend costs 0, so the receipt shows nothing captured and the demo money step looks empty | `integrations/training_local/` | A believable demo job (see Order of work, step 5) | open |
| D3 | Prices are placeholders; quotes are about 53 cents | `services/cost/prices.py` | Measure one real job and replace them | open |
| D4 | The real LLM has never been run; the agent evals have no real pass rates | `backend/evals/` | One real run after the owner is told (see below) | done: real model gpt-5.4 (Azure) passed 22/22 eval runs (see `specs/integration-testing.md`) |
| D5 | No authentication. Deferred on purpose | `routes/` | Email and password login, org per signup, owner-scoped routes; optional `POST /auth/demo` behind `DEMO_LOGIN_ENABLED` | done 2026-11-06 (api.md section C; frontend still to wire, send cookies) |
| D6 | An existing Supabase database has tables from older schema versions (missing columns such as `users.password_hash`), because `create_all` never alters tables | `app/db/init.py`, `app/db/check.py` | `python -m app.db.init --check`, then `--upgrade --yes` | script built, owner must run --check then --upgrade --yes on Supabase |

## 5. Order of work

1. Routes and CORS: U1 to U7.
2. Payment fixes: P1 to P8, one small reviewed change at a time.
3. Frontend: HTTP client, adapters and status mapper (U8, U9).
4. Real PayPal sandbox check (D1), one real LLM run (D4), optionally AWS.
5. A believable demo job (D2, D3).
6. Auth (D5).
7. Agent items A1 to A5 fit between steps 2 and 4.

Real-LLM runs, real PayPal sandbox runs and any AWS run (step 4) cost money or use shared keys. Tell the owner first and wait for a yes. Never use real money.
