# Agent as a Data Scientist (plan, not built)

Status: written 2026-11-09 from a read-only review (4 sub-agent passes plus direct greps). **Built so far (2026-11-09): Phases 1, 2, 3, 4 and 5** (4 without `restart_project`; see below), plus the data fix (`propose_data_fix`/`apply_data_fix`), family and quote pinning. Not built: Phase 0 measurement, Phase 6 onward. The rest of this file was the plan. Where this file says "verify", the claim was read from code or specs by a reviewer but not run.

## 1. Problem

The steps work (describe, data, readiness, free test, forecast, quote, pay, train, result). But the conversation feels scripted and "deterministic", not like a data scientist talking to a non-technical person. Also the product only does yes/no and few-category prediction; "hi" starts a dataset search.

Root causes (verified in code unless marked):

1. **Information starved.** `run_readiness` returns only `{grade, findings}` (`services/agent/tools.py:270-272`). `insights.analyze` computes `measurements` (rows, missing %, duplicates, minority share, constant/leaky/ID/text-number columns, `insights.py:67-71`) and the model never sees them. NOTE texts give counts, not column names (`insights.py:40-64`). `run_pilot` hides the model race, learning curve and rungs (`tools.py:293-297`; stored at `pilot.py:134-135`). `run_baseline` returns only accuracy and simple-guess accuracy; rare-class recall is never computed (`baseline.py`).
2. **No power to act.** No tool profiles columns or changes data. `datasets.clean()` (`datasets.py:58`) has no caller. Cleaning is silent in `features.prepare_features`. Skills say "you have no tool" (`data-leakage.md`, `lopsided-classes.md`).
3. **Fixed conveyor.** Tools by status: `described` discovery/fetch/select tools; `data_chosen` only `run_readiness`; `readiness_done` only `run_baseline`; `baseline_done`/`quoted` `run_pilot`, `create_quote`; `done/failed/stopped/voided` only `load_skill` (`context.py:79-97`). `NEXT_STEP` gives one-line commands (`context.py:62-76`). Lifecycle is forward-only.
4. **Scripted style.** `BASE` prompt (`context.py:11-27`, 1363 chars) is mostly prohibitions, has no persona. `explaining-results-plainly.md` caps replies at "three or four sentences". Every skill ends in "tell the user".
5. **Thin memory.** `state_block` (`context.py:107-135`) has no findings, no column names, no decisions. Tool results are kept in `messages` and shrunk to stubs only past 30,000 tokens (`memory.py:176-206`), so the model can remember within a conversation, but findings carry no column names to remember.
6. **Chat disappears.** `breakpoints.md` F1 says chat exists only on the describe step and is not shown after data is chosen (verify in `frontend/`).
7. **Greeting starts a search (user-reported, not reproduced).** `clarity.py` requires 2 content words, but only runs when the model calls a search tool. There is no greeting or small-talk path.
8. **ML scope is classification only.** Only classifiers exist (`baseline.py:10-12,40`; `pilot.py:16-18,53-55`); score is accuracy. No regression, clustering, anomaly, time-series. `BASE` tells the agent to refuse number prediction.

## 2. Hard rules that do NOT change

Everything in `CLAUDE.md`: no paid work before server-confirmed capture, sandbox only, no secrets, append-only ledger, hard spend caps, no accuracy promises, estimates labelled, plain language, target accuracy chosen by the user (`target.py`).
HUMAN REVIEW items are marked below. Keep those diffs tiny.

## 3. Phases

Each phase is its own small task: tests first, run `pytest` and the demo check (`pytest tests/e2e/test_payments_and_demo.py`) before calling it done.

### Phase 0: Measure first (no code risk)
- Run the real model (`python -m evals.run --model <deployment> --repeats 3`; costs tokens, ask the owner first) and READ the replies (`python -m evals.show`). No saved transcripts exist today.
- Loosen eval checks in `evals/run.py`: `JARGON` (line ~44) false-fails everyday "precision"/"gradient" and misses "leakage", "feature", "class imbalance"; `PROMISE` (~46-52) false-fails "you will reach 70% on the rows I tested" and misses "it will get 9 out of 10 right"; `asked_a_question` only checks `"?"` in the first reply.
- Add a tone eval (`evals/tone_cases/*.json`) with 8 cases: churn 78 vs 73; loan default 90 vs 88 lopsided; house price (a number, unsupported today); 80-row dataset; 3% fraud; leaky column; near coin flip 53 vs 52; "why is it only 70%?". Each has must-contain / must-not-contain. LLM-judge rubric, 1-5 each: plain words, structure (finding, meaning, recommendation), honest uncertainty, warmth, insight (a good domain question and the WHY). Pass: mean >= 4, none below 3, judge at temperature 0 with the tool state included, 3 repeats, plus a hand-rated gold set of 8 replies.
- Acceptance: baseline scores recorded in `specs/integration-testing.md`.

