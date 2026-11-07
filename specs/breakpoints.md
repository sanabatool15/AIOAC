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
| F1 | Real mode has no chat: the describe step is goal text plus a CSV upload. Dataset discovery and the agent's explanations are not shown | `frontend/components/real/` | Render `GET /projects/{id}/messages`, `POST /chat` and approval cards once the chat route is stable (api.md A0, U5) | done 2026-11-06 for the describe step: `components/real/chat.tsx` + `lib/chat.ts`. History from `GET /messages`, the goal is sent once as the first message only when there is no history, Approve/Not now card (approve only on click, action = card `tool`), blocks, plain errors (503 falls back to upload). Chat exists only on the describe step; later steps still use buttons, and the chat is not shown after data is chosen. Checked with a scripted model only, never the real one |
| F2 | Paid steps (hold, authorize, train, settle) were never clicked through against real PayPal sandbox. Screens were checked only with intercepted responses | `components/real/pay-return.tsx`, `steps-run.tsx` | One manual run after D1 | open (owner): one run with the real PayPal sandbox buyer and `TRAINING_BACKEND=sagemaker`; the browser flow is covered only on the mock |
| F3 | After a missed target the Improve round reuses the free pilot form. No dedicated screen 29, and no explanation of the new hold | `steps-run.tsx` `ResultStep` | Optional polish | open |
| F4 | Try-one-record, CSV predictions, model download, sharing, usage, keys, plans, login were mock-only | mock screens | Hide or build, see section 3 of `frontend-integration.md` | done 2026-11-06 for everything with a backend route: login (earlier), model tab (one record, CSV, download), usage, billing history, sharing and the public result page (`frontend-integration.md` section 10). Plans, payment methods, invoices, API keys, integrations stay out on purpose |
| F5 | The demo path is only reachable at `/` and `/c/{id}`; the old mock routes (`/c/{id}/pay`, projects, billing, keys) still render mock screens that fail in real mode | `app/(app)/` | Redirect or hide in real mode | done: the mock routes and `mock-notice.tsx` are gone (step 3). Routes now: `/login`, `/signup`, `/`, `/c/[chatId]`, `/projects`, `/projects/[projectId]`, `/account/usage`, `/account/billing`, `/welcome`, `/pay/return`, `/pay/cancel`, public `/s/[token]` |
| F6 | `Stop` on the local backend takes effect only between stages (D2); the screen says "Stopping..." until the run ends | `TrainingStep` | Backend side | open |
| F7 | Frontend unit tests (`npm run test:unit`) use `tsx`; no component tests and no Playwright test for real mode | `frontend/unit/` | Add a real-mode Playwright run when a fake PayPal exists | done 2026-11-06: 6 Playwright files (11 tests) in `frontend/tests/` against the test launcher; no component tests |
| F8 | Two UIs (steps 2 to 9 done 2026-11-06: `components/real` deleted, quote, pay, train, result and receipt are polished; step 10 cleanup left): polished screens run on fake data, real-mode screens are plain. Goal is one polished UI on real data, with dead screens deleted and `USE_MOCK_API` removed | `frontend/components/shell`, `components/real`, `lib/mock-api.ts` | Plan in `frontend-integration.md` section 9, steps 1 to 11 | done 2026-11-06: one polished UI on real data, `components/real` and the mock deleted, unused types removed, 11 real-mode Playwright tests (`npm run test:e2e`). The full cycle with real PayPal and SageMaker is F2 |
| F9 | The approval card does not name the dataset (text is only "The agent wants to select dataset") | `backend/app/services/gate.py:73`, `services/agent/loop.py:267` | Add `detail {name, source, rows, columns, license, target}` and a plain `what` for `select_dataset` (frontend-integration 9.5, step 1) | done 2026-11-06: `select_dataset_card` in `services/agent/tools.py`, merged into the card by `loop.py`; shape in api.md A2 |

### 1c. Screens back on real data (E rows, 2026-11-06)

