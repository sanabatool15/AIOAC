# ML tasks 01: backend ML core (all classical tabular task types)

Status: design only, 2026-11-11. Nothing here is built. No code was changed. Items marked (inferred) were not run or measured. Line numbers are from the code on branch `claude/ml-task-types-spec` and will drift. Continues `specs/regression-and-task-types.md` (which covered classification plus regression only) and widens it to five task types. Where the two disagree, this file wins for the backend.

Scope: scikit-learn tabular ML only. Deep learning, text, images and audio stay OUT. Hard rules in `CLAUDE.md` do not change: no paid work before a server-confirmed hold, hold then capture actual compute then void the rest, append-only ledger, hard spend cap, no accuracy promises, plain words in the main flow (no F1, MAE, R-squared, "split"), every estimate labelled. Payment code, gate, verification, quotes, lifecycle and SageMaker packaging are HUMAN REVIEW; slices that touch them say so.

Task type ids and plain names (use exactly these everywhere):

| id | plain name | asks |
|---|---|---|
| `classification` | yes/no or a few groups | "will this customer leave" |
| `regression` | a number | "what price will this sell for" |
| `forecast` | a number over time | "how many orders next month" |
| `grouping` | find natural groups | "group my customers" |
| `unusual` | find unusual records | "find odd transactions" |

---

## 1. Current state (classification only)

### 1.1 How each stage works today

**Data prep.** `features.prepare_features(df, target)` (`services/data/features.py:49-55`) drops row-ID-like columns (`id_like_columns`, :8-17, text or int column with at least 95% unique values), drops exact copies of the answer (`leaky_columns`, :20-34), drops duplicate rows, and converts numbers stored as text (:37-46). It is called by the baseline (`baseline.py:63,97`), the split (`verification.py:63,70`), compare, and the SageMaker script (`train.py:53`).

**Free baseline.** `analysis.baseline_detailed` (`services/data/analysis.py:27-39`) calls `baseline.run_baseline` (`baseline.py:94-100`): `fit_and_score` (:61-75) prepares the file, splits 80/20 with `_split` (:53-58, stratified), fits one random forest (100 trees), scores with `accuracy_score` (:70), computes the "simple guess" as the training majority class (:71), and `rare_group_recall` (:40-50) reports the share of the smallest group found when that group is under 20%. `sample_timings` (:78-91) times the family on 5%, 10% and 20% samples; these feed the cost estimator. Result is stored as `project.baseline_result = {accuracy, simple_guess_accuracy}` plus a `BaselineRun` row (`analysis.py:32-36`, `db/tables.py:104-110`). `rare_group_caught` is NOT stored (docstring `analysis.py:28-29`).

**Readiness.** `insights.analyze` (`insights.py:40-96`) measures rows, duplicates, missing, `minority_share` from `value_counts` of the target (:48-50), constant, leaky and ID columns; grade from fixed penalties. `trust_level` (:87-96) is accuracy lift over the simple guess (0.15 and 0.05 thresholds). `profile.py` types the target (`_target_part`, :101-124: at most 20 distinct values or bool is a "category", else numeric is a "number", whose `balance_text` is "a number, not a few groups"), and `_predictive_accuracy` (:139-157) scores a single column by majority-vote accuracy per band.

**Pilot (free).** `pilot.run_pilot` (`pilot.py:66-121`) requires `0 < target < 1` (:68), takes the WORK rows only (`verification.split_for`, :73), draws a sample of 8% (min 100, max 3000 rows, :27-28,88), and runs successive halving over all three families (`families.PLAIN_NAMES`, :95) at rungs P/4, P/2, P (:94). Each model is scored by 3-fold cross-validation (`_score`, :39-50: `StratifiedKFold`, accuracy as `(predict == y).mean()`), the weaker half is dropped after each rung (:100-105), the survivor's learning curve is drawn (:108-112), and the cost timings are measured on the winner at full size (:107). `Forecast.metric="accuracy"` is hard-coded (:82).

**Forecast and eligibility.** `forecast.extrapolate` (`forecast.py:36-54`) fits `error = 1 - accuracy` as a power law of training rows (exponent 0 to 0.4, error never more than halved, :18-19,43-47), adds noise terms in quadrature including the BINOMIAL finite-test term `p*(1-p)/locked_rows` (:51), and returns predicted score, a 95% band and `confidence = P(verified >= target)` (:52-54). `suggest_target` (:57-63) scans 0.99 down to 0.50 in steps of 0.01. `not_eligible_reason` (:66-81) uses "out of 100 right" wording and `settings.forecast_min_confidence` (0.60) and `forecast_min_rows` (500) (`config.py:72-73`).

**Locked-test verification.** `verification.prepare_split` (`verification.py:49-77`) writes `splits/<version>/work.csv` and `locked.csv` once: a random, stratified 80/20 split with seed 7 (:25-26,72-74). Child versions inherit the locked rows from the root by row content (`row_keys`, :37-42; :60-69). `verify_model` (:91-101) loads the model and returns `{metric: "accuracy", value: accuracy_score(...), rows}`; any exception is OUR failure (`VerificationError`).

**Training, local and SageMaker.** `training.execute_run` (`training.py:111-177`) runs the backend on the WORK file with the quote's compute cap and the quote's pinned family (:130-134), verifies once (:153), sets `passed = checked["value"] >= target` (:158) and builds `result` with `accuracy`, `simple_guess_accuracy`, `runtime_seconds`, `verification` (:159-160). Local: `LocalBackend.run` (`training_local/backend.py:122-137`) calls `fit_and_score` with 300 trees. SageMaker: `SageMakerBackend._create_job` (`sagemaker.py:126-155`) passes hyperparameters `target` and `family`; the script (`train_script/train.py:46-89`) re-prepares data (:53), splits with `baseline._split` (:54), grows a forest in 25-tree batches so SIGTERM saves a partial forest (:57-70), fits boosting and linear in one call (:71-74), scores `accuracy_score` (:77-78) and writes `metrics.json` (:79-84). `TrainingResult` carries `accuracy`, `simple_guess_accuracy` (`ports.py:63-70`); `sagemaker.py:258-266` fills them from `metrics.json`. The tarball ships `features.py`, `families.py`, `baseline.py` as package `aioac_core` (`sagemaker.py:28,67-78`).

**Saved model, versions, use.** The paid model is saved as `models/<project>/<run>.joblib`, quality JSON = `result` (`training.py:164-173`); `model_versions.record_new_model` (`services/data/models.py:52-67`) records `verified_value`, `passed`, `family`. `model_use` loads the pipeline and reads `pre.transformers_` and `pipeline.classes_` (`model_use.py:45-49,76,169`), predicts one record or a CSV (`:249-289`), adds `probabilities` and `confidence` when `predict_proba` exists (:242,260-262,286-287).

