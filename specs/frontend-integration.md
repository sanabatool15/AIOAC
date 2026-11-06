# Frontend Integration Plan

Status: draft, updated 2026-10-27 after the frontend was merged onto the payment-port branch. The merge changed only wording and cleanup (section 7); no screen calls the backend yet. Read it to see what we have, what is missing, and what we must decide.

## 1. How the frontend gets its data today

The frontend does not call our backend at all. Every screen asks small functions in `frontend/lib/mock-api.ts` for data. These functions return fixed, made-up answers after a short pause. Chats like "baseline", "agreement", "verified" and "missed" are just prepared stories picked by name. "Connecting" means this: replace each mock function with a real web request to the backend, and change the screens so they read the backend's field names and units. The backend is the final money model. So the frontend must change to fit it, not the other way round.

## 2. Money and flow screens

Backend ids: there is one id, the project id. Backend money is whole cents. Backend rates are 0 to 1 (0.8 means 80 out of 100). The mock uses dollars and percent (80).

| Mock function | Screen | What it does | Backend endpoint | Main differences |
|---|---|---|---|---|
| startChat | Home, first prompt | Makes a chat with the user's goal | `POST /projects` `{goal}` | Returns `{id, status}`. Mock ids look like `chat-xyz`. The mock "sample" flag has no backend twin (data comes from upload or the agent). |
| sendMessage | Chat box | Sends one user message | `POST /projects/{id}/chat` `{message, approve[]}` | Reply is `{status, text, card}`. Mock returns one message. No streaming. A second send during a turn gives 409. |
| getChat (new chat) | Describe / data | Loads messages and cards | NONE for history. Closest: `GET /projects/{id}` and `/trace` | Backend stores messages but has no endpoint to list them. Mock has `blocks` (steps, readiness, etc). Backend has `card` and `status` only. |
| getChat baseline | 3 data / readiness / baseline | Shows readiness grade and free test result | `GET /projects/{id}` (`readiness_grade`, `trust_level`, `baseline`) | Baseline runs only through the agent chat. No direct "run baseline" endpoint. Mock has `precision`, `recall`, `targetPrecision`. Backend has `accuracy`, `simple_guess_accuracy` (0 to 1). |
| getChat agreement | 5 quote | Shows 3 target tiers (Safe, Recommended, Ambitious) | `POST /chats/{id}/pilot` `{target}` then `GET /jobs/{id}/forecast` | Backend has no tiers. It has one target and returns `confidence`, `band_low`, `band_high`, `suggested_target`. Tiers could be built from `suggested_target`. |
| createAgreement | 5 quote | Saves target and max price | `POST /chats/{id}/pilot` then `POST /agreements/{id}/quote` | Mock takes `{precision, minRecall, maxUsd}`. Backend takes only `target` (accuracy, 0 to 1). The user does not pick a max price. We compute it and return `cap_cents`. |
| holdAgreement | 5 to 6 | Starts the PayPal hold, returns a link | `POST /projects/{id}/quote/approve` then `POST /payments/orders` | Order returns `payment_id`, `hold_cents`, `compute_max_cents`, `success_fee_max_cents`, `approve_url`. Mock returns `approvalUrl` pointing to its own fake page. |
| getAgreement | 6 pay | Reads the amount to show | `GET /projects/{id}` (`quote`) | Mock `target.maxUsd` dollars. Backend `quote.cap_cents`. There is no endpoint to get a payment by project id, only by `payment_id`. |
| authorizeHold | 6 pay | Confirms the hold, moves to training | `POST /payments/{payment_id}/authorize` | Returns `{held, state}`. Mock returns `nextChatId`. Then the frontend must call `POST /projects/{id}/train`. Mock does this in one step. |
| cancelHold | 6 pay | Cancel and go back | `POST /projects/{id}/cancel` | Returns `{payment_state, status}`. Only valid after the hold and before training. A cancel in the PayPal window before approval needs no call (nothing is held). |
| getChat training / research | 10 train | Live chart, ETA, stages | `GET /projects/{id}/training` | Backend gives `stage`, `fraction` (0 to 1), `elapsed_seconds`, `spend_so_far_cents`, `eta.low_seconds/high_seconds`. No live accuracy line, no research steps. Polling needed. |
| stopJob | Budget panel, Stop | Stops and voids the hold | `POST /projects/{id}/training/stop` (running) or `/cancel` (before run) | Mock says "hold voided". Truth: stop captures compute used so far, no fee, rest released. |
| getChat verified | 12 verified | Locked-test result and capture | `GET /projects/{id}/training` (`result.verification`) then `GET /payments/{id}` | Verification has `value`, `target`, `passed`. Capture shown from `compute_captured_cents`, `fee_captured_cents`, `released_cents`. |
| getChat missed | 13 missed | Target missed, hold voided, "pay $0" | Same as above | Mock text says "you pay $0". WRONG for our model: user pays compute, no fee. Must change (see LESSONS.md). |
| getChat result | 14 result and receipt | Result, try model, receipt | `GET /payments/{id}` for receipt | Receipt gives `hold_cents`, `compute_captured_cents`, `fee_captured_cents`, `released_cents`, `total_charged_cents`. Mock receipt is a list of text rows. |
| getChat ineligible | 28 not eligible | Reasons and 3 fixes | `GET /jobs/{id}/forecast` | Backend gives `eligible`, `reason`, `issues[]`, `suggested_target`, `min_confidence`. Mock options (sample, lower target, upgrade) are only partly real. "Upgrade plan" has no backend. |
| getChat round2 | 29 improve | Second round after a miss | `POST /chats/{id}/pilot` (reopens a missed project) | Backend: free pilot reopens at the pilot step. A new quote needs a new hold. Mock shows "hold voided, new hold". |
| getBudget | Top bar | Held / used headline per chat | NONE as such. Parts from `GET /payments/{id}` and training progress | Mock is a hardcoded text per chat name. Real value must be built from payment state. |
| getBudgetBreakdown | 11 budget panel | Split of hold into experiments and buffer | NONE | Backend has no experiments or buffer. Replace with compute max + success fee max (see section 4). |
| predictChurn | 14 try one record | Predict for one customer | NONE | Model is stored but there is no predict endpoint. Mock input is fixed to 3 churn fields. |
| predictBatch | 30 use model | Predict for an uploaded CSV | NONE | No endpoint. |
| getPublicResult | 27 share link | View-only result page | NONE | No share or public result endpoint. |

