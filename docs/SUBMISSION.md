# AIOAC (AI on a Click): Devpost Submission

Hackathon: PayPal AI Hackathon, "Build What's Next with PayPal and AI". Rules and honesty notes: `specs/hackathon.md`. Everything here is sandbox only. No real money, cards or PayPal passwords.

Copy sections 1 to 10 into the Devpost form. Section 11 is the video script. Section 12 is the screenshot list.

---

## 1. Tagline

Describe a prediction problem in plain words. An AI agent finds the data, tests it for free, quotes a price, and PayPal holds the money. You only pay for the compute actually used.

## 2. The problem

Training a useful model needs an ML engineer, cloud know-how, and trust that the bill will not surprise you. AutoML products exist, but they show many screens and technical choices, and they bill by the hour with no hard guarantee of what you will owe. A small business owner who wants to know "which customers may stop buying?" gets stuck at step one.

## 3. What AIOAC does

One path, start to finish, in plain words:

1. **Describe.** Say what you want to predict. The agent asks one short question if the goal is vague.
2. **Bring data.** Upload a CSV, paste a link (Hugging Face, UCI or OpenML), or say "I have no data" and the agent finds and ranks open datasets.
3. **Readiness.** A grade, plain findings (OK or NOTE) and a trust level. Row-ID columns, numbers stored as text and columns that give the answer away are found and handled.
4. **Free test.** A small model is trained and tested on data it has not seen: "about 8 out of 10 predictions were right", next to what a simple guess would score.
5. **Free pilot and forecast.** On 5 to 10 percent of the data, a learning curve forecasts the full run against the user's own target, with a confidence. This is labelled an estimate. If confidence is too low, the run is not sold and the agent explains why and offers a guided data fix.
6. **Quote.** One price: estimated compute plus a small success fee (5 percent of compute), a range, and a hard cap.
7. **Pay.** PayPal places a hold for the cap. Nothing is charged. The server confirms the hold itself.
8. **Train.** A capped job runs on AWS SageMaker. Progress and spend are shown in plain language. The user can press Stop.
9. **Result.** The model is checked once on locked test rows it never saw. The user sees forecast and verified result side by side, plus a receipt of what was held, charged and released. The user can try the model on one record, run a CSV, download it, or share a read-only link.

If the target is missed, the user paid compute only (no success fee) and gets a free "Improve" round. If a target is reached, the user can try a higher one.

## 4. How PayPal is used (central to the project)

PayPal is the trust layer. The product promise, "you can never be charged more than you approved, and you only pay for what ran", is enforced by PayPal's authorize, capture and void flow.

| Step | PayPal call (REST, sandbox) | Why |
|---|---|---|
| Create hold order | Orders v2, intent `AUTHORIZE`, amount = the cap | The cap is the most the user can ever pay |
| Buyer approves | PayPal checkout approval by a sandbox buyer | The user consents to the cap |
| Server confirms hold | Orders v2 authorize, server side, amount checked | A browser success screen is never proof. Paid training starts only after the server sees the hold |
| Capture compute | Payments v2 capture of the actual compute, never above the compute cap, `final_capture` false | Pay only for what ran |
| Capture success fee | A second capture on the same authorization, only if the locked-test check passed | The user pays the fee only for a verified result |
| Void the rest | Payments v2 void of the remaining authorization | Unused hold is released, not charged |
| Our own failure | Void everything | The user pays $0 if our code or infrastructure fails |

Safety properties, each covered by tests:

- Every capture and void carries a `PayPal-Request-Id`, so repeating one moves no money twice.
- The ledger is append-only. Webhook events are stored by id, so a repeated event can never charge twice.
- A capture above the hold, or after a void, is refused.
- The provider refuses any host except the PayPal sandbox.
- Webhook signature verification uses PayPal's verify-webhook-signature API, and the raw body is sent byte for byte. A webhook can never create a hold or mark a project paid.
- Settlement steps are saved one at a time, so a crash or PayPal outage can be retried without moving money twice (`POST /projects/{id}/settle/retry`).

What has really run against the PayPal sandbox (2026-11-02): authorize into a hold, repeated authorize returns the same authorization, a 20 cent compute capture, a 5 cent fee capture on the same hold, repeated capture with the same request id returns the first capture, void of the remaining 25 cents, repeated void is harmless, and a capture after the void is refused. The webhook has not run live yet.

Code: `backend/app/integrations/paypal/provider.py`, `backend/app/services/payments.py`, spec `specs/payments.md`.

## 5. How AI is used