**Cost samples.** `baseline.sample_timings` times `families.build(family, ...)` and `fit` on 5/10/20% (`baseline.py:78-91`); `cost.project_seconds` fits log-log time vs rows with slope clamped to 1.0 to 2.0 (`cost.py:14,33-48`); `quotes.create_quote` reads `forecast.pilot["cost_samples"]` and pins `family` and `dataset_version_id` (`quotes.py:132-143`). The fee is `ceil(success_fee_percent * compute)` (`quotes.py:135-138`).

### 1.2 Every place that assumes classification

| # | Where | Assumption |
|---|---|---|
| A1 | `baseline.py:9,70` | score is `accuracy_score` |
| A2 | `baseline.py:53-58`, `compare.py:90-95`, `verification.py:72-74`, `pilot.py:42`, `train.py` via `_split` | stratified split / `StratifiedKFold` on the target (silently falls back on error) |
| A3 | `baseline.py:71`, `compare.py:108`, `train.py:78` | "simple guess" = majority class of the training rows |
| A4 | `baseline.py:40-50`, `compare.py:244` | rare-group recall needs discrete groups |
| A5 | `families.py:12-14,57-59` | only `LogisticRegression`, `RandomForestClassifier`, `HistGradientBoostingClassifier`; `FAMILIES`, `PLAIN_NAMES`, `PILOT_SIZE`, `FULL_SIZE` are classifier-only (:18-24) |
| A6 | `pilot.py:49` | pilot score `(predict == y).mean()` |
| A7 | `pilot.py:68-69`, `routes/forecast.py` (`0 < target < 1`) | target is a rate in (0,1) |
| A8 | `pilot.py:82`, `tables.py:161` | `Forecast.metric` fixed to "accuracy" |
| A9 | `pilot.py:61` (`data_issues`) | baseline keys `accuracy`, `simple_guess_accuracy`, margin 0.03 |
| A10 | `forecast.py:39,51` | error is `1 - accuracy`; finite-test term is binomial |
| A11 | `forecast.py:73-81` | wording "out of 100 right" |
| A12 | `verification.py:16,98-101` | `accuracy_score`, metric string "accuracy" |
| A13 | `training.py:158-160` | `passed = value >= target` (fine for any higher-is-better score); result keys `accuracy`, `simple_guess_accuracy` |
| A14 | `ports.py:63-70` | `TrainingResult.accuracy`, `.simple_guess_accuracy` |
| A15 | `train.py:32,54,77-84`, `sagemaker.py:258-261` | accuracy metric, `_split`, majority guess, `metrics.json` keys |
| A16 | `insights.py:48-50,87-96` | `minority_share` from `value_counts`; `trust_level` = accuracy lift |
| A17 | `profile.py:97-124,139-166` | target "category" vs "number"; `_predictive_accuracy` is majority vote; `cat_target` branches |
| A18 | `compare.py:207` | `permutation_importance(..., scoring="accuracy")`; `verdict` says "points right" |
| A19 | `model_use.py:45-49,169,242,260-262` | `pre.transformers_` num/cat shape; `classes_`; `predict_proba`; `accuracy` keys at :152-153,194-196 |
| A20 | `explain.py:14-16,53,101-104` | `accuracy` curve key, out-of-100 wording, "simple guess" |
| A21 | `agent/tools.py:349-350,411,427`, `agent/blocks.py:58`, `history.py:14`, `share.py:62` | read `accuracy` / `simple_guess_accuracy` / `right_out_of_100` |
| A22 | `agent/target.py` | "N out of 100" regexes; the user must name the target |
| A23 | `features.py:8-17,49-55` | `target` is required; a unique date column is "id-like" and dropped; `drop_duplicates` removes legitimate repeated time rows |
| A24 | `datasets.py:34-47`, `tables.py:82` | a target must be chosen at select; `DatasetVersion.target_column` is nullable but treated as set everywhere |
| A25 | `cost.py:14`, `quotes.py:132-143` | time vs rows slope clamped to 1..2 (too low for some unsupervised estimators) |
| A26 | `gate.py:97-99` | pins checked: dataset version and family; NOT task type |

`Project.task_type` exists, nullable, unused (`tables.py:53`).

---

## 2. Design per task type

### 2.0 The internal score contract (applies to all five)

The money pipeline needs ONE thing from a task type: a **higher-is-better number `score` in [0,1]** measured on held-out rows, with a **simple-guess score** on the same rows. `extrapolate` works on `error = 1 - score`; `training.py:158` compares `score >= target`. If every task type produces that contract, the pilot, forecast, eligibility, quote, hold, verify and settle code stays structurally unchanged. The user never sees the raw score for non-classification types: wording is per type (section 5 and `TaskKind.wording`).

Each task also returns an `extras` dict of plain-unit numbers (a typical error in dollars, groups found, flag rate) used only for wording.

Hard honesty rules for all types: a score is a measurement on held-back rows, never a promise; the simple guess is shown next to it; estimates are labelled; the locked rows are scored once.

### 2.1 `classification` (built) plus improvements

Data: a target with at most 20 distinct values or bool (`profile.MAX_CATEGORY_TARGET`, `profile.py:18`) or a text column; two or more groups; at least 500 usable rows to sell (`forecast_min_rows`).

Families (unchanged): logistic regression, random forest, `HistGradientBoostingClassifier`.

Score: accuracy (unchanged). Simple guess: majority class of training rows. Split: stratified. Locked: stratified random, seed 7.

**Improvement: rare-group catch rate.** When the smallest group is under 20% of rows (`RARE_GROUP_BELOW`, `baseline.py:37`), accuracy rewards ignoring them (a "99 out of 100" model that never finds the 1 in 100). For such targets:
- `metric_name = "rare_group_caught"`, `score` = recall of the smallest group on held-out rows; simple guess = 0 (always say the common answer). Plain: "caught N out of 100 of the rare ones".
- Applies only when the user's goal is about the rare group (agent confirms: "find the few who will leave"). Otherwise accuracy stays the score and the catch rate is shown as an extra (as `rare_group_caught` is today, `tools.py:352`).
- Pilot: `_score` takes a `metric` function (A6). The binomial finite-test term uses the rare-group count: `p*(1-p)/max(n_rare_locked, 1)` where `n_rare_locked = round(locked_rows * smallest_share)` (inferred). Requires at least 30 rare rows in the work rows, otherwise not eligible with a plain reason.
- Verification: `verify_model` returns recall of that group; `metric` string says which group. The group label is stored (`extras.rare_group`).
- Tests: classification golden numbers must be byte-identical when the metric is accuracy.

### 2.2 `regression` (a number)

