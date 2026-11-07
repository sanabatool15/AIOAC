# HTTP API Contract

Status: written 2026-11-04 from the route code in `backend/app/routes/` and the services they call. Section A is BUILT and was read from code. Section B is PLANNED: a decided design that is not yet in the code. Updated 2026-11-04: B1 to B5, the messages route, `GET /projects/{id}/payment`, `approve_url`, `not_started` and idempotent approve are now built (section A0 below).

Conventions (built):
- One id: the project id. `/chats/{id}`, `/jobs/{id}` and `/agreements/{id}` are aliases of it (see `payments.md` section 6).
- Money is whole cents. Rates (accuracy, target, confidence, fraction) are 0 to 1. JSON keys are snake_case.
- Errors are FastAPI's `{"detail": "<plain message>"}`. A body that fails validation gives 422 with `detail` as a list.
- Login (2026-11-06, section C): every route except `GET /health`, `POST /webhooks/paypal` and `/auth/signup|login|logout|demo` needs the session cookie `aioac_session`. 401 `please sign in` without a valid one; 503 `login is not set up` when `SECRET_KEY` is missing. CORS allows `CORS_ORIGINS` (default `http://localhost:3000`). No URL prefix: `http://localhost:8000`.
- Quote and forecast numbers are estimates (`is_estimate: true`).

## A. BUILT endpoints

### A1. Health
`GET /health` -> 200 `{"ok": true, "llm": {"configured": bool}}`. `llm.configured` is false when the model key is empty or a placeholder such as `your-openrouter-key`; the key itself is never returned.

### A2. Projects (`routes/projects.py`)

`POST /projects` body `{goal: string}` -> 200 `{id, status}` (status `described`).

`GET /projects/{id}` -> 200 `{id, goal, status, readiness_grade, trust_level, baseline, quote}`.
- `baseline` is `{accuracy, simple_guess_accuracy}` (0 to 1) or null.
- `quote` is the latest quote or null: `{id, estimate_cents, low_cents, high_cents, cap_cents, success_fee_max_cents, approved}`.
- 404 `project not found`.
- Fuller since 2026-11-04 (see A0).

`POST /projects/{id}/chat` body `{message?: string, approve?: string[]}` -> 200 `{status, text, card, blocks}`. 503 with a plain `detail` when no real model key is configured (empty or placeholder); 409 if a turn is already running.
- `status`: `reply` | `awaiting_approval` | `limit` | `error`. `card` is null except for `awaiting_approval`.
- `card` (L1 approval): `{what, level, tool, args, detail?}`, for example tool `select_dataset` with `{candidate_id, target}`. For `select_dataset`, `detail` is `{name, source, rows, columns, license, target, target_meaning}` (each null when unknown; `target_meaning` is the optional plain-words `target_meaning` argument the model fills) and `what` is plain words, e.g. `Use "Credit card default" (UCI, 30,000 rows) and predict "Y": whether the next payment was missed` (without a meaning: `... and predict the column "Y"`; bundled samples say "sample data"). `detail.name` is the dataset title shown by discovery, never the source id. The `quote` block gains an optional `breakdown` `{compute_estimate_cents, compute_cap_cents, storage_cents, platform_fee_cents, success_fee_estimate_cents, success_fee_max_cents}` (same numbers as the quote; nothing recomputed).
- Agent tool result `run_pilot` without a target the user named in their own words: `{need_target: true, baseline_percent: <free test, out of 100 or null>, hint}`. No forecast is stored. The explicit route `POST /chats/{id}/pilot` is unchanged. Other cards keep the generic `what` and have no `detail`. The user approves by sending the request again with `approve: ["select_dataset"]` (the gate action name).
- `blocks`: list (empty when nothing applies), built by code from this turn's successful tool results, never from model text. Types: `readiness` `{grade, findings: [{kind: "OK"|"NOTE", text}], trust}` (`trust` is null until the free test ran); `baseline` `{accuracy, simple_guess_accuracy, trust}` (0 to 1); `quote` `{quote_id, estimate_cents, low_cents, high_cents, cap_cents, success_fee_cents, is_estimate: true}`; `pay` `{payment_id, approve_url, hold_cents}`. They are stored on the turn's assistant message (`messages.payload`, new column: delete any old `aioac.db`) and returned by `GET /projects/{id}/messages` as `blocks` on every item (`[]` for user messages).
- `limit`: a step, token, cost, repeat or timeout limit was hit; `text` explains it in plain words.
- `error`: the model service failed, including a missing LLM key. The HTTP status is still 200.
- 404 project not found. 409 `The assistant is still working on your last message...` while a turn for this project runs.
- No `blocks` and no `approve_url` in the reply. The payment link comes from `POST /payments/orders`.

