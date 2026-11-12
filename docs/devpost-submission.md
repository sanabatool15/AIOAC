# Devpost submission text (PayPal AI Hackathon)

Copy each block into the matching Devpost field. Items marked **YOU** need your own input. Everything else is taken from the repo specs and is honest about what was and was not run live.

---

## 1. Project overview

**Project name:** AIOaC (AI on a Click)

**Elevator pitch (under 200 characters):**

> Describe a prediction problem in plain words. An AI agent finds data, runs a free test, quotes a capped price, takes a PayPal hold, trains on AWS and captures only what was used.

---

## 2. Project details

### About the project (paste as Markdown)

```markdown
## Inspiration
Training a machine-learning model still needs an ML engineer, a cloud account and a lot of guessing about cost. People who just want an answer ("which customers will leave?") give up. We wanted it to feel like Gamma for presentations: you say what you want, an agent does the technical work, and you approve the few decisions that matter. The hard part is trust: nobody wants an AI agent near their wallet. So we made PayPal the safety rail.

## What it does
AIOaC takes a plain-language goal and walks one path from start to finish:

1. **Describe.** You state the goal. The agent asks one short question if needed.
2. **Data.** Upload a CSV, paste a dataset link, or say "I have no data" and the agent searches open datasets (hand-checked list, UCI, OpenML, Hugging Face) and explains the top three in plain words.
3. **Readiness.** A readiness grade with plain OK/NOTE findings (leaky columns, lopsided answers, too few rows).
4. **Free test, pilot and forecast.** A free baseline on held-out data, then a free pilot on 5-10% of the rows that forecasts the full-run result against *your* target, with a confidence. If we cannot honestly sell it, we say so ("Not eligible") and suggest a target we can.
5. **Quote.** One price: estimated compute plus a 5% success fee, a range, and a hard cap. Everything is labeled an estimate.
6. **Pay.** PayPal places a **hold** for the cap. Nothing is charged yet. The *server* confirms the hold with PayPal; a browser success screen is never proof.
7. **Train.** A capped job runs on AWS SageMaker with live progress and a Stop button.
8. **Result.** The model is checked **once** on locked test rows it never saw. The server then captures the actual compute, captures the success fee **only if the target was verified**, and **voids the rest** of the hold. If our own code fails, the whole hold is voided and you pay $0.
9. Try the model on one record, run a CSV, download it, share a read-only result link, or start a free "Improve" round.

Task types: classification, regression, forecasting, grouping and unusual-record detection (tabular data, scikit-learn).

## How we use PayPal
PayPal sandbox is the spending control of the product, not a checkout bolted on:
- **Orders v2 authorize** places a hold for the cap; the server confirms it before any paid work starts.
- **Payments v2 capture** (with `final_capture` and a `PayPal-Request-Id` on every call) takes the actual compute, then a *second* capture on the same hold takes the success fee only if the locked-test check passed.
- **Void** releases the unused remainder. Repeating any capture or void is harmless (idempotency keys).
- **Webhooks**: signature verified through PayPal's verify-webhook-signature API, events stored once, used as a cross-check only; a webhook can never create a hold or mark a project paid.
- An **append-only ledger** records every capture; the app refuses to capture above the hold or above the compute cap.

## How we use AI
AI does the work a person would otherwise need an ML engineer for, but it never holds the wallet.

**1. The agent (LLM through Azure AI Foundry or OpenRouter).** A custom tool-calling loop, small enough for us to test and trace ourselves. In plain words it:
- **Finds data.** When the user has no data, `discover_datasets` searches a hand-checked list of 12 datasets plus UCI, OpenML and Hugging Face side by side (about 5-10 s live), removes near-copies, ranks the results and explains the top three in one plain sentence each. It can also look at a dataset's size and columns before anything is downloaded.
- **Checks the data.** Readiness grade, plain OK/NOTE findings, a column-by-column profile with suspects (a column that copies the answer, row IDs, numbers stored as text), and a side-by-side comparison of model types with "which columns matter" clues.
- **Runs the free steps.** The free test on held-out rows, then the free pilot and forecast against the user's own target.
- **Explains.** The quote, the result ("verified 84 out of 100 right vs 70 for a simple guess"), and what could help after a miss. Numbers always come from code, never from the model's own claims.

**2. The agent proposes, the system disposes.** A permission gate (ordinary code) sits between the model and every tool. Level 0 tools are free and run on their own. Level 1 tools (choose a dataset, apply a data fix) need the user's click on an approval card. Level 2 tools (request payment, start training) need an approved, unexpired quote and a **server-confirmed PayPal hold**. The gate reads stored state, never what the model says happened, and logs every allow and refuse. If the user approves a card and the model replies with text only, the server runs the exact call stored on the card, so the model cannot talk its way out of or around an approval.

**3. Guards around the model.**
- Tool arguments are checked against each tool's schema (types, ranges, arrays) and bad calls go back to the model as errors.
- The target accuracy must come from the user's own words; otherwise `run_pilot` answers "ask the user" and the model cannot pick it.
- A reply guard replaces any final answer that claims a payment, training run or settlement the stored state does not support, or promises to run something when it has no tools.
- Limits per turn: 12 steps, 80,000 tokens, a 120 s deadline, 60 s per free tool, and a stop if the same call repeats more than 3 times. Limits per project: 600,000 tokens and a model-cost ceiling. When one is hit the user gets a plain message.
- Server-side gates for the data choice and for vague goals: search tools answer "wait" until the user's own words say they have no data, or name an actual outcome.
- Dataset titles, column names, sample rows and licenses are wrapped as untrusted data so a poisoned dataset cannot give the model instructions.

**4. Context engineering.** Each step the model sees a short rules prompt, a live state block rebuilt from the database (status, chosen dataset, grade, free test, quote, next step), only the tools that fit the current stage, and stored history inside a token budget. Eleven short skill playbooks (leakage, lopsided answers, too little data, a suspiciously good baseline, choosing the target column, explaining results plainly, and others) load on demand. Skills hold wording and judgment only; money rules live in code.

**5. Evaluation, not vibes.** An eval harness runs scripted and real models against fixed cases with a mock payment provider, local training and a throwaway database. It checks that no paid work ran, no false claims, plain language, no accuracy promise, tool order and limits. With `gpt-5.4` on Azure: 22 of 22 runs passed on 11 dataset and flow cases and 12 of 12 on 4 skill cases built on synthetic files (lopsided, 80 rows, exact copy, near copy of the answer), with zero safety violations. The smaller `gpt-5.4-mini` passed 15 of 22 on the same scoring, which is why the guards are in code and not in the prompt. Rewriting skill descriptions to say exactly when to load them cut unneeded skill loads from 12 of 12 runs to 0 of 12. These are small samples, not a guarantee.

**6. Classic ML that is honest.** scikit-learn only, on tabular data: classification, regression, forecasting, grouping and unusual records. The free pilot tries linear, forest and boosted-tree models on 5-10% of the rows, drops weak ones early, and fits a learning curve to forecast the full-run result with a band and a confidence. Below 0.60 confidence, or with too little data, we do not sell the run. The paid run trains the model type the quote pinned, then scores it once on locked test rows it never saw. The same feature and model code is copied verbatim into the SageMaker training script, so local and cloud cannot drift apart.

**7. Small extra AI uses.** One cached, validated LLM call turns column names like `Attribute1` into plain labels ("Checking account status") on the Model tab; a failure just shows the raw names.

## How we built it
**Stack.** Next.js (TypeScript) frontend; FastAPI (Python) backend; SQLite for the demo and Postgres-compatible (Supabase) for real use; scikit-learn; AWS SageMaker and S3; PayPal REST sandbox; Azure AI Foundry or OpenRouter for the agent.

**Architecture.** The dependency direction is fixed: routes, then services, then repositories and integrations, then database and interfaces. Services contain no SQL; only repositories touch the database. Every outside system (PayPal, AWS, LLM, dataset sources, storage, job runner, local training) has its own folder behind an interface in `ports.py`, and one factory builds each from config. In-memory stand-ins (mock PayPal, scripted model, offline datasets) live in `doubles/` and are used only by tests; the app has no mock mode. An architecture test fails the build if a service imports SQLAlchemy or the app imports a double.

**The money path.** A project moves through fixed states (`described`, `data_chosen`, `readiness_done`, `baseline_done`, `quoted`, `awaiting_payment`, `paid`, `training`, `done`, plus `failed`, `stopped`, `voided`) and steps cannot be skipped. `paid` is set only after the server asks PayPal to authorize the order and checks the amount. Settlement saves each step (compute capture, fee capture or skip, void of the rest) before the next, so it can resume after a crash or PayPal outage without moving money twice. The ledger is insert-only and refuses a balance below zero. Every capture and void carries an idempotency key, and webhook events are stored once by event id.

**Training.** `POST /train` returns at once; the job runs in the background (a thread by default, Inngest optional). Progress, spend so far and an ETA range are shown in plain words, and Stop captures the compute used so far with no success fee. Three layers prevent a duplicate paid run (event id, an atomic "claimed" timestamp, and a SageMaker job named after the run so AWS itself refuses a second one). On start-up, orphaned runs are failed and their holds voided. On SageMaker the quote's cap becomes `MaxRuntimeInSeconds` (minus a 120 s grace and a safety margin), so AWS stops the job at the cap even if our server is down. Actual cost is billable seconds times the hourly price, never above the cap. Plain boto3, AWS's own scikit-learn image and our script: no custom Docker image.

**Product extras.** Email and password login with one organization per signup and owner-scoped routes (404, never 403, for someone else's project), a live activity feed, model versions, "Try a higher target" and free "Improve" rounds, guided data fixes (limit 3, forecast shown before and after), try-one-record, CSV predictions, model download, usage and billing history, and a public read-only result link.

**Testing.** Hundreds of offline backend tests (unit, contract on mocked HTTP and boto3, end-to-end on doubles), frontend unit tests, and Playwright browser tests against a test launcher. A demo check (`tests/e2e/test_payments_and_demo.py`) runs the whole flow with no network. Live checks (`RUN_REAL=1`) are separate; paid ones need a second switch (`RUN_PAID=1`) so a normal run can never start a paid job. Terraform for the bucket, roles and budget alert is written in the repo.

## Challenges
- **The money model took three tries.** First "charge the cap, then refund the unused part". Then "pay $0 if the target is missed", which we rejected: the compute is real and someone pays for it. We landed on **forecast, then verify**: hold the cap, always capture the real compute, capture a 5% success fee only if the result passes a check on locked data, and void the rest. If our own code fails, the whole hold is voided.
- **Payment edge cases.** An audit found races and stuck states: a hold confirmed but the project never moved to paid, a late authorize after a cancel that nothing would void, an amount mismatch that left a hold at PayPal, two simultaneous requests hitting a unique key. Each got a small reviewed fix and a test on the mock provider (atomic status updates, void first then transition, refuse and void a late authorize).
- **Real PayPal sandbox behavior.** Early credentials were rejected. Once working, we proved authorize, a repeated authorize, a partial capture, a second capture on the same hold, repeated capture and void with the same request id, void of the remainder, and a refused capture after the void. Webhook signatures, many captures per hold and hold lifetime are still unchecked.
- **Honest cost estimates.** Timing small samples and extrapolating is shaky: at 4,800 rows we projected 2.3 s and measured 2.1 s, but at 20,000 rows we projected 3.0 s and measured 5.8 s, because the baseline timed 100 trees while the cloud script used 300. We fixed the timing to use the chosen model type. The platform fee still dominates small quotes, and prices are placeholders until more real jobs are measured (one real job: cap 60 cents, 69 billable seconds, real AWS compute about 0.44 cents).
- **Messy real data.** A customer-ID column was one-hot encoded and hurt the model; numbers stored as text; and a column that exactly copied the answer made the baseline score 100% while readiness said it would be ignored. We fixed leakage detection and added skills and checks for near copies.
- **A silent version bug.** A model trained on scikit-learn 1.4 loaded on 1.9 with a warning and then crashed at predict time. The app runs Python 3.13, which 1.4 does not support, so we pinned the SageMaker image to 1.9 and added a test that loads and predicts in the app environment.
- **Making an LLM safe near money.** A real model chose the target accuracy itself and ran pilot and quote in one turn; it asked for approval twice instead of acting; vague goals triggered searches; it used jargon like "pilot" and "cap". The fixes live in code (target guard, forced approved call, clarity and data-choice gates, plain wording rules), not in prompt pleading.
- **Wiring a polished UI to real data.** We had two UIs (a fake-data one and a plain real one) and merged them into one, with chat position, live steps and approval cards that name the dataset instead of an id.

## What we learned
- Put every irreversible step behind code that reads stored state, and let the model only propose. A prompt is advice; a gate is a guarantee.
- Idempotency keys, compare-and-swap status changes and "save each step before the next" make retries and crashes boring.
- The cap should be enforced by the party that bills you (AWS's maximum runtime), with our timer only as a backstop.
- Small honest numbers ("about 8 out of 10, an estimate", a confidence, "no success fee if missed") build more trust than big promises, and the free steps are what make users willing to pay.
- Evaluate agents on real models with repeats; a smaller model that looks fine in one run fails the same cases a stronger one passes.
- Sandbox-first PayPal development is practical: authorize, capture and void map cleanly onto "hold, charge actual, release the rest".

## What's next
- Run the complete flow in a browser against the live PayPal sandbox and SageMaker together, with a person approving as the sandbox buyer.
- Verify webhook signatures against a public URL, and check PayPal's limits on captures per authorization and hold lifetime.
- Calibrate prices and the speed factor from more real jobs so quotes stop being dominated by the platform fee.
- Run paid SageMaker jobs for the newer task types (regression, forecasting, grouping, unusual records).
- Choose the instance size from the data, and a possible GPU path.
- A shared rate limiter for multi-process deployment, scheduled cleanup of expired candidates and leftover cloud resources, password reset and team invites.
```