**Target typing.** A numeric column (or text that parses as numbers at 90%, `NUMERIC_SHARE`, `features.py:5`) with MORE than 20 distinct values (`MAX_CATEGORY_TARGET`) is `regression`. 20 or fewer distinct numeric values stays `classification` (profile rule unchanged: '0'/'1', 1 to 5 stars are groups) and the agent may offer "treat this as a number instead". The decision is made by one pure function `tasks.infer_task_type(df, target, goal_text)`; the user's goal words ("price", "how much", "how many") only break ties and are confirmed in chat. Dates, IDs and constant columns are not valid targets.

**Readiness checks** (new findings, same `{kind, text}` shape): enough rows (same row thresholds); spread (target is not almost constant: coefficient of variation under 1% is a NOTE and not sold); heavy skew or outliers (top 1% of rows account for a large share of the total: NOTE "a few very large values may dominate"); share of zeros; negative values allowed; missing target rows dropped and counted. `minority_share` (A16) is replaced by `target_spread` and `target_skew`. Grade penalties same scale.

**Families** (scikit-learn): `ridge` (`Ridge` after the existing imputer and `StandardScaler`, plain "a simple straight-line model"), `forest` (`RandomForestRegressor`, "a forest of decision trees"), `boosting` (`HistGradientBoostingRegressor`, "a boosted-trees model"). Same `PILOT_SIZE` and `FULL_SIZE` shape. Optional later: log-transform of a skewed target via `TransformedTargetRegressor` (plain: "prices are modelled on a log scale"; inferred, evaluate before shipping).

**Split.** Plain random 80/20 (`train_test_split` without `stratify`), `KFold` in the pilot. (To avoid leaking near-duplicates, rows are already de-duplicated by `prepare_features`.)

**Score and simple guess.** Define:
- `guess_error` = mean absolute error of always predicting the training mean (fallback: median if skewed; fixed per task as the MEAN so wording says "the average").
- `error` = mean absolute error of the model on held-out rows.
- `score = clip(1 - error / guess_error_ref, 0, 1)` ("how much closer than a simple guess"), where `guess_error_ref` is **frozen from the work rows at pilot time and stored on the forecast** (`pilot.score_scale.guess_error`). Freezing the denominator keeps a user's target stable between pilot and verification and lets code convert "off by no more than $X" into a target score: `target = 1 - X / guess_error_ref`.
- Simple-guess score is 0 by construction; `extras.simple_guess_error` is shown in dollars.

Alternative considered: R-squared (what the earlier doc proposed). Rejected as the internal score because squared error is dominated by outliers and does not map to a dollar target; kept as a secondary extra ("explains about N out of 100 of the ups and downs"), shown only in detail views. Open question OQ2.

**Plain wording.** "On average off by about $X (an estimate). A simple guess, always the average, is off by about $Y." Target: "off by no more than $X on average", stored as a score; the conversion is shown for approval. Never "N out of 100 right". Units: the target column name and an optional unit/currency symbol inferred from the column name (inferred; fall back to the bare number).

**Free test, pilot, learning curve.** Free test: one 80/20 fit of the forest, report error vs guess error (`BaselineOutcome` gains `score`, `guess_error`, `error`). Pilot: same successive halving on the three regressors, 3-fold `KFold`, learning curve of `score` against training rows; `extrapolate` unchanged except the finite-test term (see 4.4): for a mean absolute error the standard error of the held-out error is `sd(|e|)/sqrt(locked_rows)`, divided by `guess_error_ref` to stay on the score scale; `sd(|e|)` comes from the cross-validation residuals of the survivor and is stored as `pilot.score_scale.abs_error_sd`. Eligibility: same `forecast_min_confidence` and a minimum score margin over the guess (score at least 0.05, else "the columns barely help predict this number").

**Locked verification.** Random 80/20 on the root version, same inheritance. `verify_model` returns `{metric: "error_reduction", value: score, rows, extras: {error, guess_error, unit}}` using the STORED `guess_error_ref`; `passed = value >= target` unchanged. A model that does worse than the guess scores 0 and misses.

### 2.3 `forecast` (a number over time)

Hardest honesty case: rows are not exchangeable, so the random-fold learning curve and random locked set (A2, `verification.py:72`) are INVALID. Everything time-related must be time-ordered.

**Data requirements and typing.** One column that parses as dates (or a regular integer period index), one numeric target, optional extra columns known in advance (promotions, holidays, price). v1 supports ONE series (optionally aggregated: sum or mean per period when several rows share a date; the agent asks which). Panels (store x date) are out of scope v1 (OQ4). Frequency is inferred (`pd.infer_freq`, tolerating gaps by regularising to the dominant step). Required: at least 3 full seasonal cycles when a season is detected (e.g. 36 months of monthly data) and at least 100 periods to sell (inferred; owner to confirm, OQ5). `infer_task_type`: a date-like column plus the user's goal mentioning the future ("next month", "over time", "forecast") or an explicitly chosen time column. The detected time column and horizon `H` (periods ahead, default one season or 12) live in `projects.task_config` (section 3).

**Readiness checks.** Gaps and duplicate timestamps (NOTE with counts), irregular spacing, very short history, flat or all-zero stretches, strong trend vs seasonality (detected simply by autocorrelation at common lags), extreme last values, and **extra columns that are not known at forecast time** (leakage: using today's sales to explain today's sales; the agent must ask, skill text, not code).

**Features.** Lags (1, 2, 3, season length), rolling mean and std over recent windows (computed with `shift(1)` so no row sees itself), calendar parts (month, day of week, week of year), a time index, and the user's known-in-advance columns. A pure `tasks.forecast.make_features(df, time_col, target, freq)`. `prepare_features` must keep the time column (A23): add a `keep` argument; also skip `drop_duplicates` for forecast (repeated consecutive rows are real).

**Families.** Same regressor families as section 2.2 on the lag features (`ridge`, `RandomForestRegressor`, `HistGradientBoostingRegressor`), plus two **naive baselines that are also the simple guess**: `last` ("same as last period") and `seasonal` ("same as this time last cycle", when a season is found), and `average` (mean of the training window). The pilot also races the naive baselines; if a naive baseline wins it is reported honestly ("a simple repeat of last period beat our models") and the run is not sold as a model (a naive model is not worth money).

**Strategy.** Recursive one-step forecasting (feed predictions back) for H steps; direct multi-horizon is a later option (inferred; recursive is simpler and error compounding is measured by the same evaluation).