- **An agent** runs on a hosted model (Azure AI Foundry or OpenRouter) in a custom tool-calling loop. It talks in plain words, finds and ranks datasets, inspects them, explains findings, and proposes what to do next.
- **The agent proposes, the system disposes.** A permission gate, ordinary code, sits between the agent and every tool that changes data or costs money. It checks stored state, never what the model says. The agent cannot spend money, start paid training, or change a job's paid status.
- **Numbers come from code, not the model.** Readiness, the free test, the pilot, the forecast, the price and the final check are computed with scikit-learn. The model chooses what to try and words the result.
- **Safety guards on the model:** the target accuracy must come from the user's own words; unsupported claims about payments or training are replaced with a correction; every tool argument is schema-checked; step, token, cost and time limits end a runaway turn; dataset text is wrapped as untrusted data.
- **Evaluated on a real model.** An eval harness (`backend/evals/`) ran 11 cases twice each on `gpt-5.4` (Azure): 22 of 22 runs passed, 0 safety violations (2026-10-31). Two repeats per case is a small sample, so this is evidence, not a guarantee.

Spec: `specs/agent.md`.

## 6. Architecture

```
Browser (Next.js)  ->  FastAPI  ->  services  ->  repositories -> SQLite / Postgres
                                         |
                       integrations: PayPal (sandbox) | AWS SageMaker + S3 | LLM | datasets | storage
```

Dependency rule: routes -> services -> repositories / integrations. Services have no SQL. Every outside system sits behind an interface in `ports.py`. The app has no mock mode; test doubles live in `backend/doubles/` and `app/` never imports them (enforced by a test).

Job lifecycle: `described, data_chosen, readiness_done, baseline_done, quoted, awaiting_payment, paid, training, done`, with side exits `failed`, `stopped`, `voided`. `paid` is set only after the server confirms the PayPal hold.

Spend control, four layers: the quote cap, a hold equal to that cap, AWS's own `MaxRuntimeInSeconds` derived from the cap (so the stop does not depend on our code running), and a global budget guard.

## 7. Training on AWS

A SageMaker training job runs AWS's own scikit-learn image plus our script (plain boto3, no custom Docker image). The cap becomes the job's maximum runtime. Real jobs ran 2026-10-30 and 2026-11-01: cap 60 cents, 69 billable seconds, accuracy 0.82 against 0.69 for a simple guess, real AWS compute about 0.4 cents. The same code builds features locally and on SageMaker, so the model cannot drift between the free test and the paid run. Infrastructure as code is in `infra/terraform/` (not applied from CI).

## 8. Testing and proof

- About 500 offline backend tests (497 passed on 2026-11-06) in `unit/`, `contract/` and `e2e/`, including the demo check `tests/e2e/test_payments_and_demo.py`.
- Browser tests: 6+ Playwright specs against a test launcher with a scripted model and mock PayPal.
- Safety checks that must always pass: no paid action without an approved, unexpired quote; training never starts before a server-confirmed hold; repeated capture or void moves no money; the success fee is never captured unless verification passed; actual cost never exceeds the cap.
- Live tests (`RUN_REAL=1`): PayPal sandbox hold lifecycle, AWS, SageMaker (second switch `RUN_PAID=1`), LLM, database, datasets.

## 9. Challenges, lessons, and what is next

**Challenges.** Honest cost estimation (the platform fee dominates a tiny job); preventing a model from deciding the target or claiming a payment happened; a scikit-learn version mismatch that made a SageMaker model crash on load (fixed by pinning 1.9); a leaked-answer column that produced a fake 100 percent baseline (fixed).

**Design lesson.** "Pay $0 if the target is missed" is not sellable, because compute is a real cost. The final model is "forecast, then verify": the user pays compute either way, the success fee only if verified, and our own failure costs $0 (`LESSONS.md`).

**Known limits (say them plainly).** Tabular data, classification as the shipped path (other task types are in progress); datasets up to 50,000 rows; one CPU instance; the full browser cycle with real PayPal sandbox plus real SageMaker has not been run end to end; the PayPal webhook and the Inngest runner are unverified live; estimates are estimates.

**Next.** Webhook live check; instance choice from data size; funding stretch; password reset and shared rate limiting.

## 10. Built with

Python, FastAPI, SQLAlchemy, SQLite and Postgres (Supabase), scikit-learn, Next.js, TypeScript, Playwright, **PayPal REST API (Orders v2, Payments v2, Webhooks, sandbox)**, **AWS SageMaker and S3**, Terraform, **Azure AI Foundry and OpenRouter** (agent model), Hugging Face, UCI and OpenML dataset APIs, Claude Code (development).

