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
- **Agent (LLM, via Azure AI Foundry or OpenRouter):** a custom tool-calling loop that searches and previews datasets, explains readiness in plain words, runs the free test and pilot, builds the quote and explains results. The agent *proposes*; ordinary code *disposes*: a permission gate between the model and every tool that costs money or changes data checks stored state (approved quote, server-confirmed hold, cap) and the model cannot argue its way past it.
- **Guards:** schema-checked tool arguments, a code check that the target accuracy came from the user's own words, a reply guard that blocks false claims about payment or training, step/token/cost/time limits per turn, and untrusted-data wrapping for dataset text.
- **Evals:** an eval harness with 15 cases; the real model (gpt-5.4 on Azure) passed 22/22 runs with zero safety violations (small sample, not a guarantee).
- **Classic ML:** scikit-learn models (linear, forest, boosted trees) chosen by the free pilot; the same code runs locally and in the SageMaker training script.

## How we built it
Next.js (TypeScript) frontend, FastAPI backend, SQLite or Postgres. Strict layering (routes, services, repositories, integrations) enforced by an architecture test. Every outside system (PayPal, AWS, LLM, datasets, storage, jobs) sits behind an interface, with in-memory doubles used only in tests. Training runs on AWS SageMaker using AWS's scikit-learn image; the cap becomes SageMaker's `MaxRuntimeInSeconds`, so AWS itself ends the job at the cap even if our code is down. Terraform describes the bucket, roles and budget alert.

## Challenges
- Designing the money model: first "charge the cap, refund later", then "pay $0 if the target is missed" (rejected, the compute is real). We settled on **forecast, then verify**: hold the cap, always capture real compute, charge the fee only on a verified result, void the rest.
- Honest cost estimates from tiny samples; platform fee dominates small jobs.
- Real data traps: ID columns, numbers stored as text, columns that copy the answer (our baseline once scored 100% before we fixed it).
- A model trained under scikit-learn 1.4 crashed on 1.9 at predict time; we pinned the SageMaker image to 1.9.
- Making an LLM agent safe near money: most guards live in code, not in the prompt.

## What we learned
Put every irreversible step behind code that reads stored state. Idempotency keys and compare-and-swap status changes make retries safe. Small honest numbers ("about 8 out of 10, an estimate") build more trust than big promises.

## What's next
Run the full cycle in a browser against live PayPal sandbox plus SageMaker, verify the webhook with a public URL, calibrate prices from real jobs, multi-process rate limits, instance selection by data size.
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