**Split and score.** Order by time. Work = older rows; locked = the newest `max(20% of periods, 2*H)` periods (at least H). No shuffling. In the free test and pilot, use **rolling-origin (expanding-window) cross-validation** on the work rows: 3 origins, each trained on everything before the origin and tested on the next H periods. Evaluation never feeds actuals from the test window back as inputs within one H-step forecast.
- `error` = mean absolute error across the H-step forecasts (a mean over several origins in the locked block, each forecast starting from data the model was not trained on).
- `guess_error_ref` = the error of the BEST naive baseline (last, seasonal, average) on the same windows. `score = clip(1 - error / guess_error_ref, 0, 1)`: "better than the best simple repeat". So the score is honest: beating the naive baselines is what you pay for.
- Plain: "typically off by about N orders per month, a simple repeat of last month is off by about M (estimates)". Target: "off by no more than N", converted to a score as in regression.

**Learning curve.** The curve is over the number of training periods (expanding windows), not random subsets. The extrapolation maths is unchanged but gets a stronger conservative term: forecast quality can also depend on future regime changes, so add a fixed extra sigma for forecast (e.g. +0.03, tuned on real data, inferred). The pilot's random sampling (`pilot.py:92`, `work.sample`) is invalid here: the forecast pilot takes the last `P` periods of the work set and places its origins inside them, never random rows.

**Locked verification.** The newest block, scored once. Because it is the newest data it is also the most relevant to a user predicting the future; it can never be used to train (the paid run trains on work periods only; after verification, a refit on all rows for the delivered model is a later option, OQ6). Children inherit (`row_keys` matching, `verification.py:60-69`) works by content; require the time column in the key set.

**Prediction shape** (section 5): next N periods with a typical-error band.

### 2.4 `grouping` (no answer column)

**Data requirements and typing.** No target. At least 200 rows and at least 2 usable columns after dropping IDs and constants. Detected from the goal ("group", "segments", "types of customers") or chosen by the user. `target_column` is NULL and the pipeline must accept `target=None` (A23, A24).

**Readiness checks.** Row and column counts; too many text columns with high cardinality (one-hot explosion; NOTE and columns dropped); heavy missing values; one numeric column dominating scale (handled by `StandardScaler`, NOTE); near-duplicates; and "the records look like one blob" (a quick silhouette of k=2 under 0.1 is a finding: "there may be no clear groups").

**Families** (scikit-learn): `kmeans` (`KMeans`, n_init="auto", fixed seed; "groups around centre points"), `minibatch` (`MiniBatchKMeans`, used above ~50,000 rows; same plain name), `gmm` (`GaussianMixture`, "overlapping groups", only up to ~10,000 rows and ~50 dense columns). Features: same imputer, `OneHotEncoder` (min_frequency to cap width), `StandardScaler` on numbers; optional `PCA` to 20 components for wide data.

**Choosing k.** Not by silhouette alone (it favours k=2). For k in 2..8 (cap by rows), compute silhouette on a sample (at most 5,000 rows) AND stability: fit on two disjoint bootstrap halves, assign the same rows with both models, adjusted Rand index (ARI). Pick the k with the best `0.5*silhouette_clip + 0.5*stability`, subject to every group holding at least 2% of rows. If the best combined value is under a floor (stability under 0.5), report "no clear groups".

**Score and simple guess.** `score = stability` (mean ARI over 5 repeated half-splits, clipped to [0,1]) combined with separation: `score = min(stability, max(silhouette, 0) * 2)` clipped (inferred; tune on synthetic blobs and on uniform noise; the unit test of "pure noise scores under 0.3, three clear blobs over 0.7" is the acceptance bar). Simple guess: random labels with the same group sizes (score about 0) or "one big group" (score 0). Plain: "how clearly your records fall into groups, and whether the same groups appear when we look at a different half".

**Free test, pilot, learning curve.** Free test: the stability/silhouette of the chosen k on the work rows (no held-out truth exists). Pilot (free): tries the families and k on a sample; "learning curve" is stability against sample size: if stability rises with rows it will probably be higher on the full data; if it is flat it is a property of the data. The forecast is "the chance the full run finds groups that hold up (score at least `T`)" with `T` set by the system (default 0.6), not by the user (the user-named-target guard `target.py` does not apply: there is no user target). The forecast row stores `target = T` and `reason` text says so.

**What locked verification means.** There is no ground truth, so the locked rows can verify only STABILITY on unseen rows: (1) assign locked rows to the model's groups and measure silhouette on them; (2) fit a fresh model on the locked rows (when at least 200) and measure ARI against the paid model's assignments of those rows. This proves "the groups hold up on records the model did not see", NOT that the groups are meaningful or useful. The UI must say exactly that. **Money rule (recommended, OQ1):** grouping and unusual are **compute-only**: the quote has `fee_cents = 0`. This needs no payment code change: `settle` computes `fee = min(ceil(pct * compute), pay.fee_amount_cents)` (`payments.py:147`), so a hold with `fee_amount_cents = 0` gives `fee = 0` and the state goes to `fee_skipped`. The hold equals the compute cap. The gate and quote tests prove it.

**Prediction shape** (section 5): group label plus a short plain description of each group (top numeric columns that differ most from the overall average, built by code).

### 2.5 `unusual` (anomaly detection)

**Data requirements and typing.** No target. At least 300 rows, at least 2 usable columns. If the file contains an obvious label column ("is_fraud", "anomaly") the agent should say plainly that this is a yes/no question with known answers and offer `classification` with the rare-group catch rate (2.1); that is far better than guessing from no labels.

**Readiness checks.** As grouping plus: how many records are exact duplicates, columns with one dominant value, and a rough view of how many records look unusual by a robust z-score on any column (a plain "about N in 100 look very different" finding).

**Families:** `isolation` (`IsolationForest`, default: fast, handles mixed scaled data; "records that are easy to separate from the rest"), `lof` (`LocalOutlierFactor(novelty=True)`, "records far from their neighbours", up to ~20,000 rows), `ocsvm` (`OneClassSVM`, "records outside the usual shape", up to ~5,000 rows because of O(n^2) to O(n^3) time).

**Contamination.** An input, not a discovery: "about how many in 100 do you expect to be unusual?" default 1 in 100, bounds 0.1% to 20%, stored in `task_config.contamination` and shown plainly. It decides how many records are flagged; it is NOT a finding.

**Score and simple guess.** Without labels, accuracy cannot exist. Two honest measurements on held-out rows:
1. **Stability** of the flagged set: fit on two disjoint halves of the work rows, flag the same held-out rows with both, Jaccard overlap of the flagged sets (clipped to [0,1]).
2. **Calibration:** the share flagged on held-out rows should be close to the contamination (within a band of about 2x).
`score = stability` if calibration holds, otherwise scaled down. Simple guess: flag the same share of rows at random; expected stability is about the flagged share, near 0 for 1%. Alternative simple-rule baseline: flag by the largest robust z-score on one column; reported as an extra. Plain: "we can show which records look unlike the rest, and we get the same ones when we look at a different half of the data. We cannot know whether they are mistakes, fraud or just rare."

