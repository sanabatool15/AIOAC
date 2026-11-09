# Regression and other task types: design

Status: design only, 2026-11-09. Nothing here is built. Items marked (inferred) were not read in code or run. Line numbers are approximate. Payment, gate, verification and quote work is HUMAN REVIEW (CLAUDE.md). Continues Phase 6 and Phase 8 of `specs/agent-data-scientist.md`.

## 0. Headline

Regression is not realistic safely before the 2026-11-12 12:00 PT deadline (internal target 11-11; two working days). It crosses the pilot, forecast, locked-test check, SageMaker script, UI and the success-fee rule, and it has never run on real AWS. For the demo ship only: the honest "we do not predict numbers yet, here is the nearest yes/no reframe" behaviour (section 3) and the narrowed claim guard (section 4). Build regression after the hackathon, behind a `task_type` column, in the slices of section 2.

## 1. Task types: value, effort, risk

Common to all: `Project.task_type` already exists, nullable and unused (`db/tables.py:53`). `Forecast.metric` exists too (stored as "accuracy", `pilot.py` `save`). Today everything assumes accuracy: `baseline.py` (`accuracy_score`, mode guess), `pilot._score`, `forecast.extrapolate` (binomial finite-test term `p*(1-p)/locked_rows`), `verification.verify_model` (`accuracy_score`), `training.py` ~158 (`passed = value >= target`), `train_script/train.py` (`accuracy_score`, stratified `_split`), `target.py` ("N out of 100"), `model_use.py` (`accuracy`, `predict_proba` already optional), `compare.py` (permutation scoring="accuracy"), `insights.trust_level` (accuracy lift), UI `outOf100` in `result-step.tsx` ~135, `model-tab.tsx` ~165.

| Rank | Type | Value | Effort | Risk | Why |
|---|---|---|---|---|---|
| 1 | Better scoring for lopsided classes | High | S | Low | Still classification. `rare_group_caught` exists (`baseline.py`). Mostly a score and wording change. |
| 2 | Number prediction (regression) | High | L | Medium | Most-asked goal (prices, sales). Needs a new score, guess, target, verification. |
| 3 | Grouping / unusual records | Medium | M | High | No right answer to verify, so no honest target and no success fee. A different product (compute-only). |
| 4 | Time-based forecasting | Medium-high | L | High | Needs time-ordered split. A shuffled locked set leaks the future and fakes the result. |

### 1.1 Lopsided classes (catch rate)
- Ask: "find the few customers who will leave". Score: "caught N of 100 of the rare ones". Guess: 0 caught (always say the common answer).
- Target: "catch at least N out of 100 of them" (recall of the smallest group); `target.py` regexes still apply, only the sentence changes.
- Pilot/forecast: same maths on recall. Recall on a rare class is noisy, so the finite-test term must use the rare-group count (inferred: `locked_rows * share`), not all rows.
- Verification/fee: `verify_model` returns recall of the smallest group; `passed` unchanged. Quote/cap/cost unchanged. SageMaker script: add the same metric to `metrics.json`; `baseline.py` ships verbatim, so one change.
- Model tab: unchanged. UI: swap "right" for "caught". Tests: new golden numbers for lopsided cases; classification goldens must stay.

### 1.2 Regression (detail in section 2)
- Ask: "what price will this house sell for". Plain score: "typically off by about $X" plus "explains N out of 100 of the ups and downs".
- Simple guess: always predict the average (error = typical spread). Target: see 2.2. Pilot/forecast: learning curve on the score, with a continuous-score noise term instead of the binomial one.
- Verification/fee: score the model once on the locked rows; the same `passed = value >= target` if the score is higher-is-better (R-squared is).
- Quote/cap: unchanged shape; only timings differ. SageMaker: regressor families, non-stratified split, new metrics. Predict: no probabilities (already optional) and a number result. Tests: new fixtures (numeric target), and a golden "classification unchanged" suite.

### 1.3 Time-based forecasting
- Ask: "how many orders next month". Score: typical error on the most recent period. Guess: repeat the last value or season.
- Target: an error you accept. Locked set must be the newest rows (`verification.prepare_split` shuffles with `train_test_split`, so this needs its own split). Pilot learning curves assume exchangeable rows; they would be invalid.
- Fee: possible, but only with a time-ordered locked period. Needs a date column detector, lag features, a different "Try the model" form (dates in, number out). Biggest honesty risk. Post-hackathon at the earliest, own design.

### 1.4 Grouping / unusual records
- Ask: "group my customers", "find odd transactions". No target, no held-out truth, so no forecast against a target, no verification, no success fee. If sold at all, it is compute-only with a plain "this is exploration, not a prediction" label. Cost model works (timing) but the quote text, result screens and the gate (fee rule) differ. Do not build before a product decision.

## 2. Regression plan

### 2.1 Principle
A `task_type` ("classification" default, "regression") chooses scoring in a few pure functions. Every existing path stays the default branch. Add a golden test first: the same fixtures produce byte-identical classification baseline, forecast, quote and verification output before and after each slice.