`POST /projects/{id}/data` body `{name: string, csv_text: string}` -> 200 `{candidate_id, rows}`. 400 with a plain message if the file is rejected. It only stores a candidate. Choosing it is done today only by the agent's `select_dataset` tool (needs the user's approval). 404 project not found.

`POST /projects/{id}/quote/approve` no body -> 200 `{approved: true, cap_cents}`.
- 400 `no quote yet`. 400 `this quote has expired; ask for a new one`. 400 with a status pair like `awaiting_payment -> awaiting_payment` on a second call (not idempotent, B6).

`POST /projects/{id}/train` no body -> 200 `{run_id, status}` (status `running`). Returns at once; the job runs in the background.
- 409 with the gate's reason: no quote, no server-confirmed hold for the current quote, project not `paid`, or training already started (a second call). 403 only when the global budget guard refuses.
- 503 `could not start the training job; nothing was charged and your hold is being released`. The hold is voided.

`GET /projects/{id}/training` -> 200 `{run_id, status, stage, fraction, elapsed_seconds, spend_so_far_cents, spend_is_estimate, cap_cents, eta, stop_requested, result}`.
- `status`: `running` | `done` | `stopped` | `failed`. `fraction` is 0 to 1. `cap_cents` is the compute cap. `eta` is `{low_seconds, high_seconds, is_estimate}` while running, else null.
- `result`: null while running. `done`: `{accuracy, simple_guess_accuracy, runtime_seconds, verification: {value, target, passed}}`. `failed`: `{error}`. `stopped`: `{stopped_by_user: true}`.
- 404 `no training has started for this project` (planned 200 `not_started`, B6).

`POST /projects/{id}/training/stop` -> 200 `{run_id, stop_requested: true}`. 409 `there is no training running for this project`. The user pays the compute used so far, no success fee.

`POST /projects/{id}/settle/retry` -> 200 `{payment_state, status}`. 409 with the payment error text (no finished run, no confirmed hold). 502 `The payment service could not be reached yet...`. Safe to repeat.

`POST /projects/{id}/cancel` -> 200 `{payment_state, status}`. Only while the project is `awaiting_payment` or `paid`. 409 `it is too late to cancel...` or `there is no hold to cancel`. 502 if PayPal is unreachable. Releases the whole hold; project ends `voided`.

`GET /projects/{id}/trace` -> 200 list of `{seq, kind, content}` (agent steps, gate decisions, forecast, `settle_failed`). For debugging, not for screens.

### A3. Free pilot and forecast (`routes/forecast.py`)

`POST /chats/{id}/pilot` body `{target: number}`, `0 < target < 1` (422 otherwise) -> 200 `{forecast_id, metric, target, is_estimate, predicted_metric, band_low, band_high, confidence, eligible, reason, pilot, min_confidence, suggested_target, issues}`.
- Free. Needs status `baseline_done` or `quoted`, else 409 `run the free baseline first`.
- If the project is `done` and the last run missed its target, it first reopens to `baseline_done` (the Improve round). If the target was met: 409 `the finished run reached its target, so there is nothing to improve`.
- 400 with a plain message when the pilot cannot run (no dataset, too few rows). 404 `not found`.
- "Not eligible" is a 200 with `eligible: false`, a `reason`, `issues[]` and a `suggested_target`.