**Pilot and forecast.** Same as grouping: stability against sample size, system target `T` (default 0.5), eligibility on the forecast, compute-only. **Locked verification:** the same two measurements on locked rows, plus the flag rate; reported side by side with the forecast. If the user supplies a few known-unusual records later (optional), report "caught N of M known ones" as an extra (never a promise).

**Prediction shape** (section 5): a "looks unusual" flag and a score, with the reasons (the columns furthest from typical).

### 2.6 Summary table

| | score (0..1, higher better) | simple guess | split | locked | fee |
|---|---|---|---|---|---|
| classification | accuracy, or rare-group recall | majority class / 0 | stratified random | stratified random | yes |
| regression | error reduction vs average | 0 (always the average) | random | random | yes |
| forecast | error reduction vs best naive repeat | 0 (best naive) | time-ordered, rolling origin | newest block | yes (OQ1) |
| grouping | stability and separation | random / one group | half-splits | stability on unseen rows | no (compute-only) |
| unusual | flagged-set stability | random flags | half-splits | stability and flag rate on unseen rows | no (compute-only) |

---

## 3. Data model changes

No migrations in this project. Everything is added with `python -m app.db.init --check` then `--upgrade --yes` (`specs/db.md` 4a): only NEW nullable columns (or NOT NULL with a default) are allowed; existing columns are never altered. All new task columns are nullable and read as `classification` when null, so old rows and old behaviour are untouched. Owner note for Supabase: no new table, so no new RLS step (a new table would need it).

| Table | Change |
|---|---|
| `projects` | `task_type` EXISTS (`tables.py:53`), start writing it. NEW `task_config` JSON nullable: `{time_column, horizon, frequency, contamination, k_min, k_max, aggregate, unit}` (only keys that apply) |
| `baseline_runs` | `accuracy` and `simple_guess_accuracy` are NOT NULL floats (`tables.py:107-108`): for non-classification they hold `score` and `simple_guess_score` as ALIASES (transition rule, below). NEW nullable `task_type`, `metric_name`, `extras` JSON |
| `forecasts` | `metric` EXISTS (`tables.py:161`, default "accuracy"): used as the metric name. NEW `task_type`, `baseline_value` (float, the simple-guess score) |
| `quotes` | NEW `task_type` (PINNED like `family`) and nothing else; `fee_cents = 0` expresses compute-only (no flag needed) |
| `training_runs` | NEW `task_type`, `metric_name` (the result JSON carries values) |
| `models` | NEW `task_type`, `metric_name`, `baseline_value`; `verified_value` (`tables.py:225`) stays the locked-rows score, no new `metric_value` column |

Gate (HUMAN REVIEW, tiny): in `gate.py` next to the family pin (`:97-99`), refuse `START_TRAINING` if `quote.task_type` is set and differs from `project.task_type` ("the task changed after this price was quoted").

**JSON shapes** (all new keys are additive; old keys stay):

`projects.baseline_result` (served as-is by the API; keeps `accuracy`, `simple_guess_accuracy`; for non-classification these two are aliases of `score` and `simple_guess_score` so any old client or share page keeps working; the UI switches wording on `task_type`):
```json
{"accuracy": 0.62, "simple_guess_accuracy": 0.0,
 "task_type": "regression", "metric": "error_reduction",
 "score": 0.62, "simple_guess_score": 0.0,
 "extras": {"error": 18400, "guess_error": 48500, "unit": "$", "rows_test": 840}}
```
`forecasts.pilot` (adds):
```json
{"score_scale": {"guess_error": 48500, "abs_error_sd": 21000},
 "task_type": "forecast", "horizon": 12, "frequency": "MS",
 "origins": 3, "naive_scores": {"last": 0.0, "seasonal": 0.12, "average": -0.4},
 "learning_curve": [{"training_rows": 40, "accuracy": 0.31}]}
```
Keep the learning-curve key `accuracy` (read by `explain.py:53`, `compare.py:162`, `tools.py:427`) and add `score` with the same value; consumers move to `score` slice by slice.

`models.quality` / `training_runs.result`:
```json
{"accuracy": 0.62, "simple_guess_accuracy": 0.0, "runtime_seconds": 3.1,
 "task_type": "regression", "metric": "error_reduction", "score": 0.62,
 "extras": {"error": 18400, "guess_error": 48500, "unit": "$"},
 "verification": {"metric": "error_reduction", "value": 0.60, "rows": 840, "target": 0.55, "passed": true,
                  "extras": {"error": 19400, "guess_error": 48500}}}
```
`verification.value` and `passed` keep their meaning, so `model_versions.verified_value/passed` (`models.py:12-24`), `payments.settle` (`:149`) and `explain` need no structural change.

`TrainingResult` (`ports.py:63-70`) gains `score: float | None = None`, `simple_guess_score: float | None = None`, `metric: str = "accuracy"`, `extras: dict = {}`; `accuracy`/`simple_guess_accuracy` stay and are filled with the aliases.

---

## 4. Pipeline refactor plan

### 4.1 `TaskKind` strategy

New package `backend/app/services/data/tasks/`:

```
tasks/__init__.py        TASKS registry, infer_task_type(), get(task_type)
tasks/base.py            TaskKind Protocol, Score dataclass, shared helpers
tasks/classification.py  moves today's behaviour verbatim (default)
tasks/regression.py
tasks/forecast.py        features, rolling origin, naive baselines
tasks/grouping.py
tasks/unusual.py
```
`TaskKind` (pure: pandas and scikit-learn only; no app, no DB, no storage imports):

- `id`, `plain_name`, `needs_target: bool`, `supports_fee: bool`.
- `check_target(df, target, config) -> TargetCheck` (typing rules, plain refusals).
- `prepare(df, target, config) -> DataFrame` (wraps `features.prepare_features` with `keep` columns).
- `split(df, target, config, share, seed) -> (train, test)` and `folds(X, y, config, n)`.
- `families: tuple[str, ...]`, `build(family, X, size) -> estimator/Pipeline`, `PILOT_SIZE`, `FULL_SIZE`, `plain_name(family)`.
- `score(model_or_labels, X_test, y_test, ctx) -> Score(value, simple_guess, extras)` where `ctx` carries the frozen `score_scale` and config.
- `simple_guess(y_train, y_test, ctx)`.
- `finite_test_sigma(score, locked_rows, ctx)` (replaces the binomial term, A10).
- `cost_fit(model, X, y)` timing helper for `sample_timings`.
- `predict_one(model, record_frame, ctx)` and `predict_batch(...)` returning the shapes in section 5.

App-side (not shipped to SageMaker) wording lives in `services/data/task_wording.py`: `plain_score(task, value, extras)`, `plain_guess`, `plain_target`, `target_from_text`. This keeps vocabulary out of the shipped tarball.