### 2.2 Score, target and the "closeness" idea
Evaluation of "express the score as a 0-100 closeness number so quotes, targets and fee logic stay unchanged":
- Technically good: the pipeline only needs a higher-is-better number in 0..1. R-squared, clipped at 0 for the stored score, fits: `error = 1 - score` already drives `extrapolate`. Payment, gate, quote and `passed = value >= target` stay unchanged.
- Misleading if shown as "N out of 100 right". Classification counts predictions. A regression score is not a count of right answers, and users read 80 as "80 percent of my prices were correct". Also R-squared hides units: 0.8 can mean off by $5,000 or $50,000.
- Verdict: acceptable as the internal number (`score`, stored in the existing `accuracy`-shaped fields via an alias), not acceptable as user wording. Show to the user:
  - "typically off by about $X" (median absolute error on the locked rows, in the target's own units, an estimate)
  - "explains about N out of 100 of the ups and downs" (R-squared)
  - "a simple guess (always the average) is off by about $Y"
  - never "N out of 100 right", never a promise.
- Target wording (owner to confirm): "explain at least N out of 100 of the ups and downs", shown next to the implied typical error ("roughly off by $X at that level", an estimate computed from the work rows). A user who wants "within $5,000" is converted by code to the implied N using the guess error from the work rows; the conversion is shown for approval.

### 2.3 Slices (each shippable and testable)
0. **Honest refusal and reframe** (no regression code). Section 3. Files: `agent/context.py` line ~24, a skill, evals. Not payment.
1. **Detect and record `task_type`** (free). New pure `services/data/task_type.py` (numeric column with many distinct values and a number-like goal); set at `datasets.select_candidate`; readiness says plainly "this column holds numbers" and `run_baseline` is refused with the reframe until slice 2 ships. Files: `task_type.py`, `datasets.py`, `analysis.py`. Tests: unit. Not payment.
2. **Regression families and free baseline** (free). `families.py`: add `build(..., task=...)` with regressors (ridge, forest, boosting); `baseline.fit_and_score` branches on task, returns R-squared, typical error, guess error. Both files ship verbatim to SageMaker and must import only sklearn and pandas. Store `score`, `score_kind`, `typical_error`, `simple_guess_error` in `project.baseline_result`. `insights.trust_level` gets a regression branch. Files: `families.py`, `baseline.py`, `insights.py`, `analysis.py`, `features.py` (no change expected). Not payment.
3. **Readiness, profile, compare for numbers** (free). `insights.measure` balance uses `value_counts` (breaks for a continuous target): replace with spread and skew. `profile._predictive_accuracy`, `compare` permutation `scoring=` use the right metric. Not payment.
4. **Pilot, forecast, target** (free but feeds eligibility, so light HUMAN REVIEW). `pilot._score` branches on task; `forecast.extrapolate` takes a `finite_test_variance` argument (default the binomial term, so classification output is identical); regression uses `~(1-score)^2 * 2/locked_rows` (inferred, to be validated on real data). `target.py`: add the regression phrases, same approval-text rule. `Forecast.metric` = "r2". Files: `pilot.py`, `forecast.py`, `target.py`, `routes/forecast.py`.
5. **Verification and training** (HUMAN REVIEW). `verification.verify_model` dispatches on task (the only function the fee depends on); returns `{metric, value, rows}` unchanged in shape. `training.py` ~158 needs `result["score_kind"]`; `passed` line stays as is. `training_local` passes `task`. Files: `verification.py`, `training.py`, `training_local/`, `ports.py` (TrainingResult). Tests: payments e2e on the mock with a regression fixture: missed target pays compute only, passed pays the fee, our failure voids everything.
6. **SageMaker script** (HUMAN REVIEW: spend path). `train.py`: no stratify for regression, new metrics, `--task` hyperparameter. Regressors have no partial-model path; fit once like boosting. Contract test on mocked boto3, then one live capped job (RUN_PAID, ~1 cent) before release. Files: `train_script/train.py`, `sagemaker.py` (hyperparameter only).
7. **Quote** (HUMAN REVIEW to confirm it is a no-op). `create_quote` already reads `forecast.family` and `cost_samples`; add `task_type` to the stored breakdown only. No change to `fee_of`, caps or the hold. Gate unchanged.
8. **Use the model** (free). `model_use.py`: result is a number, `probabilities: null`, note "an estimate"; model tab shows "typical error" (not "right"); predict-batch adds a `prediction` number column; classes empty. Frontend: one `score` formatter used by `result-step.tsx`, `model-tab.tsx`, forecast and quote cards, share page (`public-result.tsx`; public fields are allow-listed: add `score_kind`, not money).
9. **Agent** (section 3 final state) and the tone evals.

Tiny-diff tactics: default `task_type` None means classification; the new branches sit in new small functions; payment files change only in slices 5 and 7, and only to dispatch.

## 3. Agent side

Today `agent/context.py:24` says only categories can be predicted and to offer yes/no. Replace with a decision step the model performs once the goal is clear and before any search:
1. Classify the goal: yes/no, pick a group, a number, a number over time, or find groups.
2. Say plainly what is supported today: yes/no and pick-a-group.
3. If unsupported, offer the nearest reframe and ask which they prefer: "above or below $X" (X from their data or the median), "which of 3 price bands", "will it go up or down next month".
4. Never search or quote for an unsupported type.

Code backstop (cheap): `select_dataset` / `run_baseline` answer `unsupported_task` when slice 1 finds a many-valued numeric target, with the reframe text, like `clarity.py` does for vague goals.

Reframe by data: a new allow-listed fix operation in `propose_data_fix` / `apply_data_fix` (inferred; Phase 7 tools exist, not read): "turn this number into groups" (median split or 3 quantile bands), replacing the numeric column, with the usual approval card, new dataset version, forecast invalidated. Not payment; the original number column must be dropped or it leaks the answer.

Skill: `what-we-can-predict` (what is and is not supported, wording of the reframe, no money rules). Eval cases (`evals/cases/`): house price goal (expects reframe, no search for a regression dataset), "how many sales next month" (over time, reframe), "group my customers" (not supported, explain), a yes/no churn goal (control: must not be refused), an uploaded file with numeric target (expects `unsupported_task` and a band offer). Checks: no accuracy promise, plain words, no jargon (R-squared, MAE) in replies.

## 4. Phase 6 leftover: the claim guard (`guards.py`, used at `loop.py:204-211`)

The guard replaces a reply with "Nothing was charged or started by me". Pattern, blocked statuses, false blocks:
1. **Payment received** (`payment|pay ... was/is received/confirmed/complete` or `you've paid`): blocked before `paid`. Correct blocks. Possible false block: "a payment is confirmed only after PayPal approves" at `quoted` (explanation, not a claim; inferred, low).
2. **Training/model started or ready** (`(training|the model) ... is ready/is trained/is complete`, `I've trained`, `I've started training`): blocked at every status except `training` and settled ones. False blocks: "I've trained a quick model" and "the model is ready" at `baseline_done`, `quoted`, `awaiting_payment`, `paid`, where the free test really trained a model; "the check on the model is complete". This is the main defect.
3. **Refund/release done** (`refunded|released|voided ... sent/issued/processed/complete`): blocked at all non-settled statuses. False blocks: explanations at `quoted`/`awaiting_payment`: "the unused part is released when the run is complete" (matches within 30 characters).
4. **Promise to run** (`I'll / I can / let me / shall I / do you want me to` + run/start/try/launch/test/train...): blocked at `training` and settled statuses only (the set holds statuses where it is allowed). False blocks at `done`/`stopped`/`failed`: "let me try to explain", "I can start by summarising", "let me test that idea with you" (no tool exists, but no run is promised).

Smallest narrowing (HUMAN REVIEW; tests first, no gate change):
- Pattern 2: drop the bare `the model` and `I've trained` alternatives. Keep paid wording only: `(paid|full) (training|run)`, `training (has started|is running|has finished)`, `I've started (the )?(paid |full )?training`. Free-test wording passes at all statuses.
- Pattern 3: require a past-tense carrier (`has been|have been|was|were|I've`) before the verb, and drop `complete` from the object list.
- Pattern 4: keep the verbs `retrain|re-?train|re-?run|train|start|launch`; drop `try|test|run` alone, unless followed by `(the )?(full|paid|new) (run|training)`. Exclude `let me (try|test) (to )?(explain|summar)`.
- Pattern 1: no change.
Tests (`tests/unit/test_guards.py`, inferred name): honest phrases pass at each status (the list above); true false claims still blocked ("you've been charged" at `quoted`, "training has started" at `paid`, "I've refunded you" at `baseline_done`); a table over all statuses; the claim_blocked trace is unchanged. Unit-only; no payment, gate or ledger code touched.

## 5. Order and decisions

Recommended order:
1. Now (before 11-11): section 4 narrowing; section 3 prompt/skill/evals and the `unsupported_task` backstop. All outside payment code except the guard (reviewed).
2. Post-hackathon: lopsided scoring (1.1) as the first test of the generalised-metric seam; then slices 1 to 9 for regression; live AWS check before release.
3. Later: grouping (product decision), time-based (own design).

Minimal honest demo behaviour for a number goal: "I can predict yes/no or pick a group today, not exact numbers yet. I can answer 'will the price be above $X?' or 'which of 3 price bands?'. Which would you like?", then continue the normal flow on the reframed question. No quote, no price, no accuracy claim for the number itself.

Open questions for the owner:
1. May the 5% success fee apply to regression, or compute-only at first?
2. Target wording: "explain N out of 100 of the ups and downs", or "typically off by no more than X" (converted by code)?
3. Is the "N out of 100" language banned for regression (recommended) or allowed with a changed label?
4. Do number-prediction quotes price differently (regressor timing, 300-tree default)? Price impact is expected to be small (inferred).
5. Is a failed forecast on noisy numbers also "not eligible" at confidence 0.60, or a different bar?
6. Bands reframe: median split or 3 bands by default; who chooses the cut?
7. Demo timing: confirm regression is post-hackathon and the demo shows only the reframe.
8. Does a live capped SageMaker regression job (about 1 cent) get a yes before release?
