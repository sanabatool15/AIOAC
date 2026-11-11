# ML task types 02: success, verification and payments

Status: design only, 2026-11-11. Nothing here is built. Items marked (inferred) were not run or not read in full. Line numbers are from the current branch and will move. Everything that touches the quote, the fee, verification, the gate, lifecycle or the ledger is HUMAN REVIEW (CLAUDE.md). Builds on `specs/regression-and-task-types.md` (which covered regression only) and extends it to five task types: `classification` (built), `regression`, `forecast`, `grouping`, `unusual`.

Hard rules that do NOT change for any type: paid training starts only after the SERVER confirms the PayPal hold; sandbox only; the ledger is append-only; webhooks are idempotent; every job has a hard cap; compute is always captured at actual cost; the success fee is captured only if the locked-test check passes; the rest is voided; our own failure voids everything; no accuracy promise; every number is labelled an estimate; plain words.

## 1. What "success" means today

### 1.1 The path, step by step

1. **Stating the target.** `services/agent/target.py` accepts only a number the user typed: "80%", "8 out of 10", "80 out of 100", "0.8" (lines 11-13), converted to a 0-1 fraction and kept only if `0 < v < 1` (line 30). `user_named` (line 33) is the code guard that stops the model choosing the target; synthetic approval text never counts (lines 9, 19-20). The question hint says "how many out of 100 predictions do they need to be right" (line 15). The route enforces the same range: `PilotIn.target` has `gt=0, lt=1` (`routes/forecast.py:18`), and `pilot.run_pilot` re-checks (`pilot.py:149`).
2. **Eligibility.** `forecast.not_eligible_reason` (`forecast.py:66-81`) says "not eligible" when rows are below `forecast_min_rows` (500, `config.py:73`) or confidence is below `forecast_min_confidence` (0.60, `config.py:72`). `pilot.run_pilot` also refuses a too-small pilot (`pilot.py:169-171`). Reasons are written as "about N out of 100 right".
3. **The forecast.** The free pilot cross-validates three model types on 5-10% of the work rows and keeps one (`pilot.py:120-131`, `173-188`). `forecast.extrapolate` (`forecast.py:36-54`) treats `1 - accuracy` as an error that shrinks as a power of the training size, adds a binomial finite-test term `p*(1-p)/locked_rows` (line 51), and returns a predicted value, a band and a confidence = chance the verified value reaches the target. `suggest_target` scans 99 down to 50 (line 59). The forecast row stores `metric="accuracy"` (`pilot.py:163`, `db/tables.py:161`).
4. **The quote.** `quotes.create_quote` (`quotes.py:314-359`) refuses a non-eligible forecast (328-329), times the chosen model type (`cost_samples`, 338), estimates compute, and adds a fee of `success_fee_percent` (5%, `config.py:71`) of compute: `fee_of` (341-342). Hold = `cap_cents = compute cap + max_fee` (348). The target is only copied into `breakdown["target"]` (353). Card text is the fixed sentence in `routes/quotes.py:100`, and the frontend constant `QUOTE_TERMS` (`adapters.ts:16-17`).
5. **Pay.** `payments.create_order` holds `quote.cap_cents` and stores `compute_amount_cents` and `fee_amount_cents` on the payment (`payments.py:62-66`). `confirm_hold` is the only place a hold becomes `held`/`verified` and the project becomes `paid` (70-99).
6. **Verification.** After training, `verification.verify_model` scores the finished model once on the locked rows with `accuracy_score` (`verification.py:293-303`), returning `{metric: "accuracy", value, rows}`. A failure to verify raises `VerificationError`, which `training.execute_run` treats as OUR failure (`training.py:362-367`).
7. **The decision.** `training.py:368`: `passed = checked["value"] >= target`. The result dict (369-370) is `{accuracy, simple_guess_accuracy, runtime_seconds, verification: {metric, value, rows, target, passed}}`.
8. **Settle.** `payments.settle` captures `min(run.cost_cents, compute cap)` always (`payments.py:135-143`), then captures `min(ceil(5% x compute captured), fee held)` only if `run.status == "done"` and `verification.passed` is truthy (144-153), else `fee_skipped` (155), then voids the rest (156-160). A failed run goes to `void_all` (132-133, 164-179). A user stop skips verification and the fee (`training.py:351-357`).
9. **Receipt.** `GET /payments/{id}` returns held, compute, fee, released, total. The frontend words it in `result-view.ts:18-48, 84-91`, `screens.ts:23-37, 108-110, 167`, `pay-timeline.ts:47-59`.

### 1.2 Every place where success = "accuracy reached the target"