## 3. Things the frontend has that the backend does not have at all

Demo path: describe, data, readiness, baseline, pilot/forecast, quote, pay, train, result, receipt. Everything else is optional.

- Login, signup, forgot password, logout: not needed. Use one fixed demo user. Skip the login screens (hide or auto-sign-in).
- OAuth with Google and GitHub: not needed.
- API keys screens (Hugging Face, Kaggle, OpenRouter keys): not needed. Keys live in `.env`.
- Billing plans (Starter, Pro, Team), plan wizard, `payPlan`: not needed. Hide it. The "upgrade" option on the not-eligible screen goes too.
- Payment methods tab, card details, billing details: not needed. PayPal handles this.
- Usage screen and meters (`getUsage`): not needed. A simple spend line from the receipt is enough.
- Billing history list (`getBilling`): optional. Could later list payments.
- Projects list, rename, delete, project page with runs and versions: optional. One project per chat is enough for the video.
- Share dialog, invite members, public result link: optional. Nice-to-have only.
- Integrations (Kaggle, Hugging Face connect), `connectIntegration`, sync: not needed. The agent searches datasets itself.
- File upload, link detection, `addDatasets`, sample data button: needed in a simple form. Upload a CSV (`POST /projects/{id}/data`) is on the demo path. Link detection is optional.
- Model download, API snippet, "model use" screen 30: optional. Try-one-record is nice for the video.
- Delete model or version: not needed.
- Live view (agent browser) and research steps (screen 9): not needed. The backend has no browser tool.
- Live accuracy chart during training: optional. The backend only gives a progress fraction.
- Welcome / first-run screens, system states: optional, harmless to keep.

## 4. Mismatches to decide

1. Precision and recall vs accuracy. The mock uses "precision 80%, recall 60%" everywhere. The backend target is accuracy only ("X out of 100 right", 0 to 1). Recommended: change all UI to accuracy and drop recall and the tiers' recall field (also the spec forbids jargon).
2. Mock text "you pay $0 if missed". Wrong for our model. Recommended: replace with "you pay compute either way, the success fee only if verified" everywhere (screens 5, 6, 12, 13, 29, budget rule, usage rows).
3. Base URL. Mock comments say `/api/v1`, and one API snippet shows `api.aioac.app/v1`. Backend has no prefix (`/projects`, `/payments`). Done: the frontend setting is `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`, no prefix), read in `frontend/lib/config.ts`.
4. CORS. Still true on 2026-10-27: `backend/app/main.py` has no CORS middleware, so the browser would block calls from `localhost:3000`. Recommended: add a small CORS rule for the frontend address.
5. Ids. Frontend has chat id, job id, agreement id (`agr-...`). Backend has one project id. Recommended: one id everywhere; the agreement is just the quote of that project.
6. Money units. Frontend uses dollars as numbers (`maxUsd: 40`). Backend uses whole cents. Recommended: keep cents in the data, and convert to dollars only in one display helper.
7. Percent vs fraction. Frontend uses 80. Backend uses 0.8. Recommended: convert in one helper (times 100) at the edge.
8. Hold parts. The UI shows "Experiment 1, Experiment 2, Safety buffer" (`HoldPart`, `BudgetBreakdown`). Backend hold is compute max plus success fee max. Recommended: show two lines, "Compute (up to $X)" and "Success fee (up to $Y, only if verified)", plus "Released".
9. Max price chosen by the user. Mock lets the user type "max price $1 to $500". Backend sets the cap itself (max $7 per job today). Recommended: remove the field. Show the cap as a fact.
10. PayPal window. `paypal-window.tsx` is a fake popup with an "Authorize" button that calls `authorizeHold`. Recommended: on "Pay", call `POST /payments/orders`, then send the browser to `approve_url`. PayPal comes back to `/pay/return` (backend config already says `http://localhost:3000/pay/return` and `/pay/cancel`). The `/pay/return` page calls `POST /payments/{payment_id}/authorize`, waits for `held: true`, then calls `POST /projects/{id}/train` and opens the training screen. `/pay/cancel` shows "Nothing was held" and goes back to the quote. Keep `payment_id` in browser storage until the return, since PayPal's return link carries only its own token. The project id could also go in the return URL query. Never trust the return page alone: the server check is the proof.
11. Baseline and readiness have no direct endpoints. They happen inside the agent chat. Recommended: for the demo, drive them through `POST /projects/{id}/chat` and read the result from `GET /projects/{id}`. Add small direct endpoints later if the chat is too slow.
12. Messages and cards. The frontend expects a list of messages with `blocks`. The backend has a chat reply with `card`, no history. Recommended: add `GET /projects/{id}/messages` and let the screen choose its card from `project.status`.
13. Screens chosen by chat name. The frontend picks a screen from fake chat names. Recommended: choose the screen from `project.status` (described ... done, voided, stopped, failed).
14. Training result missing from "missed" vs "met". Backend has `result.verification.passed`. Recommended: use that one flag to pick screen 12 or 13.
15. Stop button wording. Mock "stopJob" says the hold is voided. Truth: compute used so far is captured, no fee. Recommended: say so in the confirm dialog.
16. Estimates. Backend marks quotes and forecasts with `is_estimate: true`. Recommended: show the word "estimate" next to every such number.
17. Our-failure case. The frontend has no screen for "our failure, whole hold voided, you pay $0" (status `voided` or `failed`). Recommended: add one simple screen, reusing the receipt.

