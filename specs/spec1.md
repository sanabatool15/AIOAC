# AIOAC (AI on a Click): System Specification

Status: draft 1. High-level design, not a rulebook. Detailed specs live in the files listed in section 9.

## 1. Vision

Anyone can describe a prediction problem in plain words and get a working, trained model without knowing anything about machine learning or cloud infrastructure. The product feels like Gamma for presentations: you say what you want, an agent does the technical work, and you approve the few decisions that matter.

### What makes it different

AutoML products and AWS SageMaker Canvas can already train models. They are broad tools with many screens and technical choices. AIOAC is narrow on purpose:

- **One path, start to finish.** Describe, bring data, check readiness, get a price, pay, train, use the result. No technical choices are shown to the user.
- **The agent finds and prepares the data.** It searches for suitable open datasets, previews them, and explains what it found in plain language.
- **The agent estimates and controls cost.** It quotes a price before any money is spent, enforces a hard spending cap, and releases the part of the PayPal hold that was not used. Nothing else in this space does that visibly.

The hard problems, and where most engineering and testing time goes, are: finding and storing the right data, producing honest insights about it, and producing a cost estimate that holds up.

## 2. Scope and priorities

### 2.1 Hackathon reality

The PayPal AI Hackathon is judged largely on the demo video. Judges may never run the code. Therefore:

1. **The demo path must work end to end, for real.** A smooth three-minute video of a real flow beats a perfect architecture.
2. **MVP over polish.** Where a shortcut does not change what the demo shows, take it.
3. **Run instructions, not deployment.** The repository must be easy to run from a README. We do not need to host it publicly.
4. **Security and multi-tenancy are deferred.** Login, organizations and per-tenant checks are straightforward to add later and are not where the project is judged. The data model leaves room for them (see db.md) but nothing enforces them yet.

### 2.2 What matters most

| Priority | Area | Why |
|---|---|---|
| 1 | Agent core: tools, skills, permissions | This is the product |
| 2 | Cost estimation and spend control | The unique idea |
| 3 | Dataset search, storage, insights | Largest source of failure in testing |
| 4 | PayPal hold, capture, void, webhook cross-check | Required by the hackathon |
| 5 | Training infrastructure (Terraform, SageMaker) | Needed for the paid step |
| 6 | UI | Follows the wireframes, kept simple |
| 7 | Login, multi-tenancy | Deferred |

### 2.3 Not building

Image, text or audio models. Model hosting beyond download and a simple "try it" form. Teams and roles. Real money of any kind: everything runs in PayPal sandbox only.

## 3. User journey

The wireframes (Figma file "AIOAC") define the core steps below plus a few extra screens (receipt, not eligible, improve round). The crowdfunding stretch was removed.

1. **Describe.** The user states the goal in plain words. The agent asks a short follow-up question if needed and fills in a plan card: goal, type of task, data needed.
2. **Bring data.** The user uploads a CSV or picks a free open dataset the agent suggested. A short preview is shown.
3. **Readiness.** The agent inspects the data and returns a readiness grade, a few plain-language findings (OK or NOTE), and a "how much to trust this" level.
4. **Free test, pilot, forecast and quote.** The agent runs a free baseline on held-out data and reports it as "about 8 out of 10 predictions were right". It then runs a free pilot on about 5-10% of the data and forecasts the full-run result against the user's target, with a confidence (an estimate, not a promise). If confidence is too low the run is not sold ("Not eligible"). Otherwise it quotes one price: estimated compute plus a small success fee (5% of compute), a range, and a hard cap.
5. **Pay.** The user approves and PayPal places a hold for the cap. Nothing is charged yet. The server confirms the hold before anything paid begins.
6. **Train.** A capped training job runs. Progress and spending are shown in plain language. The user can stop it and pays the compute used so far, with no success fee.
7. **Result.** The model is checked once on locked test data. The user sees the forecast and the verified result side by side, the final cost, the trust level, and can try the model on one record, upload a CSV or download it. If the target was missed, the user paid compute only and no success fee, and a free "Improve" round is offered. A receipt shows what was held, captured and released.