`GET /jobs/{id}/forecast` -> 200 the same view for the latest forecast. 404 `no pilot has been run yet`.

### A4. Quote (`routes/quotes.py`)

`POST /agreements/{id}/quote` no body -> 200 `{quote_id, is_estimate, estimate_cents, low_cents, high_cents, cap_cents, compute_estimate_cents, compute_cap_cents, success_fee_estimate_cents, success_fee_max_cents, forecast_confidence, target, terms}`.
- `estimate`, `low`, `high` and `cap` include the success fee. `cap_cents` is the PayPal hold.
- 409 with a plain message: no pilot yet, forecast not eligible (its reason), no baseline, quote above the per-job maximum, bad status. 404 `not found`.
- Not restricted by status beyond the above. Statuses `baseline_done`, `quoted` and `awaiting_payment` move to `quoted`. A new quote after a hold exists orphans that hold (`breakpoints.md` P2).

### A5. Payments (`routes/payments.py`)

`POST /payments/orders` body `{project_id}` -> 200 `{payment_id, hold_cents, compute_max_cents, success_fee_max_cents, approve_url, state}`. State `none` means nothing is held yet.
- Returns the existing payment for the current quote if there is one (a reload resumes it), even if it is `declined` or `expired`.
- 409 gate reason (no quote, quote not approved, quote expired); 409 also when the payment for the quote is dead (expired, declined, voided: ask for a new quote) or the project can no longer take a payment. 404 unknown project. 502 `The payment service could not be reached. Nothing was charged...`.

`POST /payments/{payment_id}/authorize` no body -> 200 `{held: bool, state}`. The server asks PayPal to place the hold and checks the amount. Only a server-confirmed hold sets `held` and moves the project to `paid`. `held: false` means not held yet or declined. 404. 409 on an amount mismatch. 502 if PayPal is unreachable.

`GET /payments/{payment_id}` -> 200 `{payment_id, state, hold_cents, compute_captured_cents, fee_captured_cents, released_cents, total_charged_cents}`. 404. No `approve_url` and no project id (B7).

`POST /webhooks/paypal` raw PayPal body and headers -> 200 `{result: "processed" | "duplicate" | "ignored"}`. 400 `invalid signature`. 409 `amount mismatch`. A webhook never creates a hold or marks a project paid.

Payment `state`: `none`, `held`, `compute_captured`, `fee_captured`, `fee_skipped`, `released`, `voided`, `expired`, `declined`.

### A6. No route exists for
Predict (one record or CSV), model download, share link.

## A0. Added 2026-11-04 (step 1, non-payment items; BUILT)