## 5. Proposed small steps

1. Plumbing and first slice (create, data, baseline). Backend: add CORS only. Frontend: add `lib/api.ts` (fetch wrapper plus cents and percent helpers); switch `startChat` to `POST /projects` and the upload to `POST /projects/{id}/data`; show readiness and baseline from `GET /projects/{id}`. Test: backend runs, frontend creates a project from the home screen, you see a real grade and baseline. Add one automated test for the helpers.
2. Chat for real. Backend: add `GET /projects/{id}/messages`. Frontend: `sendMessage` calls `/chat`; render reply text and card; choose screen by `project.status`. Test: a scripted fake model run in the backend tests; one browser test.
3. Pilot and forecast, in accuracy. Frontend: replace precision/recall with one accuracy target field; call `POST /chats/{id}/pilot`; show confidence, band, and the "not eligible" screen from `eligible`, `reason`, `issues`, `suggested_target`. Backend: none. Test: a case that is eligible and one that is not (too few rows).
4. Quote screen. Frontend: replace the 3 tiers and max price field by one quote card from `POST /agreements/{id}/quote` (estimate, range, compute cap, success fee max, cap, terms text). Fix the "pay $0" copy. Backend: none. Test: quote numbers match the backend response in cents.
5. Real PayPal pay (sandbox, mock provider first). Frontend: delete the fake popup; add `/pay/return` and `/pay/cancel` pages; "Pay" calls `quote/approve` then `/payments/orders`, redirects to `approve_url`. Backend: maybe add `GET /projects/{id}/payment` to find `payment_id` after a reload. Test: full click-through on the mock provider; then once on the real sandbox (this is also the first real check of authorize, which is still open).
6. Train screen. Frontend: after `held: true` call `/train`; poll `GET /projects/{id}/training` every few seconds; show stage, bar, estimated spend, ETA range; Stop calls `/training/stop`. Remove the fake research steps and live chart. Test: local backend run end to end, then press Stop once.
7. Result and receipt. Frontend: screens 12/13/14 read `result.verification` and `GET /payments/{id}`; show held, compute captured, fee captured, released, total. Add the "our failure, you pay $0" state. Rewrite the missed screen copy. Backend: none. Test: three scenarios on the mock (verified, missed, our failure) with the exact amounts.
8. Optional extras, only if time is left. Try-one-record: backend `POST /projects/{id}/predict` and a download link; hide login, plans, keys, usage, sharing; Improve round (screen 29) with the existing reopen behaviour. Test: demo check plus one recorded run-through.

## 6. Questions for the founder

1. Do we change every screen to "accuracy" (X out of 100 right), or do you want a second number such as recall kept? The backend only supports accuracy now.
2. Should the user pick a maximum price, or is the cap always set by us (today up to $7)? We recommend we set it.
3. For the demo video, can we hide login, plans, keys, usage and sharing screens completely?
4. Do you want the "try the model on one customer" screen in the video? It needs one extra backend endpoint.
5. Is a one-time fake sign-in (a single demo user) acceptable for the video?
6. The wireframes show "Experiment 1/2" and a "safety buffer". Are you happy to replace them with "Compute" and "Success fee" lines?

## 7. Merge notes (2026-10-27)

Checked against `backend/app/routes/` (projects, payments, quotes, forecast, webhooks, health) and `main.py`. The frontend calls no backend endpoint yet, so there is no wrong call, only the gaps below.

- Endpoints the plan needs that exist now: `POST /projects`, `GET /projects/{id}`, `/chat`, `/data`, `/quote/approve`, `/train`, `/training`, `/training/stop`, `/cancel`, `/settle/retry`, `/trace`, `POST /payments/orders`, `POST /payments/{id}/authorize`, `GET /payments/{id}`, `POST /chats/{id}/pilot`, `GET /jobs/{id}/forecast`, `POST /agreements/{id}/quote`.
- Still missing in the backend: CORS, `GET /projects/{id}/messages`, any predict endpoint (one record or CSV), share or public result, `GET /projects/{id}/payment`, direct baseline and readiness endpoints.
- Mock-only features with no backend twin (hide before the demo): login and signup, API keys, plans and billing wizard, payment methods, usage, projects list, sharing, live view, research steps.
- Wording fixed on merge (rules 7 and 8): "you pay $0 if missed" became "you pay only the compute used, no success fee"; "guarantee" became "quote"; precision and recall labels became plain words ("right when flagged", "leavers caught"). Still to do: the data and types still use precision and recall (to become one accuracy number, section 4 item 1), and a few mock receipts for the missed case still show "$0" charged (`lib/mock-api.ts`). Estimates are not yet labelled "estimate" on every number (item 16).
- Removed on merge: the four `/dev/*` preview pages, their preview components and 3 screenshot tests (screens 18, 19, 32; screen 31 lost its preview test).
- Real mode: `NEXT_PUBLIC_USE_MOCK_API=false` makes every mock call fail with a clear message until the steps in section 5 are done.