### Built with (tags, max 25)

`python`, `fastapi`, `next.js`, `typescript`, `react`, `paypal`, `paypal-orders-api`, `paypal-payments-api`, `paypal-webhooks`, `aws-sagemaker`, `amazon-s3`, `terraform`, `scikit-learn`, `azure-ai-foundry`, `openrouter`, `llm-agents`, `sqlalchemy`, `sqlite`, `postgresql`, `playwright`, `pytest`, `hugging-face`, `inngest`

### "Try it out" links

- Code: https://github.com/sanabatool15/AIOAC
- (Optional, **YOU**) your YouTube demo link in the video field. No hosted demo exists; the app runs locally (see section 3, testing instructions).

### Image gallery (suggested screenshots, JPG/PNG, 3:2)

1. Describe screen with the chat and the three data choices
2. Readiness grade with OK/NOTE findings
3. Forecast card ("an estimated N% chance of reaching X out of 100", labeled estimate)
4. Quote card with range, cap and the PayPal hold explanation
5. Training screen with progress, spend so far and Stop
6. Result: forecast vs verified result, and the receipt (held / captured / released)
7. Model tab: try one record, CSV, download
8. Architecture diagram: agent -> permission gate -> PayPal hold -> SageMaker -> capture + void

### Video demo (YouTube, under 3 minutes, public or unlisted)