### Phase 1: Show the model what the code already knows (S, low risk)
- `run_readiness` and `inspect_candidate` also return `measurements` and the column NAMES for ignored, constant, leaky and text-number columns.
- `insights.py` NOTE sentences name the columns. Keep finding shape `{kind, text}` (used by `blocks.py`, `activity.py`, the readiness screen).
- `run_pilot` also returns plain winning model (`pilot.PLAIN_NAMES`), dropped models, learning curve in out-of-100, rows used. `run_baseline` also returns train/test row counts and rare-group catch rate (add recall for the smallest class to `baseline.py` when classes are lopsided).
- Wrap dataset-derived text with `context.mark(...)` (injection rule). Keep results small: `compact()` cuts at 2500 chars and only trims top-level lists, so a big dict is cut mid-JSON. Add `memory.stub_for` entries.
- Extra keys do not break `blocks.py` or tests (reviewer found no exact-equality assertions; confirm by running the suite).

### Phase 2: Persona, reply shape, state, skills (S, low risk)
- Rewrite `BASE` with a persona and reply shape; compress prohibitions; resolve "never round" vs "about N out of 100" (restate clean numbers in everyday words, never invent). Suggested text:
  - Persona: "You are a friendly senior data scientist helping someone who has never built a model. Look at the data first, say what you found and why it matters in one or two plain sentences, recommend one next step with the reason, then ask at most one question. Use everyday comparisons. Say 'I think' or 'probably' when you infer, and 'I checked' only for what a tool measured."
  - Reply shape: "1) what I looked at, 2) what I found and what it means for you, 3) my recommendation and why, 4) one question or the next step. Bad news: say it kindly and offer a way forward."
- Prompt budget: the 4000-char limit covers BASE + state block + skill index (`tests/unit/test_context.py:23`, `test_agent_fixes.py:81`). Measure headroom first; put detail in skills.
- Allow one short list of 3-5 items (renderer supports `-` lists, bold; no tables, `frontend/lib/markdown.ts`). Update the "no markdown" prompt line.
- Greeting rule: if the message is a greeting or has no goal, greet, ask what they want to predict, call no search tool.
- `state_block`: add `Known about the data:` (rows, balance in plain words, ignored column names), `Decisions so far:`, `Open question you asked:` (from `analysis_repo.latest_insight_report`).
- `NEXT_STEP` for `readiness_done` / `baseline_done`: "explain what you found in 2-3 plain sentences with one recommendation, then run the next test".
- New skills (each < 60 lines, no money words, "Use when" description; see `test_context.py:48-62`): `ask-like-an-analyst` (what decision, when is each column known, who is one row; ask one, state the assumption, move on), `why-accuracy-is-low-and-what-helps` (flat curve = weak columns, rising curve = more rows help, all near the simple guess = maybe not answerable), `reading-a-forecast`, `improve-after-miss`. Rewrite `explaining-results-plainly.md` (remove the 3-4 sentence cap) and `data-insights.md`. Add new skills to `evals/run.py` `SITUATION_SKILLS`.
- Acceptance: tone eval from Phase 0 improves; all existing evals still show 0 safety violations.

### Phase 3: `profile_data` tool (M, low risk)
- Level 0, reuse `Action.ANALYZE`. New pure function `services/data/profile.py` (per-column kind, missing %, distinct, top values, ranges, date-like, near-leaky via single-column predictiveness, target balance in plain words, `suspects[]` with reasons). Max 8 columns per call; small output.
- Offer from `data_chosen` through `quoted`; add to `TOOLS_BY_STATUS`, `NEXT_STEP`, `services/activity.py` (fixed sentence + `TRACE_STEP`), unit tests, one e2e case.
- Chat must stay usable at these statuses (see Phase 5).