## 8. Step 3 done: demo path wired (2026-11-04)

With `NEXT_PUBLIC_USE_MOCK_API=false` the demo path calls the real backend. With the default (`true`) every screen is unchanged mock data.

Wired (real mode):
- `/` (describe): `POST /projects`. `/c/{id}` is one page that picks its screen from `GET /projects/{id}` `status` (`lib/status.ts`, table in api.md B8). A reload at any step shows the right screen.
- Data: CSV upload (`POST /projects/{id}/data`) then choose the answer column (read from the CSV header) and `.../select`. Readiness and free test: `POST .../readiness`, `.../baseline`.
- Target (typed as "X out of 100 right", sent as 0 to 1): `POST /chats/{id}/pilot`. Not eligible shows `reason`, `issues`, and a one-click `suggested_target` retry. Eligible: `POST /agreements/{id}/quote`, shown with every figure marked estimate and the cap as a fact (no max-price field).
- Pay: `quote/approve` then `POST /payments/orders` then the browser goes to `approve_url`. `/pay/return` calls `POST /payments/{id}/authorize` (polls 5 times if `held:false`), then `POST /projects/{id}/train`, then `/c/{id}`. `/pay/cancel` says nothing was held. `payment_id` is kept in sessionStorage and recovered from `GET /projects/{id}/payment` (or the project list) if lost.
- Train: polls `GET .../training` (`not_started` is normal). Stop calls `.../training/stop` with the honest wording.
- Result and receipt: `result.verification.passed` picks "Target reached" or "Target not reached"; receipt from `GET /projects/{id}/payment`. Stopped, voided and failed states, with "our failure: you pay $0". A missed run offers a new free pilot (Improve).
- Login (2026-11-06): real mode no longer opens a demo session. `/login` and `/signup` call `/auth/login` and `/auth/signup`; `GET /auth/me` decides signed-in state (`lib/session.ts`, memory only); a 401 outside `/auth/*` clears the user and goes to `/login?next=<path>` (never from `/login` or `/signup`); the sidebar shows the email and Log out; per-user browser memory (`aioac.pay`, `aioac.lastProject`) is wiped when the user changes; optional 'Try the demo' with `NEXT_PUBLIC_DEMO_LOGIN=true`. Mock mode is unchanged. Forgot password and OAuth are mock-only.

Code: `lib/api.ts` (fetch client, `ApiError`), `lib/api-real.ts` (one function per endpoint), `lib/adapters.ts` (all unit conversions), `lib/status.ts`, `components/real/`. Tests: `npm run test:unit`.

Wired 2026-11-06 (F1): chat on the describe step (history, agent replies, dataset approval card, blocks; one `/chat` call per user action, no polling or auto-retry). Not wired (still mock): chat on later steps,  try-one-record, CSV predictions, model download, sharing, usage, keys, plans, forgot password (see breakpoints F rows). Paid steps were not run against real PayPal.

## 9. One polished UI on the real backend (COMPLETE 2026-11-06, steps 1 to 10 done; step 11 try-one-record also built, section 10)

Goal: keep ONE UI, the polished one (`components/shell`), driven only by the real backend. Plan only, no code changed yet. Read-only audit of the frontend on 2026-11-06.

Idea in one line: the polished screens are chat-first (`InlineChatFrame`, `AgentRow`, `UserBubble`, inline cards) and today a fake "chat name" picks the screen. We keep that look, but `ChatScreen` picks the screen from the project status (`lib/status.ts`, api.md B8) and each card is fed by a view model from `lib/adapters.ts` (cents, 0 to 1, one id), never by `lib/types.ts` mock shapes.

### 9.1 Inventory

Counts: 18 route pages (7 keep or rewire, 11 delete). 43 files in `components/shell` (3 keep as is, 19 rewire, 21 delete). `components/billing` (7 files), `components/real` (9 files, replaced step by step), `lib/mock-api.ts` (2115 lines) and `lib/billing-flow.ts` go.

Route pages (`frontend/app/`):

