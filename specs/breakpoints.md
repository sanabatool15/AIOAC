# Known Breakpoints and Fix Plan

Status: 2026-11-04. Found by audits and re-checked against the code. Paths are under `backend/app/` unless noted; line numbers are approximate and will move. Every row is `open`. The API target is in `specs/api.md` section B.

## 1. UI cannot drive the backend

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| U1 | No CORS: the browser blocks calls from `localhost:3000` | `main.py` (no middleware) | Add `CORSMiddleware`, setting `CORS_ORIGINS` (api.md B1) | open |
| U2 | No routes to select a dataset, run readiness or run the baseline. Only the agent can, through chat | `routes/projects.py` | Add the three routes as thin wrappers over `datasets.select_candidate`, `analysis.readiness`, `analysis.baseline` (api.md B2, B3) | open |
| U3 | `GET /projects/{id}` is thin: no dataset, forecast, payment, run or readiness findings; no list of projects | `routes/projects.py:48-56` | Fuller read and `GET /projects` (api.md B4, B5) | open |
| U4 | No message history route, though messages are stored | `routes/projects.py`; tables `conversations`, `messages` | `GET /projects/{id}/messages` (api.md B6) | open |
| U5 | Chat reply is `{status, text, card}`: no `blocks`, no `approve_url` | `routes/projects.py:59-66` | Add `blocks` built from stored state (api.md B6) | open |
| U6 | No payment lookup by project, so a reload cannot find `payment_id`; receipt lacks `approve_url` | `routes/payments.py:272-281` | `GET /projects/{id}/payment`; add `approve_url` (api.md B7) | open |
| U7 | Wrong-status errors use 403 on `/train` and `/payments/orders`; `/training` is 404 before a run; `quote/approve` fails on a repeat | `routes/projects.py:103,117,87`, `routes/payments.py:249` | 409, `not_started`, idempotent approve (api.md B6) | open |
| U8 | Frontend has no HTTP client, no status-to-screen mapper and no quote-approve step. All calls go to `frontend/lib/mock-api.ts` | `frontend/lib/` | `lib/api.ts` plus adapters and a status mapper (api.md B8, B9) | open |
| U9 | Units, ids and metrics differ: dollars vs cents, percent vs 0-1, precision/recall vs accuracy, chat/job/agreement ids vs one project id, camelCase vs snake_case | `frontend/lib/types.ts`, `mock-api.ts` | One adapter layer (api.md B9); see `frontend-integration.md` section 4 | open |

## 2. Payments (HUMAN REVIEW REQUIRED for every item, CLAUDE.md)

Small changes only, each with a test on the mock provider, each explained to the reviewer.

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| P1 | `confirm_hold` returns early when the payment is already `held` or later. If the hold was saved but the move to `paid` failed or was skipped, the project stays `awaiting_payment` for good | `services/payments.py:66-84` | On the early return, also move an `awaiting_payment` project to `paid` (same check as line 82) | open |
| P2 | A new quote after a hold exists is allowed at any status. The latest quote changes, the old hold is no longer found by `current_payment`, and it is never voided | `services/cost/quotes.py:47` and `19-49` | Refuse a new quote while a non-terminal hold exists, or void that hold first | open |
| P3 | `_settle` catches only `ProviderError`. A `PaymentError` (for example "provider did not confirm") leaves the project in `training`. `retry_settle` never moves the project to `done` | `services/training.py:68-77`, `119-149`, `213-222` | Catch `PaymentError` too and trace `settle_failed`; after a successful retry move the project to its final status | open |
| P4 | `cancel` moves the project to `stopped` before `void_all`. If the void fails the project is stuck in `stopped` with a live hold | `services/payments.py:167-177` | Void first, then transition; or keep status until the void succeeded | open |
| P5 | A late `authorize` after a cancel can place a new hold that nothing voids. `confirm_hold` does not check the project status | `services/payments.py:66-84` | Refuse (and void at PayPal) when the payment is `voided` or the project is no longer `awaiting_payment` | open |
| P6 | On an amount mismatch the hold exists at PayPal but is saved nowhere and not voided | `services/payments.py:78-79` | Void the authorization, then raise | open |
| P7 | `create_order` returns an `expired` or `declined` payment forever for that quote. `expire_stale_holds` only marks the row; it does not void at PayPal | `services/payments.py:53-57`, `180-188` | Create a new order (new quote or new payment row) after a dead payment; void at PayPal on expiry | open |
| P8 | Races on `/train` and `/payments/orders`: no compare-and-swap on the status. Two requests can both pass the check; a second order hits the unique `quote_id` and raises `IntegrityError` (500) | `routes/projects.py:96-110`, `services/payments.py:55-63`, `db/tables.py:113` | Atomic status change (`UPDATE ... WHERE status='paid'`); catch `IntegrityError` and return the existing payment | open |

## 3. Agent

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| A1 | The `start_training` tool blocks until the job ends and holds the project's turn lock the whole time | `services/agent/tools.py:243-245` | Call `training.start_training` plus the job runner and return the run id | open |
| A2 | No tools or next step for `awaiting_payment` with an expired quote, a declined hold, or the terminal states (`done`, `failed`, `stopped`, `voided`). Only `load_skill` is offered | `services/agent/context.py:70-95` | Add status-specific guidance and, where needed, a read-only tool | open |
| A3 | A missing LLM key returns HTTP 200 with `status: "error"` | `integrations/llm/openrouter.py:120-122`, `services/agent/loop.py:153-158` | Return a clear 503 on a missing key, or show the error state in the UI | open |
| A4 | `check_args` only checks required keys and non-empty strings. Wrong types for numbers and arrays pass | `services/agent/guards.py:37-48` | Check types from the tool's JSON schema | open |
| A5 | If the user approves a card and the model then replies with text only, the approval is spent without running the tool | `services/agent/loop.py:173-186` | After an approval, run the approved call from the stored card, not from the model | open |

## 4. Demo and project risks

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| D1 | PayPal sandbox hold, capture, second capture and void have never run for real | `integrations/paypal/provider.py`, `tests/integration/test_paypal_sandbox.py` | Run the two-step live check; record PayPal's limits | open |
| D2 | The local backend costs 0, so the receipt shows nothing captured and the demo money step looks empty | `integrations/training_local/` | A believable demo job (see Order of work, step 5) | open |
| D3 | Prices are placeholders; quotes are about 53 cents | `services/cost/prices.py` | Measure one real job and replace them | open |
| D4 | The real LLM has never been run; the agent evals have no real pass rates | `backend/evals/` | One real run after the owner is told (see below) | open |
| D5 | No authentication. Deferred on purpose | `routes/` | Plan: a demo user created by `POST /auth/demo`, then optional email login | open |

## 5. Order of work

1. Routes and CORS: U1 to U7.
2. Payment fixes: P1 to P8, one small reviewed change at a time.
3. Frontend: HTTP client, adapters and status mapper (U8, U9).
4. Real PayPal sandbox check (D1), one real LLM run (D4), optionally AWS.
5. A believable demo job (D2, D3).
6. Auth (D5).
7. Agent items A1 to A5 fit between steps 2 and 4.

Real-LLM runs, real PayPal sandbox runs and any AWS run (step 4) cost money or use shared keys. Tell the owner first and wait for a yes. Never use real money.