### 4.2 What moves behind it

| Today | Becomes |
|---|---|
| `baseline._split`, `compare._split`, `verification` split, `pilot._score` folds | `TaskKind.split` / `folds` |
| `baseline.fit_and_score` scoring (:70-71), `rare_group_recall` | `TaskKind.score` / `simple_guess`; `rare_group_recall` stays in `tasks/classification.py` and is re-exported from `baseline.py` for callers |
| `families.build`, `FAMILIES`, `PLAIN_NAMES`, `PILOT_SIZE`, `FULL_SIZE` | per-task tables; `families.py` keeps its public names for classification (`build(family, X, size, task="classification")`) |
| `pilot._score` (:39-50), `pilot.run_pilot` sampling (:92) | `TaskKind.score` over folds; forecast uses origins, not random sampling |
| `forecast.extrapolate` finite-test term (:51) | `finite_test_sigma` passed in (default = binomial; classification output is byte-identical) |
| `verification.prepare_split` (:70-77), `verify_model` (:98-101) | dispatch on task |
| `insights.analyze` classification checks (:48-50) | `TaskKind.readiness_checks` (new) plus common checks kept |
| `compare` / `profile` target part | per-task `describe_target`; compare for regression uses `r2`/MAE permutation scoring (`scoring="neg_mean_absolute_error"`); not offered for grouping/unusual (OQ7) |

### 4.3 Files that ship verbatim to SageMaker

`SHARED_MODULES = ("features.py", "families.py", "baseline.py")` is copied flat as `aioac_core/<name>` (`sagemaker.py:28,76-77`), and `baseline.py`/`families.py` use relative imports (`baseline.py:13-14`). New rule (HUMAN REVIEW: packaging):
- Add the whole `tasks/` directory to the tarball (`tar.add(SERVICES_DIR / "tasks", arcname="aioac_core/tasks", recursive=True)`, excluding `__pycache__`) and import inside it only with relative imports (`from .. import features`). Every shipped file stays stdlib + numpy + pandas + scikit-learn + joblib only.
- Add a unit test (extend `tests/unit/test_architecture.py`) that parses every shipped file with `ast` and fails on any import outside that set or any `from app...`.
- Keep `baseline._split`, `baseline.fit_and_score`, `families.build` import-compatible: `train.py` imports `aioac_core.baseline._split` and `aioac_core.families` (`train.py:34-36`). Keep these names as thin wrappers over `tasks.*` for classification.
- scikit-learn is pinned `1.9-0` (`specs/integration-testing.md`); new estimators must exist in 1.9: `IsolationForest`, `LocalOutlierFactor`, `OneClassSVM`, `GaussianMixture`, `MiniBatchKMeans`, `HistGradientBoostingRegressor` do (inferred from long-standing APIs; confirm with an import smoke test inside the container image in the paid test).

### 4.4 Train script and `task_type`

`sagemaker.py:_create_job` adds hyperparameters, JSON-encoded like the others: `task_type`, and only when relevant `time_column`, `horizon`, `contamination`, `n_clusters`. The script reads them in `main` like `family` (`train.py:104`), defaulting to `classification` when absent, so old jobs behave as today. `train()` calls `tasks.get(task_type)` for prepare, split, build and score. Partial-model-on-SIGTERM stays a forest-only feature for classification; regression forest can reuse the warm-start batching (`RandomForestRegressor` supports `warm_start`, inferred: keep batching for it); everything else fits once and saves at the end. `metrics.json` gains `task_type`, `metric`, `score`, `simple_guess_score`, `extras`; `sagemaker.py:258-266` fills the new `TrainingResult` fields. Unsupervised tasks have no `target`: the script must no longer `raise SystemExit("missing --target")` (`train.py:101-102`) when `task_type` needs none.

`LocalBackend.run` and `ports.TrainingBackend.run` get a `task_type="classification"` argument (and `config`) like `family` (`ports.py:77-80`, `backend.py:122`); `training.execute_run` passes `quote.task_type or project.task_type or "classification"`. Note: `execute_run` currently reads `version.target_column` (:133,153): for unsupervised tasks the target is None and `verify_model` takes `target=None`.

### 4.5 Free-test, forecast, eligibility wiring

- `analysis.baseline_detailed` stores the generic JSON (section 3) and still the aliases; `trust_level` becomes `tasks.trust(task, grade, score, simple_guess)` (classification unchanged: lift 0.15/0.05).
- `pilot.run_pilot`'s target check `0 < target < 1` stays: the score is always in (0,1). For grouping/unusual the target is the system minimum.
- `forecast.not_eligible_reason` takes plain wording from `task_wording`; thresholds stay in `config.py` (`forecast_min_confidence`, `forecast_min_rows`; add per-task minimum rows: forecast 100 periods, grouping 200, unusual 300).
- `create_quote` is unchanged in structure: copies `forecast.task_type` onto the quote; for `supports_fee=False` tasks sets `fee_of(...) = 0` (the only quote code change; HUMAN REVIEW) and stores a breakdown note.

### 4.6 Cost samples per task

`baseline.sample_timings` becomes `TaskKind.cost_fit`. Time is measured on the chosen family at 5/10/20% of rows; for `forecast` time includes feature building; for unsupervised, k is fixed to the chosen k and GMM/OCSVM scale worse than the clamp allows (`cost.py:14` clamps the slope at 2.0; OneClassSVM can be closer to 2 to 3). Mitigation: row caps per estimator (2.4, 2.5) and a per-task slope upper bound (`SLOPE_RANGE` per task, default (1.0, 2.0), `ocsvm` (1.0, 3.0), inferred). The cap-to-runtime hard stop (`MaxRuntimeInSeconds`) still protects spend whatever the estimate says (`training.md` 2b).

---

## 5. Model use per task type

All stay free (no gate, no money) and keep the existing safety rules: row/byte limits (`model_use.py:23-24`), unknown-column errors, estimate note.

`model_use.Loaded` (`:42-49`) reads `pre.transformers_` and `classes_`. Make it task-aware: `Loaded.task_type` comes from `Model.task_type` (default classification). KMeans/GMM/IsolationForest pipelines are `Pipeline([("pre", ...), ("est", ...)])` using the same `pre` step and name, so `_imputer_values`, `_choices`, `_frame` keep working; the final step's name is read as `named_steps[-1]`, not `"clf"`. For forecast the model object is a small wrapper (`ForecastModel` with the regressor pipeline, `freq`, `lags`, last-window history) saved with joblib; it must carry the training history needed for lags and cannot be a bare Pipeline.