| Route file | Action | Note |
|---|---|---|
| `(auth)/login/page.tsx`, `(auth)/signup/page.tsx` | rewire | `auth-screen.tsx` loses mock branches, forgot password, OAuth buttons |
| `(app)/page.tsx` | rewire | `home-screen.tsx`: goal box, then create project; returning user sees last project |
| `(app)/c/[chatId]/page.tsx` | rewire | the whole demo path, one page, screen chosen by status |
| `(app)/pay/return/page.tsx`, `(app)/pay/cancel/page.tsx` | rewire | keep logic of `real/pay-return.tsx`, restyle in the shell |
| `(app)/projects/page.tsx` | rewire | `projects-screen.tsx` shows `GET /projects` only (no rename, delete, members) |
| `(app)/c/[chatId]/pay/page.tsx` | delete | fake PayPal popup route |
| `(app)/projects/[projectId]/page.tsx` | delete | runs and versions, no backend |
| `(app)/account/billing/page.tsx`, `(app)/account/usage/page.tsx` | delete | plans, usage, payment methods, billing history |
| `(app)/settings/keys/page.tsx` | delete | API keys |
| `(app)/welcome/page.tsx` | delete | first-run tour |
| `(flow)/billing/{plan,review,payment,done}/page.tsx`, `(flow)/layout.tsx` | delete | plan wizard (+ `components/billing/*`, `lib/billing-flow.ts`) |
| `(public)/s/[shareId]/page.tsx` | delete | share link (+ `public-result.tsx`) |

Shell files (`frontend/components/shell/`):

| Action | Files |
|---|---|
| keep as is | `inline-chat.tsx`, `composer.tsx`, `confirm-dialog.tsx` |
| rewire | `app-shell.tsx`, `sidebar.tsx` (replaces `real/real-sidebar.tsx`), `top-bar.tsx` (drop Share), `user-menu.tsx` (email + Log out only), `home-screen.tsx`, `auth-screen.tsx`, `chat-screen.tsx`, `projects-screen.tsx`, `baseline-chat.tsx`, `agreement-chat.tsx`, `ineligible-chat.tsx`, `training-chat.tsx`, `verified-chat.tsx`, `result-chat.tsx`, `round2-chat.tsx`, `budget-card.tsx`, `budget-panel.tsx`, `add-data-modal.tsx` (shrink to CSV upload; 686 lines of integrations go), `add-data-provider.tsx` |
| delete | `activity-chat`, `research-chat`, `live-view-tab`, `canvas-panel`, `canvas-files`, `canvas-progress`, `experiment-canvas`, `model-tab`, `chat-panel`, `tool-strip`, `trace-card`, `key-drawer`, `keys-screen`, `usage-screen`, `billing-screen`, `payment-methods-tab`, `share-dialog`, `public-result`, `paypal-window`, `first-run-screen`, `project-screen` |

Also delete the mock-only parts of `lib/types.ts` (Job, Step, ResearchRun, LiveView, Share*, Key*, Plan*, Billing*, Usage*, Tier*, ModelUse, BatchResult; most of the file) and `lib/hooks.ts` pieces only used by them. Delete `components/real/*` last (step 10).

### 9.2 Demo-path screens

Backend shapes are in api.md; "view" means a function in `lib/adapters.ts` (new ones marked +).

| Screen (status) | Reuse (polished) | Replaces (real/lib) | Endpoints | Adapter and prop mapping |
|---|---|---|---|---|
| Login, logout | `auth-screen`, `user-menu` | `real/real-sidebar` logout | `/auth/login`, `/auth/signup`, `/auth/logout`, `/auth/me` | already in `api-real.ts`; keep `?next` and demo button |
| Projects list | `projects-screen`, `sidebar` | `real/real-sidebar` | `GET /projects` | `{id, goal, status, created_at}` to `ProjectSummary{id,name=goal,subtitle=status label}`; +`statusLabel()` |
| Describe + chat + approval card (`described`) | `InlineChatFrame`, `AgentRow`, `UserBubble`, `Composer`, card style of `ineligible-chat` | `real/chat.tsx` (keep its logic, `lib/chat.ts`) | `GET /messages`, `POST /chat`, `POST /data`, `POST /data/{c}/select` | message `{role: assistant}` to `agent`; `card.args` shown as dataset box (name, source, rows, answer column) |
| Data + readiness (`data_chosen`) | `baseline-chat` ReadinessCard | `real/steps` ReadinessStep | `POST /readiness` | `BaselineRun.readiness{grade,title,detail,tag}` from `readiness.grade` + findings `[{kind,text}]` (OK/NOTE list, not one tag): +`readinessView` |
| Free test (`readiness_done`) | `baseline-chat` ResultCard, Metric, Bar | `real/steps` BaselineStep | `POST /baseline` | `result{precision,recall,targetPrecision}` to `{accuracy, simpleGuess}` as "X out of 100"; drop recall |
| Target + forecast (`baseline_done`) | `agreement-chat` AgreementCard (one target, no tiers) | `real/steps` TargetForm, ForecastCard | `POST /chats/{id}/pilot` | `toForecast`: confidence, band, `is_estimate`; tiers and `maxUsd` removed; `suggested_target` as one chip |
| Not eligible | `ineligible-chat` EligibilityCard | `real/steps` IneligibleStep | forecast in `GET /projects/{id}` | `IneligibleCheck` to `reason, issues[], suggested_target`; remove "upgrade plan" option |
| Quote + approve (`baseline_done` eligible, `quoted`) | `agreement-chat` PaySummary | `real/steps` QuoteStep | `POST /agreements/{id}/quote`, `quote/approve` | `toQuote`: estimate/low/high/cap/compute cap/fee max, each "estimate", cap as limit; `terms` text from server |
| Pay (`awaiting_payment`) | `agreement-chat` (hold lines), `budget-card` | `real/steps` PayStep, `paypal-window` | `POST /payments/orders`, redirect `approve_url` | hold parts to "Compute (up to)", "Success fee (up to, only if verified)", "Released" |
| `/pay/return`, `/pay/cancel` | `inline-chat` frame + `Button` | `real/pay-return.tsx` | `POST /payments/{id}/authorize` (poll), `POST /train`, `GET /projects/{id}/payment` | logic unchanged (`recoverPayment`); server check is the proof |
| Train + Stop (`training`) | `training-chat` ProgressBody, `confirm-dialog`, `budget-panel` | `real/steps-run` TrainingStep | `GET /training` (poll 3 s), `POST /training/stop` | `TrainingRun.eta{headline,detail,progress}` from stage, fraction, `eta.low/high`, spend "estimate"; drop LiveChartCard, series, tools; Stop text: compute used so far, no fee |
| Result verified or missed (`done`) | `verified-chat` VerificationCard, MoneyRecap, BestModelCard, Banner | `real/steps-run` ResultStep | `GET /training` `result.verification`, `GET /payments/{id}` | `VerifiedRun.metrics[0]{value,ruleLabel,met}` from `{value,target,passed}`; recap `held/charged/released` from receipt cents; missed copy "you paid compute only, no success fee" |
| Receipt | `result-chat` ReceiptTab | `real/steps-run` Receipt | `GET /projects/{id}/payment` | `ResultRun.receipt rows` from `toReceipt`; demo shows about 52 cents captured, rest released |
| Improve after miss | `round2-chat` (trim) | ResultStep "new pilot" | `POST /chats/{id}/pilot` | plan card text only; new hold needs a new quote |
| Voided, failed, stopped | `verified-chat` MoneyRecap + `AgentRow` | `real/steps-run` VoidedStep, StoppedStep | `GET /projects/{id}/payment`, `settle/retry` | "our failure, you pay $0" for voided/failed; stopped shows compute used, no fee |