### Phase 4: Chat on every step, small-talk and Q&A anywhere (M) - BUILT 2026-11-09 except `restart_project`
Built: the F1 limitation was already gone on `/c/[chatId]`; the project page gets a collapsed chat panel; `pendingCard` allows the data-fix card; read-only `explain_result` at `done`/`stopped`/`failed` (not `voided`); `profile` and `result` chat blocks (`specs/api.md` A2); the claim guard also blocks "I will retrain/train/redo". **Deferred for human review: `restart_project`** (needs lifecycle and gate changes). Not built: the "before/after" and "what seems to drive the answer" blocks.

- Frontend: show the chat after data is chosen and at later steps (verify the F1 limitation first). Agent answers questions at any status using free tools only.
- Backend: offer `profile_data` and read-only explain tools at all statuses; add `explain_result` and `restart_project` (both listed as "Build now" and unbuilt in `specs/agent/03-tools-reference.md`), so the agent works at `done`, `failed`, `stopped`, `voided`.
- New chat blocks (built by code from tool results, never from model text): "what I found" card, "what seems to drive the answer" (labelled clues, not causes), before/after card, fix approval card.

### Phase 5: Honest model comparison - BUILT 2026-11-09
- Status: the forecast/model mismatch is fixed (`services/data/families.py` is the one pipeline factory; quotes pin the family; the paid run trains the pinned family). `compare_models` is built: `services/data/compare.py` (pure), `services/compare_models.py` (reads the work file and the stored forecast's learning curve; never opens the locked file), tool `compare_models` (level 0, `Action.ANALYZE`, offered at `baseline_done` and `quoted` only, 12 s budget, plain 'still working' error past the tool deadline, result under 1,800 characters), `clues` chat block and card. Remaining: not measured with a real model; clues use a 25% hold-out of at most 5,000 work rows, so they are rough for small data.
- Original plan (kept as record):
- Open finding: the pilot forecasts for its winning model (logistic/forest/boosting) but the paid run and local run always train the random forest from `baseline._pipeline` (`train_script/train.py:33,50`). So the forecast may describe a model that is not the one trained. Either (a) make the pilot forecast the random forest only, or (b) train the pilot winner (changes `baseline.py`, which ships verbatim to SageMaker, cost samples, 300-tree vs 100-tree timing gap in `integration-testing.md`). Decide, document in `training.md` and `payments.md`, then proceed.
- Then add `compare_models` (free): models side by side in plain names, rare-group catch rate, effect of more data (from the learning curve), top clues (permutation importance on held-out rows, labelled as clues). Reuse `pilot._model` / `pilot._score`.

### Phase 6: Money-adjacent checks (HUMAN REVIEW, tiny diffs, tests first)
- **Verify defect:** after a missed run the payment state is `released` or `fee_skipped`; `create_quote` allows a new quote only when the old state is in `{none, voided, expired, declined}` (`services/cost/quotes.py:31-32`; `payments.py` TERMINAL includes `released`). The Improve round may therefore fail at the quote step. `tests/e2e/test_forecast_flow.py:60-68` stops after the pilot. First step: write a failing test, do not fix until reviewed.
- **Narrow the claim guard** (`services/agent/guards.py:12-21`, used at `loop.py:204-211`): it blocks honest wording such as "I've trained a quick model", "the model is ready", and replaces it with "Nothing was charged or started by me". Restrict to paid vocabulary (charged, payment, hold, paid training), or have skills use "test run"/"check". Keep gate decisions untouched.
- Forecasts store no dataset version; `create_quote` takes the latest forecast and baseline without checking they match the chosen version (`quotes.py:34-40`). Record `dataset_version_id` (nullable column; `python -m app.db.init --upgrade`) and refuse a stale quote.

### Phase 7: Data fixes and an agent-led improvement loop (L, HUMAN REVIEW)
- Tools: `propose_fix` (L0, shows rows before/after and the plain effect) and `apply_fix` (L1, approval card). Allow-listed deterministic operations only: drop column, drop duplicates, fill missing, group rare categories, drop rows with no answer, class weights. No model-written code.
- Gate: new `Action.APPLY_FIX` at level 1 (`gate.py:86-104`; `authorize` raises KeyError for an action missing from `LEVEL`, line ~140). Card detail branch in `loop.py` (~272), approved-call replay (`loop.py:200`), frontend card (`lib/chat.ts`).
- Service: generalise `datasets.clean()`; add a repo function to set `chosen_dataset_version_id` (`repositories/datasets.py:39` is the only setter). Fixes make a NEW dataset version (never edit the original).
- Must refuse at `awaiting_payment`, `paid`, `training`; must invalidate the forecast and quote; prefer drop/fill (not derived columns) so "Try the model" and predict-batch inputs stay valid.
- Locked split is keyed by version id (`verification.py`); a new version gets a new split. Fine if the fix happens before the quote, but before/after scores then use different hold-out rows. Report both on identical row ids, or use fixes that keep row ids.
- Lifecycle: add a re-check path (readiness and baseline re-run after a fix; services update `project.readiness_grade`/`baseline_result` without transition; routes return 409 "already done"). Keep changes to `lifecycle.py` tiny.
- Improvement loop: persist the diagnosis (table or JSON on the project: findings, fix applied, before/after), show it in the state block. Use fresh pilot seeds (pilot seed 0 repeats today). A full loop is ~7 sequential calls, so expect 2-3 turns (12-step limit counts model calls; repeat guard ends the turn on the 4th identical call, `loop.py:25,233-237`: consider including a changing argument or counting guard by data version).
- Update `data-leakage.md` and `lopsided-classes.md` once these tools exist.

### Phase 8: More ML task types (L, separate design first)
Decision needed from the owner before any code. Candidates in order of value:
1. **Number prediction (regression).** New regressor family, plain score ("typically off by about X", "explains N out of 100 of the ups and downs"), a different simple guess (the average), a different target (an error you accept, not accuracy), and a changed verification check. Touches pilot, forecast, locked test, SageMaker script, cost samples, and the meaning of the success fee. Payment-adjacent: HUMAN REVIEW.
2. Better scoring for lopsided classes (catch rate), partly done in Phase 1.
3. Time-based forecasting (own path, own honest limits).
4. Grouping / unusual-record detection (no accuracy to promise; different result screens; no success fee).
5. Text, images, audio: out of scope (`spec1.md` 2.3).
First, add a task-type decision step: the agent works out whether the goal is yes/no, a number, grouping or forecasting, and tells the user plainly what it can and cannot do today. Replace the "refuse numbers" prompt line with that behaviour.

## 4. Order and risk

| Order | Phase | Effort | Risk |
|---|---|---|---|
| 1 | 0 measure | S | none (needs owner yes for real-model tokens) |
| 2 | 1 surface data | S | low |
| 3 | 2 persona, state, skills | S | low |
| 4 | 3 `profile_data` | M | low |
| 5 | 4 chat everywhere, explain/restart, new blocks | M | low-medium |
| 6 | 5 forecast/model decision, `compare_models` | M | payment-adjacent |
| 7 | 6 money checks | S each | HUMAN REVIEW |
| 8 | 7 data fixes, improvement loop | L | HUMAN REVIEW |
| 9 | 8 new ML types | L | separate design |

Phases 1-4 give most of the change in feel without touching payments.

## 5. Spec drift to fix on the way

`specs/agent.md` / `status.md` still say 11 tools and "last 20 messages"; the code has `discover_datasets` and token-budget memory. `agent.md` 3.2 describes sandboxed model-written analysis scripts that do not exist. `CLEAN` action exists in the gate at L0 but no tool uses it. `agent.md` and a code comment (`context.py` ~111) say tool results are not kept between turns; they are kept until stubbed.

## 6. Caveats

- Tone gains are expected, not measured. Do Phase 0 first and re-run after each phase.
- Items marked "verify" were read from code or specs, not run: the "hi" behaviour, chat hidden after data is chosen, the quote-after-Improve defect.
- Real-model runs cost tokens; ask the owner before running them.

## 7. Prompt for a fresh session

> Read `CLAUDE.md`, `specs/status.md` and `specs/agent-data-scientist.md`. Do ONE phase at a time, starting with Phase 0 (ask me before any real-model run). Tests first; run `pytest` and the demo check before saying a task is done; keep diffs small; explain every change in payment/gate/lifecycle code for human review. Do not change `target.py` or the permission gate except as the spec says. Stop after each phase and show me what changed.