Suggested script: 0:00 problem (15 s) / 0:15 describe goal, agent finds data (30 s) / 0:45 readiness, free test, forecast (30 s) / 1:15 quote + PayPal sandbox hold approval (30 s) / 1:45 training + capture, fee, void on the receipt (40 s) / 2:25 try the model + the "our failure costs $0" guarantee (25 s) / 2:50 close. **YOU** must record and upload it.

---

## 3. Additional info

| Field | Answer |
|---|---|
| Submitter Type | **YOU** (Individual / Team / Organization) |
| Country of residence | **YOU** |
| Canadian province | N/A (unless you reside in Canada) |
| Organization name | N/A |
| New or existing? | **New** (work started late Oct 2026, after the Oct 1 start; the repo's first commit is 2026-11-06 in the current history, **YOU** confirm before choosing) |
| If existed before | N/A |
| Additional sponsor tools | None, used other AI tools. (Postman, Render, APIMatic, etc. were not used; do not select them.) |
| Public repo URL | https://github.com/sanabatool15/AIOAC (MIT license, README with setup and sandbox instructions) |
| Demo URL | Leave empty (runs locally) |
| Age / jurisdiction / not an employee checkboxes | **YOU** |

### Explain how your project meets the main technology requirement

```
PayPal developer platform (free sandbox only, no real money):
- Orders v2 authorize: creates and authorizes a hold for the job's spending cap. The server confirms the hold with PayPal before any paid work starts.
- Payments v2 capture: captures the actual compute cost, then a second capture on the same authorization for a 5% success fee only if the model passes a check on locked test data. Every capture and void carries a PayPal-Request-Id so repeats cannot move money twice.
- Payments v2 void: releases the unused part of the hold; our own failures void the whole hold ($0 for the user).
- Webhooks + verify-webhook-signature: used as a signed cross-check; webhooks can never create a hold or mark a job paid.
- An append-only ledger and idempotent settlement sit on top. Checked live on the sandbox: authorize, partial capture, second capture, void of the remainder, repeat safety.

AI tools:
- LLM (gpt-5.4 on Azure AI Foundry; OpenRouter also supported): a tool-calling agent that finds and previews datasets, explains data readiness, runs a free test and pilot, builds the quote and explains results in plain language. A code-level permission gate stops it from spending money or starting paid work without an approved quote and a server-confirmed PayPal hold.
- scikit-learn: the models (free local baseline and paid job).
- AWS SageMaker: the paid training job, capped by the quote.
```

### PayPal experience

- **Rating:** **YOU** choose. A fair suggestion from this work is **7**.
- **Why / feedback (edit to match your real experience):**

```
The Orders v2 authorize + Payments v2 capture/void model fit our "hold the cap, capture only what was used" idea very well, and idempotency via PayPal-Request-Id on capture and void made retries safe. Checking endpoints and fields against the published OpenAPI schemas worked, and the sandbox accepted partial capture, a second capture on the same authorization and void of the remainder. Pain points: the sandbox buyer approval step cannot be automated, so live tests need a person; early sandbox credentials were rejected before we sorted out the app setup; we could not find authorization-related webhook event names in the schema, so webhooks are only a cross-check; limits on captures per authorization and hold lifetime are not clearly documented. We have not yet verified webhook signatures against a public URL.
```

- **Open to contact:** **YOU** (Yes/No).

### AI tools used

```
Claude Code (Claude) for pair-programming, specs, tests and code review; Azure AI Foundry (gpt-5.4) and OpenRouter as the runtime agent model; scikit-learn for the models; the PayPal and AWS MCP/plugin documentation tools for checking API details.
```

### Learning level

**Significant** (suggested). Learned PayPal authorize/capture/void, SageMaker cost caps, agent safety design, honest cost forecasting.

### Did you gain AI value for your career?

**Yes**

---

## 4. Sandbox testing instructions for judges (put in the "testing instructions" box)

```
No hosted demo; run locally (full steps in README.md).
1. Backend: cd backend && pip install -e '.[dev]' ; copy .env.example to .env, set SECRET_KEY (32+ random chars), LLM key, and PayPal SANDBOX client id/secret; uvicorn app.main:app --reload
2. Frontend: cd frontend && npm install && npm run dev (http://localhost:3000)
3. Offline checks, no keys needed: cd backend && pytest tests/e2e/test_payments_and_demo.py (full flow on the mock payment double); cd frontend && npm run test:e2e (browser tests on a scripted model and mock PayPal).
4. With sandbox keys, approve the hold using a PayPal sandbox buyer account from developer.paypal.com. Never use real cards or passwords.
```

---

## 5. Honest caveats (do not overclaim in the video or text)

- Full browser cycle with **real** PayPal sandbox **and** SageMaker together has not been run (F2 in `specs/breakpoints.md`); PayPal lifecycle and a real capped SageMaker job were each verified separately.
- PayPal webhook signature verification is tested on mocked HTTP only.
- Prices in `services/cost/prices.py` are placeholders (quotes about 53 cents with a platform fee that dominates).
- Eval pass rates are from small samples (2-3 repeats).
- Training with the new task types (regression, forecast, grouping, unusual) has not run on SageMaker.