Not in the demo path (delete): `PredictionCard` and `WaysCard` in `result-chat` unless step 11 is approved.

### 9.3 Mock mode: remove `USE_MOCK_API` entirely

- Remove it. Delete `lib/mock-api.ts` (2115 lines), `lib/billing-flow.ts`, the `?mock=` states and all `if (USE_MOCK_API)` branches (about 12 files). `lib/config.ts` keeps only `API_BASE_URL` and `DEMO_LOGIN`.
- Two code paths is what produced two UIs; a tiny mock would drift again, and the backend already has a scripted-model test double for offline work.
- Playwright: delete all 34 mock-based specs and `tests/shots` (the 9 stale "pay $0" specs go with them). Replace with a few real-mode specs run against the real FastAPI app with the scripted model (steps 5 to 9); `npm run test:unit` stays the fast gate.

### 9.4 Order of work

Each step ships alone and ends with typecheck, lint, `test:unit`, build; browser steps use a scratchpad-only script that starts the real FastAPI app with FakeLLM and the mock payment double (stripped env, no outside calls). Real Azure and real PayPal only with the owner's yes.

| # | Step | Size | Test |
|---|---|---|---|
| 1 | Backend: approval card names the dataset (9.5) | small | pytest unit + e2e card test; api.md updated |
| 2 | DONE 2026-11-06. Delete dead routes, screens, `components/billing`, nav entries (9.1) while mock still exists; fix imports | medium | typecheck, lint, build; grep finds no import of deleted files |
| 3 | DONE 2026-11-06 (see 9.7). Remove `USE_MOCK_API`, `mock-api.ts`, mock specs, shrink `types.ts`; auth-screen cleanup | large | typecheck, lint, unit, build; browser: login, signup, logout |
| 4 | DONE 2026-11-06. Shell on real data: `AppShell`, `Sidebar` (replaces `real-sidebar`), `TopBar`, `UserMenu`, projects list, home | medium | unit for `statusLabel`; browser: sign up, create project, see list |
| 5 | DONE 2026-11-06. `ChatScreen` picks by status; describe step in the polished thread (chat, card with dataset box, CSV upload) | medium | unit (card view); browser: "I have no data" with FakeLLM, approve card |
| 6 | DONE 2026-11-06. Readiness, free test, target, forecast, not eligible views | medium | adapter unit tests from real JSON; browser: eligible and ineligible paths |
| 7 | DONE 2026-11-06. Quote, pay, `/pay/return`, `/pay/cancel` | medium | unit for hold lines; browser on mock payment double: hold, return, train starts |
| 8 | DONE 2026-11-06. Train, Stop, budget card and panel | medium | unit for progress/ETA view; browser: progress, Stop |
| 9 | DONE 2026-11-06. Result (verified, missed), receipt, voided, failed, stopped, Improve | large | unit for money recap; browser: verified, missed, our failure with exact cents |
| 10 | DONE 2026-11-06. Delete `components/real/*`, write real-mode Playwright specs, update README and docs | medium | full frontend gate + backend `pytest` + demo check + secret scan |
| 11 | DONE 2026-11-06 (section 10). Try-one-record (`POST /projects/{id}/predict`) | medium | backend unit + one browser check |

### 9.7 State after steps 2 to 9 (2026-11-06)