| task | `POST /predict` one record | `POST /predict-batch` | `GET /model` (describe) |
|---|---|---|---|
| classification | unchanged: `{prediction, probabilities, note}` | unchanged: `prediction`, `confidence` | unchanged: `classes` |
| regression | `{prediction: 412000, typical_error: 18400, range_low, range_high, unit, note}`; `probabilities` null; the band is a typical-error band (prediction ± mean absolute error from the locked rows, labelled an estimate; not a guaranteed interval) | adds `prediction` (number) and `typical_error` columns; no `confidence` | `classes: []`, `score` wording "off by about $X", `simple_guess_error` |
| forecast | body `{periods: N}` (default `H`, capped at `H`... up to 2*H allowed with a warning); returns `{periods: [{date, value, low, high}], note}` using the recursive forecast from the stored history; no "one record" form | accepts a CSV with new known-in-advance columns for future dates (optional); returns the same table | shows time column, frequency, horizon, last date in the data |
| grouping | `{group: 2, group_name: "Group 3", description: "higher spend, fewer visits", distance}` | adds `group` column and `group_name` | lists groups: size share, plain description (top differing columns, built by code), `classes` is the group list |
| unusual | `{looks_unusual: true, score: 0.83, reasons: ["income far above typical"], note}` where `score` is a 0..1 rank against the training scores | adds `looks_unusual` and `unusual_score` columns, sorted option in the UI | describes the contamination used and the flag rate on unseen rows |

Plain text for descriptions is built by code from stored statistics (never a model); column names are untrusted text (`context.mark`). `_predict_frame` (`:237-246`) calls the task's `predict` (`predict_proba` only for classification). The "usable" check (`:76`) stays. `download` is unchanged (joblib + sklearn version header).

`explain.py`, `compare.py` and `profile.py` need per-task wording (A17 to A20); until a task's slice ships, `explain_result` for that task returns only the neutral facts it can state (score vs guess, money), never "right out of 100".

---

## 6. Slices

Order: each slice is small, independently shippable, tests first, default behaviour unchanged (golden classification output must stay byte-identical). Run `pytest` and the demo check (`pytest tests/e2e/test_payments_and_demo.py`) before calling any slice done. Payment files change only in S5 (gate pin), S7 and S12 (quote fee), all tiny and flagged.

**S0. Audit-test skeleton (free; no behaviour change).** Files: `tests/unit/test_task_assumptions.py`, `tests/e2e/golden/` fixtures, `tests/unit/test_architecture.py` (shipped-module import check). Tests FIRST: golden JSON of today's classification baseline, pilot, forecast, quote, verification, training result on the synthetic churn fixtures; an AST test that every file in `SHARED_MODULES` (and later `tasks/`) imports only stdlib/numpy/pandas/sklearn/joblib; a test that fails when a new `task_type` is added without a registry entry. Acceptance: tests pass on current code; later slices must keep them green.

**S1. `task_type` plumbing and target typing (free).** Files: `tasks/__init__.py`, `tasks/base.py`, `tasks/classification.py` (moves), `services/data/task_type.py` (`infer_task_type`), `datasets.py:select_candidate`, `analysis.py`, `projects.task_config`, `db/tables.py` + `--upgrade`, `profile.py` (typing reuse), `agent/tools.py` (`unsupported_task` reply until each type ships). Tests FIRST: unit for `infer_task_type` on table of columns (0/1, 1-5 stars, price, dates, no target); `--check`/`--upgrade` test adds the columns; golden unchanged. Acceptance: the project records `task_type`; classification unchanged; regression/forecast/grouping/unusual goals get the plain reframe or "not yet" reply with no search or quote.

**S2. Regression free test and baseline (free).** Files: `families.py` (regressors, `task` argument), `tasks/regression.py`, `baseline.py` wrappers, `insights.py`/`analysis.py` (generic baseline JSON, regression readiness findings, trust), `task_wording.py`, `features.py` (`target=None` and `keep`). Both `families.py`/`baseline.py` ship to SageMaker: keep imports clean. Tests FIRST: unit for score (known arrays), guess error, frozen scale, readiness findings (skew, constant target), plain wording has no jargon; contract: `families.build("forest", task="regression")` returns a `RandomForestRegressor`; golden classification unchanged. Acceptance: free test on a numeric dataset returns "off by about X vs Y" and `baseline_result` has the aliases.

**S3. Regression pilot and forecast (free; light HUMAN REVIEW: eligibility).** Files: `pilot.py`, `forecast.py` (`finite_test_sigma` argument), `routes/forecast.py`, `agent/target.py` (regression phrases; user must still name the target), `tasks/regression.py`. Tests FIRST: `extrapolate` with the default sigma is byte-identical; regression sigma matches a hand calculation; eligibility on a pure-noise numeric target is "not eligible"; learning-curve keys carry `score` and `accuracy`. Acceptance: forecast with band and confidence in plain dollars.

**S4. Regression training and verification (HUMAN REVIEW: verification, training, ports, SageMaker packaging).** Files: `verification.py` dispatch, `training.py` (result keys), `training_local/backend.py`, `ports.py` (`TrainingResult`, `task_type`), `train_script/train.py`, `sagemaker.py` (hyperparameters, tarball includes `tasks/`), `forecast` table column `task_type`, `models`/`training_runs` columns. Tests FIRST: e2e on the mock provider with a regression fixture: target met pays compute plus fee; target missed pays compute only; verification error voids everything; contract on mocked boto3 for the new hyperparameters and `metrics.json`; unit on the tarball listing. Then ONE live capped SageMaker regression job (`RUN_REAL=1 RUN_PAID=1`, about 1 cent) before release. Acceptance: a full regression run ends with the right captures and voids.

**S5. Quote pin and gate (HUMAN REVIEW: quotes, gate).** Files: `quotes.py` (copy `task_type`, no fee change yet), `gate.py:97-99` (task pin), `db/tables.py` quotes column. Tests FIRST: unit gate test: changing task after the quote is refused (409); quotes of old rows without `task_type` skip the check. Acceptance: quote, hold, train works for regression end to end.

**S6. Regression predict and model tab (free).** Files: `model_use.py`, `routes/screens.py` (shape only), `share.py`/`history.py`/`blocks.py` (read `score` + `task_type`; allow-listed public fields: add `task_type` and `metric`, never money). Tests FIRST: predict returns a number with `typical_error`, no probabilities; batch adds numeric columns; public share key-set test updated deliberately. Acceptance: try one record and CSV on a regression model.

**S7. Lopsided-class catch rate (free; HUMAN REVIEW only if `verify_model` changes).** Files: `tasks/classification.py`, `pilot.py`, `verification.py`, `analysis.py` (store `rare_group_caught`). Tests FIRST: finite-test term on the rare count; golden accuracy output unchanged.