Backend (computing or deciding):
- `baseline.py:364-378` `fit_and_score` (accuracy and a mode-guess accuracy); `baseline.py:340-353` rare-group recall.
- `pilot.py:120-131` `_score` (accuracy); `pilot.py:134-144` `data_issues` (compares `accuracy` to `simple_guess_accuracy`); `pilot.py:163` `metric="accuracy"`; `pilot.py:201` `suggest_target`.
- `forecast.py:39` (`1 - accuracy`), `forecast.py:51` (binomial term), `forecast.py:57-63` (99..50 scan), `forecast.py:66-81` (wording "right").
- `verification.py:218, 300, 303` (`accuracy_score`, metric string); `verification.py:274` (stratified shuffle split, wrong for time).
- `training.py:360-370` (the pass rule and the result keys).
- `ports.py:63-70` `TrainingResult.accuracy / simple_guess_accuracy`; `training_local/backend.py:26`.
- `lifecycle.py:178-197` ("higher" is compared out of 100; message says "out of 100").
- `models.py:32-62` `should_promote`, `record_new_model` (uses `verification.value` and `passed`; type-neutral, good).
- `history.py:17`, `share.py:56-58`, `routes/forecast.py:32, 35` (`metric`, `predicted_metric`), `routes/projects.py:199` (baseline `accuracy`).
- `agent/target.py:15` (hint wording) and the agent tools that echo `baseline_percent` (`agent/tools.py:411`).
- The SageMaker script `train_script/train.py` (accuracy, stratified `_split`) and `metrics.json` (spec `training.md` 2b).

Frontend (wording): `adapters.ts:17, 31-38, 120-121, 248-249`; `screens.ts:108-110, 272-275, 289, 391-394`; `result-view.ts:27-48, 88-91`; `result-step.tsx:131-135` ("Verified result ... out of 100"); `pay-prompt.tsx:17`; `pay-timeline.ts:47, 55-59`.

### 1.3 Defect found while reading (not a payment-code bug, but wrong money wording)

Two screens say something the money model forbids (payments.md section 1 rule 5: the buyer always pays compute):
- `components/shell/pay-prompt.tsx:17`: "You are only charged if your target is verified. If it is missed, the hold is released." Wrong: a miss still pays compute.
- `lib/pay-timeline.ts:56-59`: shows "Target missed. Charged $0" for any finished payment with total 0 (for example a stop or a zero-cost local run, where the target was never checked), and "Missed: the hold is released" before the run ends.
Fix these first, as a small frontend change with a text test, before any new task type multiplies the wording. `adapters.ts:17` (`QUOTE_TERMS`) is already correct and is the model sentence.

## 2. The five task types

### 2.0 One idea: a normalised "check score" per type

The pipeline needs one higher-is-better number between 0 and 1 for the forecast and the fee, plus a yes/no. Store it as `verification.value`, `verification.target`, `verification.passed` for every type (section 3). It is an internal number. How honest is it?

- **Acceptable internally.** `extrapolate` only needs "error = 1 - score". `passed = value >= target` stays valid. The Model-version rule (`models.py:32-49`) already compares `value` and `passed` only.
- **Misleading if shown as "N out of 100 right".** Only classification counts right answers. A regression R-squared of 0.8 does not mean 80 of 100 predictions were correct, and the same 0.8 can mean off by $5,000 or by $50,000. A forecast skill of 0.2 sounds poor and is often good. A stability score of 0.9 is not an accuracy at all.
- **Rule for wording (decided here, owner to confirm in D3):** the phrase "out of 100 right" is reserved for `classification`. Other types get their own unit sentence (below) and always show a plain-money or plain-unit companion ("typically off by about $X") next to the 0-100 share. The API field is named `score_kind` (`right`, `variance_explained`, `beats_simple_rule`, `stability_clear`, `stability_flagged`) so every screen picks the sentence from the kind and never prints "out of 100 right" by default. A guard test (like the existing "money only through `dollars()`" test, H4 in `breakpoints.md`) must fail if the string "out of 100 right" appears outside the classification branch.
- **Never** show the internal number without a unit sentence, never in the model tab as "accuracy", and never as a promise.

### 2.1 Classification (built; the reference)

- Customer says: "I want about 80 out of 100 predictions to be right."
- Verified on the locked rows: share of right predictions (`accuracy_score`).
- Target met: `value >= target`.
- Success fee: applies, 5% of compute actually captured, only if met. Unchanged.
- Pilot forecast and confidence: as built (`forecast.py:36-54`).
- Not eligible, plain words (as built, `forecast.py:66-81`): too few rows; best case is below your target; under 60% sure of reaching it; the answer column is too lopsided or has too little signal (from `data_issues`).

### 2.2 Regression ("a number")

