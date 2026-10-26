# Frontend Integration Plan

Status: draft, 2026-10-26. This file only describes. No code was changed. Read it to see what we have, what is missing, and what we must decide.

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
3. Base URL. Mock comments say `/api/v1`, and one API snippet shows `api.aioac.app/v1`. Backend has no prefix (`/projects`, `/payments`). Recommended: no prefix, and add one `NEXT_PUBLIC_API_URL` setting in the frontend.
4. CORS. The backend has no CORS setting, so the browser would block calls from `localhost:3000`. Recommended: add a small CORS rule for the frontend address.
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