**S8. Forecast: features, naive baselines, free test (free).** Files: `tasks/forecast.py`, `features.py` (`keep`, no dedupe), `projects.task_config`, readiness findings. Tests FIRST: lag features never look ahead (shift test), time-ordered split never shuffles, naive baselines on a synthetic seasonal series, a trend series where a regressor beats naive, a random-walk series where nothing beats naive (must not be sold).

**S9. Forecast: pilot, forecast, verification, training (HUMAN REVIEW: verification split).** Files: `verification.py` time-ordered locked block and inheritance, `pilot.py` (origins), `train.py` (time hyperparameters), local backend. Tests FIRST: locked rows are always the newest and never in work; a child version inherits the same block; e2e fee rules; one live paid job.

**S10. Forecast: predict (free).** `ForecastModel` wrapper, next N periods with band, batch with future known columns. Tests: dates continue the frequency; a gap-free series; band labelled an estimate.

**S11. Grouping (free test, pilot, training, predict).** Files: `tasks/grouping.py`, `profile`/`insights` (no-target readiness), `target.py` bypass for system target, `routes` (select without target). Tests FIRST: three blobs recover k=3 and stability over 0.7; uniform noise scores under 0.3 and is "no clear groups"; stability computation is deterministic. HUMAN REVIEW part: the quote for compute-only (S13).

**S12. Unusual (free test, pilot, training, predict).** Files: `tasks/unusual.py`. Tests FIRST: planted outliers are flagged in a synthetic set; stability high on structured data and low on noise; flag rate near contamination; ocsvm row cap enforced.

**S13. Compute-only quote for unsupervised types (HUMAN REVIEW: quotes, payments behaviour).** Files: `quotes.py` (`supports_fee` -> `fee_of = 0`), tests only for payments. Tests FIRST: `settle` with `fee_amount_cents=0` ends `fee_skipped` with the full remainder voided (mock provider), ledger has only the compute capture, the receipt text says "no success fee for this kind of task".

**S14. Agent, skills, evals, UI wording (free).** Out of this file's scope (see the frontend and agent task files); the backend exposes `task_type`, `metric`, `score`, `extras` and plain-wording helpers. Must include a shared `task_wording` test that no user-facing string contains "R2", "MAE", "silhouette", "F1", "split".

Dependencies: S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6; S7 any time after S1; S8 needs S2 (regressors); S9 needs S4/S5; S11 and S12 need S1 and S13 before they are sold; S14 follows each.

---

## 7. Risks, unknowns and open questions for the owner

**Risks**
1. **Time-series honesty (high).** A wrong split makes a forecast look wonderful and be useless. The time-ordered split, the naive-baseline score and the newest-block locked set are the defence; they need review before any forecast is sold.
2. **Unsupervised "verification" is weak by nature (high).** Stability is not usefulness. Wording must say so; the compute-only rule keeps us from charging a success fee for something we cannot truly verify.
3. **SageMaker packaging (medium).** Adding a package to the tarball is the first change to what ships since `1.9-0` was pinned; one mismatch fails a PAID job with a failure, the user pays $0 but we pay AWS. Hence the AST import test and one live capped run per task type.
4. **Score scaling for regression (medium, inferred).** Error reduction against a frozen guess error can be unstable on tiny or heavy-tailed targets; the clip at 0 and the "barely helps" gate mitigate; tune on real datasets (no real regression data has run).
5. **Cost estimates for slow estimators (medium).** GMM, LOF and OneClassSVM scale worse than the slope clamp (`cost.py:14`); mitigated by row caps and a per-task slope bound; real timings are unmeasured.
6. **Metric aliases (low).** `accuracy` keys holding a non-accuracy score could mislead a future reader; documented as aliases with `task_type`, removable once the frontend reads `score`.
7. **Existing rows (low).** Null `task_type` reads as classification everywhere; a test covers it.
8. **Time budget.** Not realistic before the 2026-11-12 deadline; this is post-hackathon work, as in `regression-and-task-types.md` section 0.

**Open questions for the owner**
- OQ1. Success fee: apply to regression and forecast (recommended: yes, same rule); grouping and unusual compute-only (recommended: yes). Confirm.
- OQ2. Regression score: "error reduction vs average" (this spec) or R-squared? And the display unit: mean error, or median ("typical")?
- OQ3. Target wording for regression and forecast: "off by no more than X" converted to a score by code, or "explain N out of 100"? (This spec: the first, shown for approval.)
- OQ4. Forecast scope: single series only in v1, or panels (store x date)? Aggregation default?
- OQ5. Minimum history to sell a forecast (this spec: 100 periods and 3 seasons) and the minimum rows for grouping (200) and unusual (300): confirm.
- OQ6. After verification, may the delivered forecast model be refit on all rows including the locked block (usually better, but then the shown score describes a slightly different model)?
- OQ7. Do `compare_models`, `explain_result` and clues apply to grouping and unusual, or are they classification/regression/forecast only?
- OQ8. Unusual: is a user-chosen contamination acceptable, or should the product always ask for a few known examples first?
- OQ9. Live paid SageMaker check per new task type (about 1 cent each): approve one per type?
- OQ10. Does the "grouping/unusual" system target `T` (0.6 / 0.5, inferred) look right, or should the user choose a clarity level in words (clear, some)?

---

## 8. Acceptance checklist

- [ ] S0 golden tests pass on unmodified code and stay green in every slice.
- [ ] `task_type` is written for every new project; null reads as `classification`.
- [ ] Every new DB column is nullable (or defaulted); `python -m app.db.init --check` then `--upgrade --yes` works on a copy of an old database; no new table.
- [ ] Each task type returns `score` in [0,1] and a simple-guess score on held-out rows; the money code only compares `value >= target`.
- [ ] No user-facing string contains F1, MAE, R-squared, silhouette, "split", "out of 100 right" for non-classification tasks; every estimate is labelled.
- [ ] Locked rows for `forecast` are the newest block and never in work; children inherit them.
- [ ] Locked verification for grouping and unusual is described as stability only, in the UI and the API note.
- [ ] Grouping and unusual quotes have `fee_cents = 0`; a settled run captures compute only and voids the rest; ledger append-only unchanged; idempotent webhook tests still pass.
- [ ] `START_TRAINING` refuses when the quote's `task_type` differs from the project's.
- [ ] Everything shipped to SageMaker imports only stdlib, numpy, pandas, scikit-learn, joblib (AST test); the tarball listing test includes `aioac_core/tasks/`.
- [ ] One live capped (`RUN_PAID=1`) SageMaker job per task type before it is sold; no job left running.
- [ ] Hard rules untouched: no paid work before a server-confirmed hold, hard cap, sandbox only, no secrets.
- [ ] `pytest` (offline) and the demo check (`pytest tests/e2e/test_payments_and_demo.py`) pass after each slice.