- Customer says: "I want to know roughly what price a house will sell for, and I want the guess to explain at least 80 out of 100 of the ups and downs in prices." Optional second form: "typically off by no more than $5,000" (see D4).
- Number verified on the locked rows, in two plain forms: (a) typical error = median absolute error on the locked rows, in the answer column's own units ("typically off by about $4,200"); (b) share of ups and downs explained = R-squared on the locked rows, clipped to 0..1 ("explains about 84 out of 100 of the ups and downs"). The simple rule for comparison is "always guess the average" (its typical error is shown: "a simple guess would be off by about $11,000").
- Internal check score: (b), clipped. Target met: `value >= target` (same line as today). Recommended first release (Option A of D4): the target is stated and verified as (b), and the code shows the implied dollar error beside it ("at that level the typical miss is roughly $X, an estimate from your rows"), converted from the work rows. Option B (dollar target) is described in D4 and needs a direction flag.
- Success fee: applies, 5% of compute, only if target met. Reasoning: the result is checked against rows the model never saw, so it is exactly as verifiable as classification. OWNER DECISION D1.
- Free pilot and confidence: same learning-curve method on the score, with a continuous-score noise term in place of the binomial one, about `2*(1-score)^2/locked_rows` (inferred, to validate on real data; passed into `extrapolate` as a `finite_test_variance` argument whose default is today's binomial term so classification output is byte-identical). Same 0.60 bar.
- Not eligible, plain words: "There are only N usable rows"; "Even in the best case we expect to explain about N out of 100 of the ups and downs, below your target of M"; "We are only about P% sure the full run would reach it"; "The numbers jump around too much (a few very large values dominate), so a typical guess would be unreliable" (inferred: outlier share check); "The free test barely beats always guessing the average".

### 2.3 Forecast ("numbers over time")

- Customer says: "I want to predict next month's orders, and beat the simple rule of repeating last month by 15 out of 100." Meaning, in plain words: the typical miss should be 15 out of 100 smaller than the miss you would get by just repeating last period.
- Number verified: the typical error (mean absolute error) on a locked LATEST period, compared with the same error of the simple rule (repeat last period, or the same period last year when the data has a yearly cycle). Internal check score = `1 - error / simple_rule_error`, clipped to 0..1. Companion text: "typically off by about 40 orders a month; repeating last month would be off by about 52".
- Target met: `value >= target` on the newest locked periods.
- Locked set: the NEWEST rows, in time order, never a shuffle. `verification.prepare_split` shuffles with `train_test_split` (`verification.py:274`), which is invalid for time series, so forecast needs its own split function (new small function, same storage keys `splits/<version>/work.csv` and `locked.csv`). Minimum: at least 24 periods in total and at least 6 locked periods (inferred, to calibrate). Child versions still inherit the root's locked periods.
- Success fee: RECOMMENDATION: compute-only in the first release (fee 0). Reasoning: the locked set is the newest few periods, a very small, single sample of "the future"; one odd month can pass or fail it; and the pilot's learning-curve forecast does not apply to time order, so our forecast of success is weak. We cannot honestly say we "verified" a future. A fee can be switched on later (D1) once real jobs show the forecast and the verified check agree. With fee 0 the hold equals the compute cap (section 3).
- Free pilot and confidence: rolling-origin backtests on the work rows (train on the past, score the next block, repeated 3 times, a few model types plus the simple rule), not 3-fold shuffling. The "learning curve" is the score over longer histories. Confidence uses the spread across backtests (inferred) and is capped at a lower ceiling than other types until calibrated.
- Not eligible, plain words: "There are only N periods of history, which is too little"; "We could not find a date or time column"; "The dates have gaps or repeats we cannot sort out (a free fix may help)"; "In our test runs we could not beat repeating last period by much, so a model is unlikely to help here"; "Your target of N is above what the best test run reached (about M)".

### 2.4 Grouping (clustering)

- Customer says: "Group my customers into about 4 types." There is no accuracy target and no right answer to be right about.
- What we verify on the locked rows (no truth exists): that the groups are clear and stable. Concretely (inferred, thresholds to calibrate on real data): (a) fit on work rows; assign locked rows to the nearest group; (b) refit on the locked rows plus a resample and measure agreement between the two groupings (adjusted Rand index) and the separation of groups on locked rows (silhouette). Internal score `stability_clear` = a documented blend in 0..1. "Target met" is renamed "check passed" and defined as: stability at least 0.70 and separation at least 0.25 (inferred), computed once on the locked rows.
- Wording: "The groups are clear and stable on rows the model never saw." Never "accurate", never "right".
- Success fee: none. A success fee would charge for a quality we cannot define as right or wrong. The check result does NOT change the money: compute only, fee_amount 0. OWNER DECISION D2 (alternative: a flat reduced fee, not recommended).
- What we cannot verify, and the UI must say plainly: that the groups are useful or meaningful for the business; that "4" is the right number; that the groups will stay the same on next year's customers; and that the groups mean what a person would name them. The result screen says: "This is exploration, not a prediction."
- Free pilot and forecast: no forecast against a target. The pilot runs the same stability check on a 5-10% slice and returns a preview ("on a small test the groups looked clear"). `eligible` means enough rows and a stable preview. `confidence` is not a chance; store the preview stability and label it "preview", not a percent chance (frontend branches on `metric`).
- Not eligible, plain words: "There are only N rows, too few to form stable groups"; "Everything in your data looks alike; we cannot find clear groups"; "Most columns are text or empty, so there is little to group on"; "The groups change every time we try (not stable)".

### 2.5 Unusual (anomaly detection)

- Customer says: "Flag the most unusual transactions, about 1 in 100."
- What we verify (no labels): (a) the share flagged on the locked rows is close to the share asked for (within a stated tolerance); (b) the flagged set is stable: the overlap between the rows flagged by two fits on different samples is at least a stated floor (inferred, 0.6 to calibrate). Score `stability_flagged` in 0..1.
- Check passed: both conditions. Wording: "It flags about 1 in 100 rows, and mostly the same rows each time we test."
- Success fee: none (same reasoning as grouping; D2). Compute-only.
- What we cannot verify: that the flagged rows are actually fraud, errors or problems. A truly unusual row can be perfectly normal. If the user HAS known past problems marked in a column, the better route is classification with lopsided classes (`regression-and-task-types.md` 1.1), and the agent should offer that.
- Pilot and confidence: as grouping.
- Not eligible, plain words: "There are only N rows"; "Too few rows to say what is normal"; "Nearly every row looks unusual in a different way, so flags would be noise"; "The flagged rows change every time we test".

## 3. Money invariants per task type

Rule: the money model is untouched. The only difference between types is the NUMBER `fee_cents` that the quote stores (0 for no-fee types) and the type-specific code that fills `verification`. `settle` already behaves correctly when `pay.fee_amount_cents == 0`: the fee is `min(ceil(..), 0) = 0`, the branch `passed and fee > 0` (`payments.py:148`) is false, state becomes `fee_skipped` (155), the rest is voided. No `payments.py` change is needed for no-fee types.

| Rule | Unchanged? | How the new types satisfy it |
|---|---|---|
| Hold = compute cap + max fee (`quotes.py:348`, `payments.py:62`) | Yes | Fee types: same formula. No-fee types: max fee 0, hold = compute cap. The hold amount is confirmed against PayPal as today (`payments.py:88`). |
| Paid work starts only after the server-confirmed hold (`gate.py:122-125`, `payments.py:70-99`) | Yes | Type-agnostic. |
| Quote pins data version and model type (`gate.py:126-132`) | Yes | Give each type's families their own ids (`reg_ridge`, `reg_forest`, `reg_boosting`, `fc_...`, `grp_kmeans`, `unu_isolation`), so the existing family pin also pins the task type. No gate edit (D5 notes the stricter option). |
| Compute capture never above compute cap (`training.py:350`, `payments.py:136`) | Yes | Type-agnostic. SageMaker still derives `MaxRuntimeInSeconds` from the cap. |
| Compute always captured, even on a miss | Yes | Same. A grouping check that "fails" still pays compute. |
| Fee only if verification passed (`payments.py:145-148`) | Yes | Fee types: `passed` from the type's check. No-fee types: fee held is 0. |
| Fee = 5% of compute actually captured, never above the fee held (`payments.py:147`) | Yes | Same. |
| Void the remainder (`payments.py:156-160`) | Yes | Same. |
| Our failure voids everything (`payments.py:132-133`, `training.py:309-318`, 364-367) | Yes | A new type's verification error raises `VerificationError`, mapped to our failure as today. A type with no verifier written must raise, never skip. |
| Stop: pay compute so far, no fee (`training.py:351-357`) | Yes | Same, no verification. |
| Idempotency keys `compute-{id}`, `fee-{id}`, `void-{id}` (`payments.py:138, 149, 159`) | Yes | Same. |
| Ledger kinds `compute_capture`, `fee_capture`, append-only (`payments.py:141, 152`) | Yes | No new kind. A no-fee type simply has no `fee_capture` row. |
| Webhook cross-check and idempotency (`payments.py:102-121`) | Yes | Type-agnostic. |
| Exactly-once run ending (`training.py:292-294`, `execute_run` claim) | Yes | Same. |
| Global budget guard and per-job max (`gate.py:133`, `cost.py:269`, `config.py:69`) | Yes | Same $7 max applies to every type. |
| Expiry of unused holds (`payments.py:195-210`) | Yes | Same. |

### 3.1 The smallest code diff

Principle: every type writes the same three normalised values, and nothing downstream reads anything else.

- `verification = {metric, value, rows, target, passed, task_type, score_kind, plain}` where `value`, `target` are 0-1 and higher is better, `passed` is a bool, and the rest are labels. `models.verified_value`/`passed` already exist (`models.py:57-62`).
- A new pure module `services/data/check.py` holds one function per type: `verify(task_type, model_bytes, storage, locked_key, target_col, ...) -> {metric, value, rows, ...}` and `decide(task_type, value, target) -> bool` (for now `value >= target` for every type; section D4 option B adds a direction).
- A new pure module `services/data/task_policy.py`: `fee_applies(task_type) -> bool` (classification, regression True; forecast, grouping, unusual False at first), `min_rows`, `score_kind`, `plain_unit`. Single place the owner's D1 and D2 answers live.

Exact functions that would change, and why each is HUMAN REVIEW:

1. `verification.verify_model` (`verification.py:293-303`): becomes a thin dispatcher on `task_type` to `check.verify`. HUMAN REVIEW: this is the only function whose output can trigger a fee capture. Classification output must stay byte-identical (golden test).
2. `training.execute_run` (`training.py:363-370`): pass `task_type` (read from the quote's pinned family, so no new argument elsewhere), call `check.decide` instead of the inline `>=`, and write the extra labels into `verification`. HUMAN REVIEW: this line IS the fee decision. The diff is three lines; the comparison must remain `value >= target` for classification.
3. `quotes.create_quote` (`quotes.py:341-349`): `fee_of` returns 0 when `not task_policy.fee_applies(task_type)`; `fee_cents`, `high_cents`, `cap_cents` follow. Add `task_type` to `breakdown` (line 350-353). HUMAN REVIEW: sets the hold amount and the cap.
4. `lifecycle.reopen_for_improvement` (`lifecycle.py:178-197`): for no-target types skip the "strictly higher" rule (section 5) and make the "reached N out of 100" message type-aware. HUMAN REVIEW: it controls when a new paid round may start.
5. `forecast.extrapolate`, `suggest_target`, `not_eligible_reason` (`forecast.py:36-81`): add the `finite_test_variance` argument and a `floor` for the scan; wording by `score_kind`. Feeds eligibility only (light HUMAN REVIEW, it decides what we sell).
6. `routes/quotes.py:100` and `adapters.ts:17` (terms text): per-type sentence. HUMAN REVIEW: user-facing money terms.
7. `gate.py`: no change recommended (D5). `payments.py`: no change. `ports.py`: no change (the names `accuracy`/`simple_guess_accuracy` of `TrainingResult` stay as aliases of "score" and "simple rule score"; document that in the dataclass, rename later).
8. Backends: `training_local` and the SageMaker script derive the task from the family id; `TrainingBackend.run` keeps its signature.

## 4. Quote and cost per type

- **Cost samples per family.** `pilot.py:188` times the chosen family via `baseline.sample_timings(...)` at 5/10/20% of rows; `quotes.py:338` feeds `cost_samples` to `estimate_quote`. Each new family needs a `PILOT_SIZE` and `FULL_SIZE` entry (`families.py:19-24`) so the timed model is the model that runs. `families.py` and `baseline.py` ship verbatim to SageMaker (`training.md` 2b), so they may import only scikit-learn, pandas and the standard library.
- **Regression:** ridge (like logistic: seconds), forest regressor (like the classifier, 300 trees), boosting regressor. Timing curve fit as today.
- **Forecast:** a few lag-feature models (ridge, boosting) plus the simple rule. Time the fit on the lagged table. Rolling-origin scoring multiplies the FREE pilot's time, not the paid run's (one fit on all work rows).
- **Grouping:** k-means is about linear in rows; a mixture model or hierarchical clustering can grow near-quadratically. `SLOPE_RANGE = (1.0, 2.0)` (`cost.py:20`) already allows up to quadratic growth; keep hierarchical clustering out of the first release and cap rows per grouping job (inferred, 50,000 as the dataset limit already is).
- **Unusual:** isolation forest is about linear; local-outlier methods are not (leave out).
- **Fixed costs dominate small jobs:** 240 s startup and the 50 cent platform fee (`prices.py:290-293`) make every small job about 53 cents whatever the type. That is expected and shown by the breakdown.
- **SageMaker runtime per family:** `MaxRuntimeInSeconds` comes from the cap exactly as today (`training.md` 2b). Regressors, k-means and isolation forest have no partial-model path: they fit once and save at the end (like boosting and logistic), so a stop at the cap before the fit finishes returns no model and the run is settled as a stop or a cap stop with no fee. The script needs `task` from the family id, non-stratified splits for non-classification, and per-type `metrics.json`. HUMAN REVIEW (spend path) and one live capped job per new type (`RUN_PAID`, about 1 cent) before release.
- **Per-job max and caps:** unchanged ($7, `config.py:69`; `QuoteTooExpensive`, `cost.py:269-270`). For no-fee types the hold equals the compute cap, so the hold is lower than for a fee type with the same compute.
- **Quote card text.** `create_quote` and `quote_view` add `task_type`, `score_kind`, `fee_applies`. The terms sentence per type:
  - classification, regression: "You pay for compute either way. The success fee is charged only if the result is verified on test data we keep aside."
  - forecast, grouping, unusual (first release): "You pay for compute. There is no success fee for this kind of project."
- **Model-type sentence.** `families.TYPE_NOTE` ("This is only the model type we tested, not a promise of a better result", `families.py:34-36`) stays, with per-type plain names, for example "a simple linear model (for numbers)", "a forest of decision trees (for numbers)", "a model that uses the last few periods", "a grouping method that finds N groups", "a method that flags unusual rows". `type_info` must key on the family id so the note and name follow the pinned type.

## 5. Gate, lifecycle, rounds and data fixes

- **States and transitions are unchanged.** `ORDER`, `SIDE_EXITS`, `transition` (`lifecycle.py:146-172`) are type-agnostic, as are the gate actions (`gate.py:51-69`). `paid` still requires a server-confirmed hold (`lifecycle.py:167-170`).
- **Improve round (after a miss):** unchanged for fee types; `reopen_for_improvement` allows it when `passed is False` (`lifecycle.py:192`). It returns the project to `baseline_done` and a new free pilot, a new quote and a new hold follow.
- **Try a higher target, per type** ("higher" = strictly better on the stated measure, compared on the 0-100 scale as today, `lifecycle.py:193-194`):
  - classification: more right (unchanged).
  - regression, Option A (target is the explained share): a higher explained share. Option B (dollar target): a LOWER typical error (the direction flag in D4); the screen says "a smaller typical miss", never "higher".
  - forecast: a larger "beats the simple rule" share (a smaller typical miss).
  - grouping, unusual: no "higher". Instead "Try a different number of groups" or "Try a different share to flag". Because there is no money-bearing target, a new free pilot is always allowed after a finished run regardless of `passed`; `reopen_for_improvement` gets one branch for types without a target (skip lines 192-197). The new quote and hold are still required before paid work.
- **Data-fix tools** (`fixes.py`, gate level 1, limit of 3, payments.md section 11): the two existing fixes (drop repeated rows, drop mostly empty columns) are safe for regression. For forecast, "drop repeated rows" is wrong when identical values repeat legitimately across dates: restrict to rows repeating the same timestamp; add "sort by date" (inferred). For grouping and unusual, only "drop mostly empty columns"; dropping repeated rows can hide the very rows (many identical transactions) the user cares about (inferred). The locked rows keep coming from the ROOT version for every type (`verification.py:209-212`); for forecast the root's locked set is the newest periods and a child may not move that boundary.

## 6. Result and receipt wording per type

Fixed sentences, built by code from stored numbers; every measured number says it was measured on rows we kept aside and that new data may differ. Placeholders in braces. "Charged" lines always come from the receipt numbers (as `recapNote` does, `result-view.ts:84-91`).

### 6.1 Classification (exists, unchanged)
- Verified: "Target reached. Checked once on test data we kept aside: about {v} out of 100 right, against your target of {t} out of 100. You paid for compute and the success fee."
- Missed: "Target not reached. ... below your target of {t} out of 100. You paid for compute only, no success fee. We kept the best model."
- Stopped: "You stopped the run. You paid for the compute used so far, no success fee."
- Our failure: "Something went wrong on our side. You pay $0. The whole hold was released."

### 6.2 Regression
- Verified: "Target reached. On rows the model never saw, it explains about {v} out of 100 of the ups and downs in {column}, and is typically off by about {err} (an estimate). Your target was {t}. You paid for compute and the success fee."
- Missed: "Target not reached. It explains about {v} out of 100 of the ups and downs, below your target of {t}, and is typically off by about {err}. A simple guess (always the average) would be off by about {guess_err}. You paid for compute only, no success fee. We kept the best model."
- Stopped: "You stopped the run. You paid for the compute used so far, no success fee, and there is no check result."
- Our failure: same sentence as classification.

### 6.3 Forecast (no fee in the first release)
- Check passed: "On the newest {n} periods we kept aside, the model beat the simple rule of repeating last period by about {v} out of 100 (typically off by {err}, the simple rule by {rule_err}). Your target was {t}. This is a test on past data, not a promise about the future. You paid for compute. There is no success fee for this kind of project."
- Check not passed: "The model did not reach your target: it beat repeating last period by about {v} out of 100, below {t}. You paid for compute. We kept the best model."
- Stopped, our failure: as above.

### 6.4 Grouping
- Check passed: "We found {k} groups, and they were clear and steady on rows the model never saw. This is exploration, not a prediction: we cannot tell whether the groups are useful for your business. You paid for compute. There is no success fee for this kind of project."
- Check not passed: "The groups were not clear or not steady on rows we kept aside, so we would not rely on them. You paid for compute. We kept the result so you can look at it."
- Stopped, our failure: as above.

### 6.5 Unusual
- Check passed: "The model flagged about {p} of every 100 rows, and mostly the same rows when we tested it again. We cannot tell whether a flagged row is a real problem. You paid for compute. There is no success fee for this kind of project."
- Check not passed: "The flagged rows were not steady on rows we kept aside, so treat them as hints only. You paid for compute."

### 6.6 Public share page (`share.py:56-70`, allow-listed)
Keep the existing exact-key-set rule and leak scan. Add only non-money, non-id keys: `task_type`, `score_kind`, and a `headline` object of plain strings computed by code: classification `{right_out_of_100, simple_guess_out_of_100}`; regression `{explained_out_of_100, typical_error_text, simple_guess_error_text}` (unit text uses the column name; a currency symbol only when the goal text names money, inferred); forecast `{beats_simple_rule_out_of_100, typical_error_text, periods_checked}`; grouping `{groups, clear_and_steady: bool}`; unusual `{share_flagged_out_of_100, steady: bool}`. `verification.passed` for no-fee types is shown as "check passed", never "target reached". No cost, payment, project or user ids, no storage keys (existing test).

## 7. Payments safety test matrix on the mock provider

All on `doubles/payments.MockPaymentProvider` with local training; the existing mock already enforces no capture above the hold and no capture after a void (`payments.md` section 7). One fixture per type; the scenario list is run for each type, with a golden test first that proves classification output is unchanged.

| # | Scenario | Classification | Regression | Forecast | Grouping | Unusual |
|---|---|---|---|---|---|---|
| 1 | Hit/pass: compute captured, fee per type policy, remainder voided | compute + fee | compute + fee | compute only, `fee_skipped` | compute only | compute only |
| 2 | Miss/not passed: compute only, `fee_skipped`, remainder voided | yes | yes | yes | yes | yes |
| 3 | User stop: compute so far, no verification, no fee, project `stopped` | yes | yes | yes | yes | yes |
| 4 | Our failure in training: whole hold voided, $0, `voided` | yes | yes | yes | yes | yes |
| 5 | Our failure in verification (`VerificationError`): whole hold voided | yes | yes | yes | yes | yes |
| 6 | Repeated settle / repeated capture with the same request id: no second capture, one ledger row per kind | yes | yes | yes | yes | yes |
| 7 | Hold never confirmed (authorize not called or `declined`): `/train` refused with 409, nothing runs | yes | yes | yes | yes | yes |
| 8 | Cap reached (cost at the cap): compute never above the compute cap, total captures never above the hold | yes | yes | yes | yes | yes |
| 9 | Fee never captured unless `passed` AND the type pays a fee (assert `fee_capture` absent for the three no-fee types even when passed) | covered | covered | new | new | new |
| 10 | Quote hold equals compute cap + max fee; for no-fee types equals compute cap | covered | new | new | new | new |
| 11 | Quote pin: changing data or family after quoting refuses `/train` (gate) | covered | new | new | new | new |
| 12 | Settle retry after a PayPal outage resumes from saved state | covered | new | new | new | new |
| 13 | Second round: Improve after a miss gives a new quote, new hold, new model version | covered | new | new | new (different k) | new |
| 14 | Try a higher/lower target per type, including the plain 400 message naming both numbers | covered | new | new | n/a (no target) | n/a |
| 15 | Eligibility refusal: a not-eligible forecast cannot be quoted (409) | covered | new | new | new | new |

Files to extend:
- `backend/tests/e2e/test_payments_and_demo.py`: add the per-type happy path and the miss/stop/failure cases (rows 1-5), keeping the classification demo check as is.
- `backend/tests/e2e/test_forecast_flow.py`: per-type pilot, eligibility, not-eligible reasons, quote refusal (rows 10, 15).
- `backend/tests/e2e/test_higher_target.py`: per-type "higher/lower target" and the no-target "different number of groups" path (rows 13-14).
- `backend/tests/e2e/test_tenant_isolation.py`: it lists every route and fails on an unclassified one; add the new routes (a per-type pilot parameter route, if any) and extend the public-result test to assert the exact key set per type and the leak scan.
- Also (not named in the brief, but required): `tests/unit` golden tests for `verification`/`check.verify`, `forecast.extrapolate` with the default variance, `task_policy`, and `tests/unit/test_architecture.py` stays green; a frontend text test that "out of 100 right" occurs only in the classification branch and that no screen says "only charged if verified".

## 8. Owner decisions, slices and risks

### D. Owner decisions

1. **Success fee per type.** Options: (a) fee for classification and regression only; (b) fee for all verifiable types incl. forecast; (c) compute-only everywhere new. Recommendation: (a). Forecast gets a fee later, only after real jobs show forecast and check agree. Grouping and unusual never get a fee in v1 (nothing to verify as right).
2. **Grouping and unusual money.** Options: (a) compute only (recommended); (b) flat reduced fee if the stability check passes; (c) do not sell them, free exploration only. Recommendation: (a). If (b), a fee must still be held and captured only on a pass, and the user must be told the pass means "clear and steady", not "useful".
3. **Wording of the 0-100 score.** Options: (a) reserve "out of 100 right" for classification and use a unit sentence per type (recommended); (b) one "closeness N out of 100" everywhere. Recommendation: (a); (b) is misleading (section 2.0).
4. **Regression target form.** Options: (A) target and verification are the explained share, with the implied dollar error shown beside it (recommended, no change to the comparison direction); (B) the user states "within $X", verified on the dollar error with a direction flag (`passed = value <= target`) in `check.decide`, which is a small, reviewable change. Not recommended: converting dollars to a share in advance and verifying the share, because the dollar target could then be shown as missed while the share passed (inconsistent receipt).
5. **Task-type pin in the gate.** Options: (a) rely on family ids being unique per task (recommended, no gate edit); (b) also compare `quote.breakdown.task_type` to `project.task_type` at `gate.py:128-132`. Recommendation: (a) now, (b) if a family id is ever shared between tasks.
6. **Forecast bar.** Minimum periods and locked periods (inferred 24 and 6), and the confidence ceiling until calibrated. Options: conservative (recommended) or equal to other types.
7. **Eligibility bar for regression/forecast.** Same 0.60 confidence and 500 rows, or stricter. Recommendation: same for regression; stricter for forecast (more rows, lower ceiling).
8. **Release order and demo.** Recommended: nothing here before the 2026-11-12 deadline (internal target 11-11); the demo shows classification only. After: wording fix (1.3), classification golden tests, lopsided scoring, regression, then forecast, then grouping/unusual.
9. **Live paid jobs.** Does each new type's capped SageMaker job (about 1 cent) get a yes before release (CLAUDE.md: real services cost money; ask first)?
10. **Share page.** Allow the new headline fields (6.6) or keep the public page classification-only at first. Recommendation: classification and regression first.

### Slices (each shippable, free before paid)
0. Fix the two wrong money wordings and add the text guard test (frontend only).
1. Golden tests: classification baseline, forecast, quote, verification, settle outputs frozen.
2. `task_type` recorded at dataset selection (free); `task_policy.py`; no behaviour change.
3. Regression families and baseline (free), then regression pilot/forecast (light review).
4. `check.py`, `verify_model` dispatch, `execute_run` pass rule, `create_quote` fee rule, terms text (HUMAN REVIEW, payment e2e matrix rows 1-12).
5. SageMaker script per task, mocked-boto3 contract tests, then one live capped job per type (D9).
6. Frontend wording per `score_kind`, result/receipt/share (section 6).
7. Forecast (time split, backtest pilot), then grouping and unusual (stability checks, no-target round rule in `lifecycle`).

### Risks
- **Overselling forecast and regression.** A good-looking pass on a small locked set. Mitigation: min locked rows, conservative confidence, labels as estimates, no fee for forecast first.
- **Name drift:** `accuracy` and `simple_guess_accuracy` carry non-accuracy meaning (`ports.py:63-70`, `result["accuracy"]`, `adapters`). Mitigation: `score_kind` required at every display; later rename (inferred).
- **Locked-set leakage for time data** if the shuffle split is reused. Mitigation: separate split function, test that every locked row is newer than every work row.
- **Check thresholds for grouping/unusual are guesses** (inferred); calibrate on real data before any wording says "clear".
- **Cost under-estimation** for non-linear families; keep them out of v1.
- **Client text drift** around money (already found, section 1.3); the guard test is the control.

## 9. Acceptance checklist

- [ ] The two wrong money sentences (`pay-prompt.tsx:17`, `pay-timeline.ts:56-59`) are fixed and a text test forbids "only charged if verified" and "Target missed. Charged $0".
- [ ] Golden tests prove classification baseline, forecast, quote, verification and settle outputs are byte-identical before and after each slice.
- [ ] Every task type writes `verification.value`, `target`, `passed`, `score_kind`; `payments.py` and `gate.py` have zero diffs (or each diff is listed with a human reviewer's note).
- [ ] `verify_model`, `execute_run` (pass rule), `create_quote` (fee rule), `reopen_for_improvement` and the terms text are marked HUMAN REVIEW in the PR and explained in plain words.
- [ ] No-fee types have `fee_cents = 0`, hold = compute cap, `fee_skipped` even when the check passed, and no `fee_capture` ledger row (test).
- [ ] Section 7 matrix rows 1-15 pass on the mock for every shipped type; hold-never-confirmed always refuses `/train` with 409.
- [ ] A verification error for any type voids the whole hold and the user pays $0.
- [ ] "Out of 100 right" appears only for classification; every other type shows its unit sentence and a plain companion number; every number is labelled an estimate or "measured on rows we kept aside".
- [ ] Forecast locked rows are the newest periods (test); grouping and unusual say plainly what we cannot verify.
- [ ] Public share page returns the exact allow-listed key set per type, no money, ids or storage keys (extended `test_tenant_isolation.py`).
- [ ] Owner has answered D1-D10; each new type has had one capped live SageMaker job if D9 is yes; `pytest` and the demo check pass.