Language rule for all screens: plain words only. No F1, no train/test split, no instance names.

## 4. System overview

Six parts, each with one clear job:

- **Web app.** Shows the seven steps and the chat with the agent. Thin: it displays state and sends user decisions.
- **API server.** Owns all state. It is the only place that decides a job's status changes, and the only place that trusts PayPal.
- **Agent.** A tool-calling loop driven by an LLM through OpenRouter. It plans, calls tools, and writes plain-language explanations. It cannot spend money or change a job's paid status by itself.
- **Permission gate.** A piece of ordinary code between the agent and every tool that costs money or changes state. The model cannot argue its way past it. See agent.md.
- **Data and model store.** Object storage for candidate datasets (temporary), the chosen dataset (kept) and trained models.
- **Training backend.** Two implementations of one interface: a local free baseline and a paid SageMaker job.

Payments sit beside this: a payment provider interface with a PayPal sandbox implementation and a mock for tests, plus a webhook receiver and an append-only ledger.

### Principle: the agent proposes, the system disposes

The agent decides *what* to try. Anything with consequences (spending, starting paid work, deleting data, changing a job's status) is executed by the system after a check the model cannot influence.

## 5. Job lifecycle

A project moves through these states, in order. Each move is recorded.

`described`, `data_chosen`, `readiness_done`, `baseline_done`, `quoted`, `awaiting_payment`, `paid`, `training`, `done`.

Side exits: `failed`, `stopped`, `voided` (our failure or a cancel: the whole hold is voided and the user pays $0).

`paid` is set only after the server confirms the PayPal hold. A success screen in the browser is never proof.

## 6. Key design decisions

| Decision | Choice | Reason |
|---|---|---|
| Agent runtime | Custom tool-calling loop on OpenRouter | Fewest dependencies, we control the permission gate, easy to test |
| First paid job | CPU, scikit-learn, on SageMaker | Fits the $160 AWS budget and the wireframe quote |
| Payment model | "Forecast, then verify": PayPal hold for the cap, capture actual compute always, success fee only if verified on locked test data, void the rest (decided 2026-10-26) | The user pays for compute either way; our own failure costs $0; the hold means nothing is charged before the work is done |
| Storage | Temporary candidates, one permanent chosen dataset | Controls cost and keeps data tidy |
| Infrastructure | Terraform for long-lived pieces; training jobs started by the app | A training job is a runtime action, not permanent infrastructure |
| Database | SQLite for the demo, Postgres-compatible schema | Simple to run from a README |

## 7. Budget constraints

The AWS account has about $160. Every design choice that touches AWS assumes this. The policy (per-job cap, global ceiling, reserve for testing) is in cost.md.

## 8. Risks and open questions

1. **Demo job duration.** The wireframe shows "about 2 hrs" for a small dataset, which is unrealistic for 4,812 rows. We need a demo task that genuinely takes 10 to 15 minutes on CPU, or the quote must reflect real small numbers. Decide before the video.
2. **Charge the cap or the estimate.** Resolved (2026-10-26): a hold is placed for the cap, but only the actual compute (plus the success fee if verified) is captured. The rest is voided.
3. **Dataset search reliability.** Open dataset search can return unsuitable results. The mitigation is testing, plus a short curated fallback list.
4. **PayPal sandbox credentials do not work yet.** The provider is written and tested on mocked HTTP. It has not run against the real sandbox, because the credentials supplied so far were rejected.
5. **Estimate accuracy.** Unknown until measured. The estimator ships with an error log so we can see how wrong it is.

## 9. Specification files

| File | Covers |
|---|---|
| spec1.md | This overview |
| agent.md | Agent loop, tools, skills, permissions, limits |
| cost.md | Cost estimation formula, quotes, caps, budget guard |
| data.md | Dataset search, candidate storage, insights, readiness |
| training.md | Training backend, Terraform, SageMaker, teardown |
| payments.md | PayPal hold, capture and void flow, ledger, webhooks |
| db.md | Database schema |
| testing.md | Test strategy and demo check |

Rules and low-level conventions are kept in the repo rule files (`CLAUDE.md`, `.claude/rules/`), not here.