- Routed (7 pages): `/login`, `/signup`, `/`, `/c/[chatId]`, `/projects`, `/pay/return`, `/pay/cancel`. Deleted earlier: mock routes, `components/billing`, `lib/mock-api.ts`, `USE_MOCK_API`.
- **Shell (step 4):** `shell/sidebar.tsx` (new project, `GET /projects` with `statusLabel()`, `UserMenu` with email and Log out; refreshes on route change and on the `aioac:projects-changed` event the project page fires when a status changes), `home-screen.tsx` (polished composer, creates the project, then `/c/{id}`), `projects-screen.tsx`, `composer.tsx` (attach only when a screen passes `onAttach`; no web-search button). `real-sidebar` and `real-home` deleted.
- **Project page (step 5):** `shell/chat-screen.tsx` loads the project, polls only while `isSettling`, and renders `InlineChatFrame` with the stepper, the persistent `ChatThread`, then `StepArea` (current step), and the `ChatComposer` pinned at the bottom, on EVERY status. Chat rules live in `lib/chat-controller.ts` (no React, unit tested): one `/chat` per user action, goal sent only for a `described` project with no history, no resend on reload, Approve only on click (`approve:[card.tool]`, no message), project re-read (GET) after every reply, 503 hides the input, 409 offers a GET-only Check again. `shell/chat-blocks.tsx`: blocks (readiness, baseline, quote, pay) and `ApprovalCard` (dataset box from `card.detail`). CSV upload is a secondary button on the describe step (`shell/data-upload.tsx`: `POST /data`, then `/select`).
- **Free steps (step 6):** `shell/step-cards.tsx` (dataset, data check with grade tile, free test with bars, forecast, not eligible with a one-click suggested target) and `shell/step-actions.tsx` (check, free test, target as "right out of 100"). `shell/step-area.tsx` picks them from `screenFor`. Deleted: `baseline-chat`, `ineligible-chat`, `real/chat`, `real/real-flow`, `add-data-provider`.
- Still in `components/real` (steps 7 to 9 replace them): `steps.tsx` (QuoteStep, PayStep), `steps-run.tsx` (paid, training, result, stopped, voided, unknown), `pay-return.tsx`. `step-parts.tsx` (Panel, Row, Stepper, useAction) moved to `shell/`.
- Not yet ported and still excluded from `tsconfig.json` and `eslint.config.mjs`: `agreement-chat`, `budget-card`, `budget-panel`, `result-chat`, `round2-chat`, `training-chat`, `verified-chat` (steps 7 to 9). They still import deleted pieces (`experiment-canvas`, `tool-strip`, `paypal-window`): drop those when porting. Unused legacy types remain in `lib/types.ts` (cleanup in step 10).
- Browser checked with `python -m tests.browser_server` (scripted model, mock payments) and Playwright on system Chrome: signup, goal, first reply, dataset card names the dataset, reload keeps the history with no second `/chat`, Approve, data check, free test, pilot (eligible and not eligible), quote, chat visible on every step.
- Playwright: config kept, `npm test` passes with no specs; real-mode specs are step 10.
- **Steps 7 to 9 (2026-11-06):** `components/real/` is gone and the old polished pieces `agreement-chat`, `budget-card`, `budget-panel`, `training-chat`, `verified-chat`, `result-chat`, `round2-chat` were deleted; `tsconfig.json` and `eslint.config.mjs` have no exclude lists any more. New in `components/shell/`: `quote-step.tsx` (quote card with the fixed terms text, "Approve and pay" = quote/approve, then POST /payments/orders, then the PayPal link; waiting-for-PayPal card with Open PayPal, Check my approval, Cancel with plain confirm = POST /cancel), `pay-return.tsx` (`/pay/return` and `/pay/cancel`), `training-step.tsx` (paid starter, progress, honest Stop confirm), `result-step.tsx` (verified or missed, money recap, receipt, settle retry button, stopped, voided or failed, Improve = free pilot). Pure logic with unit tests: `lib/pay-flow.ts` (authorize, poll, POST /train exactly once), `lib/training-poll.ts` (poll only while the project is `training`, `not_started` is normal, stop 409 text), `lib/result-view.ts` (verified vs missed from `verification.passed`, recap from receipt cents, recap note built from the real numbers, settle retry rule). `adapters.QUOTE_TERMS` is the fixed terms text. Void with no run behind it is shown as a cancel ("Nothing was charged"); with a run it is "Something went wrong on our side. You pay $0. The whole hold was released."
- Checked in the browser with `python -m tests.browser_server` (mock PayPal, local training) and system Chrome: signup, goal, approve dataset, data check, free test, target, quote, Approve and pay, mock return page, run, verified result and receipt (local training costs 0, so the recap says nothing was charged). Stop, missed, Improve, settle retry, stopped, failed and voided were checked with Playwright route interception using the JSON shapes of api.md. Not run against real PayPal or SageMaker (owner, F2).
- Step 10 (2026-11-06): `lib/types.ts` and the unused ui pieces (`badge`, `chip`, `status-icon`, `switch`), `usePersistedState`, `EmptyThread`, `getReceipt` and `public/images` were deleted; real-mode Playwright specs added (see below); README rewritten with Windows steps.


### 9.5 Backend changes

- **Approval card names the dataset (F9).** Today the card is `{what: "The agent wants to select dataset", level, tool, args}` (`services/gate.py` line 73, `services/agent/loop.py` line 267). Change: in `loop.py`, when the tool is `select_dataset`, build `card["detail"] = {name, source, rows, columns, license, target}` and a plain `what` ("Use the dataset <name> (<source>, <rows> rows) and predict <target>") from the candidate row, through a small helper in `services/agent/tools.py` that reads the candidate via the datasets repository. Add `detail` to `chat` and `messages` card JSON in `routes/projects.py` and to api.md A2. No gate logic change (level stays 1; approval stays a user click).
- Not needed: any other new endpoint for the demo path. `GET /projects` already has `status`; hold lines come from `quote` and `payment`.
- Small and optional: `GET /auth/me` answers 401 when signed out (console noise); either accept it or return `200 {user: null}` in `routes/auth.py` (changes the api.md C1 contract, owner to decide). Logout clears the cookie but the JWT stays valid until it expires (known, documented in api.md C1).