Routes for screens that were removed from the polished UI. Contract: `specs/api.md` section D. Free, owner-scoped (404 for others), no money logic touched.

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| E1 | No history screen data (versions, runs, quotes, payment) | `routes/screens.py`, `services/history.py` | `GET /projects/{id}/history` | done |
| E2 | No way to try, batch-run or download the trained model | `services/model_use.py` | `GET /projects/{id}/model`, `POST .../predict`, `POST .../predict-batch`, `GET .../model/download`; size and rate limits; plain message on a scikit-learn version mismatch | done |
| E3 | No usage totals or receipts list for the account | `services/account.py`, `repositories/account.py` | `GET /account/usage`, `GET /account/payments` | done |
| E4 | No public read-only result link | `services/share.py`, table `shares` | `POST/GET/DELETE /projects/{id}/share`, public `GET /public/results/{token}` (HUMAN REVIEW; allow-listed fields, per-IP rate limit). Owner must create the table and enable RLS (db.md) | done |
| E5 | No plain activity feed | `services/activity.py` | `GET /projects/{id}/activity`, built by code from the stored trace and the stored rows (readiness, free test, forecast, quote, payment, training), deduplicated | done 2026-11-06 |
| E6 | The rate limits are per process | `services/ratelimit.py` | A shared limiter when the API runs on several processes | open |

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

### 3b. Agent fixes from the first real-model run (gpt-5.4, Azure)

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| G1 | The agent chose the target accuracy itself (0.8) and ran pilot and quote in one turn | `services/agent/tools.py` `run_pilot`, `target.py` | Code guard: target must come from the user's own words, else `need_target`; prompt rule | fixed on branch claude/fix-agent |
| G2 | Markdown, ids like `uci:144`, decimals and cents in replies | `services/agent/context.py` | Short wording rules; state block and tool results in out-of-100 and dollars | fixed on branch claude/fix-agent |
| G3 | Price explanation was inaccurate (platform fee not visible) | `create_quote`, `blocks.py` | Quote result and block carry the stored breakdown; prompt line | fixed on branch claude/fix-agent |
| G4 | Approval card said Dataset '350' and column 'Y' | `fetch_dataset`, `select_dataset_card` | Candidate keeps the discovery title; optional `target_meaning` shown in the card | fixed on branch claude/fix-agent |
| G5 | Activity feed showed raw ids, approval text, and `[redacted key]` inside ids | `services/activity.py`, `runlog.py` | Titles only, synthetic text dropped; `sk-` pattern no longer matches inside a word or id | fixed on branch claude/fix-agent |
| G6 | Slow first turn (many looks and fetches) | `context.py` | Prompt: look at or fetch at most the top 2, do not search again. Existing limits (50,000 rows, 50 MB, 30 s HTTP, 60 s tool) kept; effect not measured offline | fixed on branch claude/fix-agent (effect unmeasured) |

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

## 6. Chat polish found in a real Azure run (2026-11-06)

| Id | Problem | Where | Fix | Status |
|---|---|---|---|---|
| H1 | Assistant text shown with raw markdown (`**bold**`, backticks, `- ` lists) | `components/shell/inline-chat.tsx` | Safe markdown reader, tests with XSS cases | fixed on branch claude/fix-chat-ui |
| H2 | Approval card title and facts: ids or the long sentence instead of a dataset name and a facts grid | `components/shell/chat-blocks.tsx`, `lib/chat.ts` | Title from `detail.name` (id-like falls back to `what`), grid with optional `target_meaning` | fixed on branch claude/fix-chat-ui |
| H3 | No sign of life during a reply that takes about 50 s | `components/shell/project-chat.tsx` | Calm indicator with rotating plain messages, `aria-live` polite, no network calls | fixed on branch claude/fix-chat-ui |
| H4 | Risk of raw cents or decimals on screens; activity text with `[redacted` | `components/`, `lib/screens.ts` | Guard test (money only through `dollars()`), activity test | fixed on branch claude/fix-chat-ui |
| H5 | Numbered lists rendered every item as "1." when blank lines separated them | `frontend/lib/markdown.ts` | Lists continue across blank lines, `start` = author's first number | fixed |
| H6 | Chat showed the server's "Yes, I approve ... Please carry it out." as a user bubble | `services/agent/loop.py`, `routes/projects.py` | Stored as message kind `approval` (kept in the model history, not returned by `/messages`) | fixed |
| H7 | "Not now" on an approval card was lost on reload | `lib/declined.ts`, `lib/chat-controller.ts` | Kept per project in localStorage (try/catch), calm card state plus follow-up line re-derived | fixed |
| H8 | No thinking indicator during the automatic first reply | `lib/chat-controller.ts`, `project-chat.tsx` | Goal shown and timer started when the boot call is sent ("Reading your goal...") | fixed |
| H9 | Agent said "pilot" and "cap" to the user | `services/agent/context.py`, `tools.py`, `target.py`, `cost-quote` skill | "free small test", "the most you can be charged" | fixed |