- CORS: `CORSMiddleware`, setting `CORS_ORIGINS` (comma list, default `http://localhost:3000`), credentials allowed.
- `POST /projects/{id}/data/{candidate_id}/select` body `{target?: string}` -> 200 `{rows, target, status: "data_chosen"}`. Wraps `datasets.select_candidate`. 409 `a dataset was already chosen for this project` unless status is `described`. 400 `unknown dataset`, `column 'x' not found`, or `which column should we predict? Columns: a, b, ...` when `target` is missing. Not built: a suggested target stored on the candidate; today `target` is required in practice.
- `POST /projects/{id}/readiness` -> 200 `{grade, findings: [{kind, text}], status}` (wraps `analysis.readiness`). 409 `choose a dataset first` (status `described`) or `the readiness check was already done for this project`.
- `POST /projects/{id}/baseline` -> 200 `{accuracy, simple_guess_accuracy, trust_level, status}` (wraps `analysis.baseline`). 409 `choose a dataset first`, `run the readiness check first`, or `the free test was already done for this project`.
- `GET /projects` -> `[{id, goal, status, created_at}]`, newest first.
- `GET /projects/{id}` now also returns `dataset {rows, columns, target, source, license}`, `readiness {grade, findings}`, `forecast` (the A3 view), `payment {payment_id, state, approve_url, hold_cents}` and `run {run_id, status}`; each is null until it exists.
- `GET /projects/{id}/messages` -> `[{id, role, text, kind, blocks, card?, created_at}]`. Chat text of the user and assistant (kind `chat` or `note`) and approval cards (`kind: "card"`, role `assistant`, `text` = the card's `what`, `card` = the full card). Tool results, skills and empty tool-call turns are not returned. The note the server writes for the model after an Approve click (`Yes, I approve: ...`) is stored as kind `approval`: the model still reads it, this route never returns it.
- `GET /projects/{id}/payment` -> the receipt body plus `project_id`; 404 `no payment has been started for this project`. `GET /payments/{id}` now includes `approve_url`.
- `GET /projects/{id}/training` before any run -> 200 `{status: "not_started"}`.
- `POST /projects/{id}/quote/approve` is idempotent: an approved, unexpired quote returns 200 `{approved: true, cap_cents}` again. An expired one still gives 400.

Still in B: the 409 status codes on `/train` and `/payments/orders` (step 2).

## B. PLANNED (not built)

B1 to B5 and B7, and the `not_started` and idempotent-approve parts of B6, are built (see A0). The text below is kept as the design record.

Order of work: `breakpoints.md`.

### B1. CORS
`CORSMiddleware` in `main.py`. New setting `CORS_ORIGINS` (comma-separated, default `http://localhost:3000`), credentials allowed, placeholder in `.env.example`.

### B2. Select the dataset
`POST /projects/{id}/data/{candidate_id}/select` body `{target?: string}` -> 200 `{rows, target, status: "data_chosen"}`.
- Same service as the agent's `select_dataset` tool: `datasets.select_candidate(session, storage, project, candidate_id, target)`. It copies the candidate to permanent storage, deletes the other candidates and moves the project to `data_chosen`. The user's click is the approval.
- How the target is chosen today: the service requires `target`, and the tool requires it as an argument. The model usually takes it from the `suggested_target` that `fetch_dataset` returned (bundled samples carry one). The candidate row does not store it.
- Planned: use `target` if sent. If omitted, use a suggested target stored on the candidate when it was fetched (to be added); if there is none, 400 `which column should we predict?` with the column names. Unknown column: 400 `column 'x' not found`. Unknown candidate: 400 `unknown dataset`. Wrong status: 409.

### B3. Readiness and baseline
`POST /projects/{id}/readiness` -> 200 `{grade, findings: [{kind: "OK"|"NOTE", text}], status}`. Wraps `analysis.readiness` (the agent's `run_readiness`). `data_chosen -> readiness_done`.
`POST /projects/{id}/baseline` -> 200 `{accuracy, simple_guess_accuracy, trust_level, status}`. Wraps `analysis.baseline` (the agent's `run_baseline`). `readiness_done -> baseline_done`.
Both are free (gate level 0). Wrong status: 409 with a plain message, for example `choose a dataset first`, `run the readiness check first`.

### B4. List projects
`GET /projects` -> 200 `[{id, goal, status, created_at}]`, newest first.

### B5. Fuller `GET /projects/{id}`
Today's fields plus: `dataset` `{rows, columns, target, source, license}`; `readiness` `{grade, findings}`; `forecast` (the A3 view); `payment` `{payment_id, state, approve_url, hold_cents}`; `run` `{run_id, status}`. Each is null if it does not exist yet.

### B6. Messages, blocks, status codes
- `GET /projects/{id}/messages` -> `[{id, role: "user"|"assistant", text, kind, card?, created_at}]`, from the `conversations` and `messages` tables. Tool results and skills are not returned.
- `POST /projects/{id}/chat` reply gains `blocks`: typed items the screen can render, built by code from stored state (for example the approval card, the payment link), not by the model.
- `/train` and `/payments/orders`: wrong-status refusals return 409, not 403.
- `GET /projects/{id}/training` returns 200 `{status: "not_started"}` instead of 404.
- `quote/approve` is idempotent: approving an already approved, unexpired quote returns 200 with the same body.

### B7. Payment lookup
`GET /projects/{id}/payment` returns the `GET /payments/{id}` body plus `approve_url` and `project_id`, or 404. `GET /payments/{id}` also gains `approve_url`.

### B8. Status to screen

Screen numbers are those in `specs/frontend-integration.md`.

| Project status | Screen | Notes |
|---|---|---|
| `described` | Describe / data | Chat, discover or upload, then select (B2) |
| `data_chosen` | Readiness | Call readiness (B3) |
| `readiness_done` | Free test | Call baseline (B3) |
| `baseline_done` | Target and forecast (5); Not eligible (28) if `forecast.eligible` is false | Pilot, then quote |
| `quoted` | Quote (5) | Approve calls `quote/approve`, then `/payments/orders` |
| `awaiting_payment` | Pay (6) | `payment.state` `none`: send the browser to `approve_url`; on return call authorize |
| `paid` | Pay return | Hold confirmed; the frontend calls `/train` |
| `training` | Train (10) | Poll `/training`; Stop |
| `done` | Verified (12) if `result.verification.passed`, else Missed (13); then Result and receipt (14); Improve (29) after a miss | Receipt from the payment |
| `failed` | Our failure | Transient while the hold is voided; poll until `voided` |
| `stopped` | Stopped receipt | Compute used so far, no fee. A user stop stays `stopped`; a cancel moves on to `voided` |
| `voided` | Our failure or cancel, "you pay $0" | New screen (frontend-integration item 17) |

### B9. Units and frontend conversions
Backend: cents, 0 to 1, snake_case, one project id. The mock frontend uses dollars, percent, camelCase and separate chat, job and agreement ids. One adapter layer (`frontend/lib/api.ts`) converts:
- cents to dollars, in a display helper only;
- 0 to 1 to percent (times 100) and back for the target;
- snake_case to camelCase;
- one id everywhere (agreement id = project id);
- precision and recall to one accuracy number; drop the three target tiers and the max price field;
- hold parts "Experiment 1/2" and "Safety buffer" to "Compute (up to)", "Success fee (up to, only if verified)" and "Released";
- screen choice from `status` (B8), not from the chat name.


## C. Login and ownership (BUILT 2026-11-06)

### C1. Auth routes (`routes/auth.py`, `services/auth.py`)
- `POST /auth/signup` body `{email, password}` (password 8 to 200 characters, email must look like an address) -> 200 `{user: {id, email, org_id}}` and an httpOnly cookie. Creates a personal organization and the user in one transaction. 409 `that email is already registered`. 422 on bad input.
- `POST /auth/login` same body and reply. 401 `wrong email or password` (same text and similar timing for an unknown email). 429 after 10 failures within 10 minutes for the same email and IP (in memory, per process).
- `POST /auth/logout` -> 200 `{ok: true}`, clears the cookie.
- `GET /auth/me` -> 200 `{user}` or 401.
- `POST /auth/demo` -> 404 unless `DEMO_LOGIN_ENABLED=true`; then logs in a fixed demo user (`demo@aioac.example`, random password, so it cannot be used with `/auth/login`).
- 503 `login is not set up` on all of the above (and on every protected route) when `SECRET_KEY` is empty, shorter than 16 characters or a placeholder. `GET /health` adds `auth: {configured: bool}`.
- The cookie holds a signed JWT (HS256) with `sub` (user id), `org` (org id) and `exp` (`JWT_TTL_MINUTES`, default 720). Name `aioac_session`; `COOKIE_SECURE` (default false) and `COOKIE_SAMESITE` (default lax). A token whose org no longer matches the user's org is refused. The browser must send credentials (`credentials: "include"`); CORS already allows credentials for `CORS_ORIGINS`.

### C2. Ownership rule
A project belongs to one user and one org (`projects.user_id`, `projects.org_id`, set from the signed-in user on `POST /projects`). Every route that takes a project id (`/projects/{id}/...`, `/chats/{id}/pilot`, `/jobs/{id}/forecast`, `/agreements/{id}/quote`) loads it through `deps.owned_project`. `POST /payments/orders` checks the project the same way; `POST /payments/{id}/authorize` and `GET /payments/{id}` load the payment together with its project owner.
- **404, never 403.** A project or payment that is not yours answers exactly like one that does not exist (`project not found` / `payment not found`), so existence is not leaked. This replaces the old `not found` bodies of the forecast and quote routes and the empty 404 of the payment routes.
- `GET /projects` returns only the signed-in user's projects.
- Open on purpose: `GET /health`, `POST /webhooks/paypal` (PayPal's signature is the authentication). The background job runner and start-up crash recovery have no request user and work on run ids only.
- Conversations and messages are only reached through the owned project. The agent never accepts a conversation id from another project.
- Projects made before login have no owner and cannot be reached (delete the old `aioac.db`).
- Test: `tests/e2e/test_tenant_isolation.py` lists every route and fails when a new one is not classified.

## D. Screens back on real data (BUILT 2026-11-06, `routes/screens.py`)

All routes are owner-scoped like section C (404 for a project that is not yours, never 403), except the one public route. Money is cents, rates are 0 to 1, keys are snake_case. Timestamps are ISO strings.

- `GET /projects/{id}/history` -> `{versions: [{id, parent_id, rows, columns, target_column, source, license, notes, created_at}], runs: [{id, status, backend, cost_cents, started_at, finished_at, result: {accuracy, simple_guess_accuracy, verification: {value, target, passed}} | null}], quotes: [{id, estimate_cents, low_cents, high_cents, cap_cents, approved, created_at}] (newest first), payment: {payment_id, state, hold_cents, compute_captured_cents, fee_captured_cents, released_cents, total_charged_cents} | null}`. Storage keys are never returned.
- `GET /projects/{id}/activity` -> `[{when, kind, text}]`, oldest first, built by code (fixed sentences, no raw JSON, no storage keys, no secrets) from two sources merged by time: the agent trace (searches, dataset looks, gate decisions, for example `Searched open datasets for loan default`, `Looked at "Credit card default" (30,000 rows)`) and the stored rows (updated 2026-11-06), so steps done with buttons appear too: `Checked data readiness: grade A`, `Ran the free test: about 87 out of 100 right`, `Forecast ready: about N% chance of reaching 80 out of 100 right (an estimate); ...`, `Price estimate ready: about $0.56 (an estimate; ...)`, `You approved the price estimate`, `Payment hold requested`, `PayPal hold confirmed by the server`, `Training started`, `Training finished ...`, `Charged $X for the compute used`, `Released $X of the hold`, `The hold was released in full; you pay $0`. A trace line for a step a stored row already records (within 2 minutes) is dropped, so nothing repeats. Settlement lines use the end time of the last run (the payment row has no per-step time). Owner-scoped.
  Live steps (2026-11-07): the chat polls this route every 2 s while a turn runs (a GET, free, never blocked by the turn lock; the agent's steps are committed as they happen). More fixed sentences: `Found N possible datasets: "A", "B", "C"` (max 3 names, untrusted tag removed), `Left out N near-copies ...`, `Skipped datasets that cannot be used: not a plain table (1), too few rows (2)` (only the four reasons `discovery.prefilter` can return, from the `dropped` field of the `discover_datasets` result), `Nothing found was a good fit for your goal`, `"X" is not a plain table, skipped`, `"X" needs a login or approval, skipped`, `Only the first N rows of "X" were kept ...`, `Could not use "X", so the assistant tried another way`, and a `working` line (`Searching open datasets for ...…`, `Looking at a dataset…`) for a tool call with no result yet (dropped after 3 minutes, so a crashed turn does not look busy). Titles come from the earlier discovery result in the same trace, never the dataset id.
- `GET /projects/{id}/model` -> `{available: false}` before a model exists, else `{available, trained_at, target, accuracy, simple_guess_accuracy, is_estimate_note, sklearn_version, size_bytes, usable, unusable_reason, columns: [{name, kind: "number"|"text", example, choices|null}], classes}`. `columns` are the inputs the saved pipeline learned (row-ID and answer columns are not inputs); `example` comes from the pipeline's own fitted imputers; `choices` are the known values of a text column with at most 20. `usable: false` with a plain `unusable_reason` when the file cannot be loaded (for example a scikit-learn version mismatch); `columns` is then empty.
- `POST /projects/{id}/predict` body `{record: {column: value}}` -> `{prediction, probabilities: {class: p} | null, note: "an estimate, not a promise"}`. Missing columns are allowed (the pipeline fills them). 400 plain message for an empty record, an unknown column, or a non-number in a number column. 404 `there is no trained model for this project yet`. 409 plain message if the model cannot be loaded or run here. 429 after 120 calls a minute per user.
- `POST /projects/{id}/predict-batch` body `{csv_text}` (at most 5 MB and 5,000 rows) -> `{rows, columns, preview (first 20 rows with a prediction column, plus confidence when available), csv_text (all rows)}`. Extra columns (ids, the answer) are kept in the output and ignored by the model; at least one known column is required. Same 400, 404, 409 as predict. 429 after 10 calls a minute per user.
- `GET /projects/{id}/model/download` -> the saved scikit-learn pipeline (joblib) as an attachment. Headers `X-Requires-Scikit-Learn` (the version it was trained with) and `X-Model-Note`; both are exposed to the browser through CORS. 404 when there is no model.
- Models, predictions and downloads are free: no gate, no money. A model exists only after a training run finished `done` (a stopped run saves none).
- `GET /account/usage` -> `{projects, training_runs, compute_charged_cents, success_fees_cents, released_cents, llm_tokens, llm_cost_micros, recent_activity: [{when, kind, text}] (at most 20, newest first)}`. Only the signed-in user's own projects (user and org) are counted. `llm_cost_micros` is 0 when the model service reports no cost.
- `GET /account/payments` -> `[{payment_id, project_id, goal, state, hold_cents, compute_captured_cents, fee_captured_cents, released_cents, total_charged_cents, created_at}]`, newest first.
- Sharing, owner side: `POST /projects/{id}/share` -> `{token, url_path: "/s/<token>", created_at}` (idempotent: returns the active share); `GET /projects/{id}/share` -> `{enabled, token|null, created_at|null}`; `DELETE /projects/{id}/share` -> `{enabled: false}` (revokes; idempotent). Creating again after a revoke makes a new token.
- **PUBLIC, HUMAN REVIEW:** `GET /public/results/{token}` needs no login (classified open in `tests/e2e/test_tenant_isolation.py`). It returns exactly `{goal, status, dataset: {name, rows, target}|null, baseline: {accuracy, simple_guess_accuracy}|null, verification: {value, target, passed}|null, finished_at|null, is_estimate_note}`. Never money, payment ids, emails, user or organization ids, storage keys or traces (a test asserts the exact key set and scans for leaks). An unknown, malformed or revoked token gives the same `404 {"detail": "result not found"}`. The token is `secrets.token_urlsafe(32)` (43 characters, 32 random bytes), looked up by its unique index. In-memory limit of 60 calls a minute per client address, then 429.
- Limits are per process and in memory (`services/ratelimit.py`).