### 9.6 Risks and open questions for the owner

1. Delete the mock completely (recommended) and lose offline UI demos without the backend? Or keep a tiny mock? This plan assumes delete.
2. Playwright specs against the real app need a test-only backend launcher with FakeLLM. OK to commit that launcher (under `backend/tests/helpers`), or keep it scratchpad-only and run the browser checks by hand?
3. Try-one-record for the video (step 11): yes or no? It adds a backend endpoint and model loading.
4. Describe step: keep chat only there (buttons later), or chat on every step? Plan says buttons later, chat only on describe.
5. Risk: steps 7 to 9 are tested on the mock payment double only; the full browser cycle on the real PayPal sandbox and SageMaker is the owner's manual check (F2). Also `/auth/me` 401 choice (9.5).

## 10. Restored screens on real data (2026-11-06)

Owner request: bring back the polished screens deleted in steps 2 and 3, wherever a backend route now exists (`specs/api.md` section D). No mock code, no fake data. Pure logic is in `frontend/lib/screens.ts` (and `welcome.ts`, `nav.ts`) with unit tests on fixtures copied from real JSON (`frontend/unit/fixtures-screens.ts`, taken from the browser test server after a finished run).

| Route / piece | What it shows | Backend |
|---|---|---|
| `/projects/[projectId]` (`shell/project-detail.tsx`) | Goal, plain status, "Open chat". Tabs Overview, History, Activity, Model (`?tab=model` opens one). Projects list rows link here | `GET /projects/{id}`, `/history`, `/activity` |
| Model tab (`shell/model-tab.tsx`) | "Try it on one record" built from `columns` (select for `choices`, number input, example as placeholder, empty fields allowed), answer as "about N out of 100" with "an estimate, not a promise"; "Run it on a CSV" (file or paste, up to 5,000 rows, preview table, Download results CSV); "Download the model" with the scikit-learn version note; `usable=false` shows `unusable_reason` and keeps Download; `available=false` shows "No trained model yet". The result step links here when a model exists | `GET /model`, `POST /predict`, `/predict-batch`, `GET /model/download` |
| `/account/usage` | Projects, runs, compute charged, success fees, released, AI tokens (cost only if above zero, called an estimate), recent activity | `GET /account/usage` |
| `/account/billing` | Receipts table (goal, plain state, held, compute, fee, released, total, date), each row links to the project; empty state | `GET /account/payments` |
| Share button + dialog (`shell/share-dialog.tsx`, in the chat and project top bars) | Create link (copy), state, "Stop sharing" with confirm | `POST/GET/DELETE /projects/{id}/share` |
| `/s/[token]` (`app/s/`, outside the signed-in layout; `shell/public-result.tsx`) | Goal, data name and rows, answer column, free test, verified vs target as "X out of 100", estimate note, read-only badge, "Built with AIOAC"; 404 shows "This link is not available". `lib/api.ts` sends no cookies and never redirects to login for `/public/*` | `GET /public/results/{token}` |
| `/welcome` | Three plain steps and Start. Shown once after the first sign-up in this browser (`localStorage` flag in try/catch); never after login | none |
| Navigation | Sidebar and user menu: Projects, Usage, Billing history. No dead links | none |
| Improve form | Starts at the forecast's `suggested_target`, else the target already set (never the lower verified result) | none |

Browser check (test launcher, system Chrome): signup shows Welcome; a full run to a finished project; project detail tabs; one record, CSV and model download; Usage; Billing history; share link opened in a new browser context with no cookies renders without login and shows no money, email or payment text; after "Stop sharing" the same address shows "This link is not available". Not run against real PayPal, AWS or Azure.

Notes: the Activity feed comes from the agent's stored trace, so steps done with buttons (data check, free test) do not appear in it; only agent turns and gate decisions do. Local training charges $0, so the receipts show a full release.

Intentionally not restored (no backend, or not part of the product): plans and the upgrade wizard (`/billing/*`), payment methods, invoices and PDFs, API keys and the key snippet, integrations, the live view tab, the experiment chart, inviting people by email, model versions delete.

### Browser tests (2026-11-06)

`frontend/tests/*.spec.ts`, run by `npm run test:e2e`. `playwright.config.ts` starts two servers (reused if already up): the TEST launcher `backend/tests/browser_server.py` on port 8765 (scripted model, mock PayPal, local training, throwaway SQLite; it never reads real keys) and the frontend (`npm run build && npm run start -- -p 3100`, built with `NEXT_PUBLIC_API_BASE_URL=http://localhost:8765`). Specs: `auth` (sign up shows Welcome, log in does not, log out, redirect to /login), `demo-path` (goal to receipt), `project-pages` (tabs, activity feed from stored rows, one record, CSV, Usage, Billing history), `sharing` (public page with no cookies, revoke), `isolation` (user B gets "project not found"), `states` (Stop, stopped, missed, failed, cancelled via route interception with api.md JSON). Not covered: real PayPal, real model, real SageMaker.