## 11. Demo video script (under 3:00, aim for 2:40)

Record on the real UI with the demo user. Say "PayPal sandbox" once on screen. Keep every line in plain words.

| Time | On screen | Say |
|---|---|---|
| 0:00 to 0:15 | Home screen, type the goal | "I run a small shop. I want to know which customers may stop buying. I have no data and no ML skills." |
| 0:15 to 0:45 | Agent finds datasets, approval card to pick one | "The agent searches open datasets, ranks them, and asks me to approve one. It cannot choose for me." |
| 0:45 to 1:10 | Readiness card, free test result | "It checks the data and runs a free test: about 8 out of 10 right, against 7 for a simple guess. Estimates, not promises." |
| 1:10 to 1:35 | Target, forecast, quote card | "I set my target. The forecast says an estimated chance of reaching it. One price, with a hard cap." |
| 1:35 to 2:00 | Approve, PayPal sandbox approval, hold confirmed | "PayPal places a hold for the cap. Nothing is charged. Our server asks PayPal to confirm before any paid work starts." |
| 2:00 to 2:20 | Training screen with progress and Stop | "Training runs on AWS with the cap enforced by AWS itself. I can stop any time." |
| 2:20 to 2:50 | Result and receipt: held, charged, released | "The model is checked once on rows it never saw. PayPal captures only the compute used, the fee only if it passed, and voids the rest. If we fail, you pay zero." |
| 2:50 to 3:00 | Title card with repo URL | "AIOAC. Plain words in, a trained model out, and you can never overpay." |

Tip: run with `TRAINING_BACKEND=sagemaker` so the receipt shows a real captured amount (about 52 cents). With `local` the compute is $0 and the receipt looks empty (breakpoint D2).

## 12. Screenshots to add

Take at 1440 px wide desktop, light theme, with the sandbox demo account. Blur or avoid any email address. Upload in this order; the first image is the Devpost thumbnail.

| # | Screenshot | Where in the app | Why judges care |
|---|---|---|---|
| 1 | **Receipt: held, compute charged, fee, released** (cover image) | Result step `/c/[id]` or `/account/billing` | The unique idea in one picture |
| 2 | **Price quote card** with estimate, range, cap and "estimate" labels | Quote step `/c/[id]` | Shows honest cost control |
| 3 | **Approval card** from the agent (choose dataset) | Chat on `/c/[id]` | Shows "agent proposes, you approve" |
| 4 | **PayPal sandbox approval page** (buyer approving the hold). Crop out any account name | Redirect from "Approve and pay" | Proves real PayPal use |
| 5 | **Pay return screen** "hold confirmed by the server" | `/pay/return` | Shows server-side confirmation |
| 6 | **Forecast and target card** (and the Not-eligible card as an optional extra) | Target step `/c/[id]` | Shows forecast before spend |
| 7 | **Readiness card** with grade and OK/NOTE findings | Readiness step `/c/[id]` | Shows data insight in plain words |
| 8 | **Training in progress** with spend so far and Stop button | Training step `/c/[id]` | Shows capped, live job |
| 9 | **Verified result** (forecast next to verified score) | Result step `/c/[id]` | Shows forecast, then verify |
| 10 | **Model tab**: try one record, versions | `/projects/[id]?tab=Model` | Shows the product is usable |
| 11 | **Sandbox dashboard transactions** showing the captured and voided amounts for that order. Hide the account id | developer.paypal.com sandbox | Independent proof that numbers match the receipt |
| 12 | **Architecture diagram** (section 6 redrawn) | Figma or any tool | Technical implementation score |
| 13 | **Terminal: demo check and tests green** (`pytest tests/e2e/test_payments_and_demo.py`) | Terminal | Shows engineering quality |
| 14 | **GitHub About box** showing "MIT license" | GitHub repo page | A listed submission requirement |

Optional: the public share page `/s/<token>`, and the AWS console SageMaker training job page (hide the account id). Skip any screenshot that shows keys, tokens, emails or the `.env` file.

## 13. Before you press Submit

1. Open the Devpost Rules tab and confirm the cutoff time and required fields (our fetch was blocked, see `specs/hackathon.md` section 1).
2. Do one run on a clean clone following only the README.
3. Check the repo has no secrets (`git log -p` search for keys; rotate anything that ever leaked).
4. Make the YouTube video public (not unlisted if the rules say public) and paste the link.
5. Re-read sections 4 and 9 and delete any claim you cannot show on video.
