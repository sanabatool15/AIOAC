# ML task types 06: latency, cost and limits

Status: design only, 2026-11-11. Nothing here is built. Line numbers are approximate. Items marked (inferred) were derived from code or complexity reasoning, not run. Every number in section 2 marked EST is an estimate that MUST be replaced by a measurement (section 2.5 and section 4). Items touching caps, quotes, SageMaker runtime or the gate are HUMAN REVIEW (CLAUDE.md). Continues `specs/regression-and-task-types.md` and `specs/cost.md`.

Goal: adding `regression`, `forecast`, `grouping` and `unusual` must not make free tools slower than 60 s, an agent turn longer than 120 s, or a paid job more expensive or less predictable than the quote. Today only `classification` exists, so every number below for the new types is a forecast of risk, not a result.

## 1. Today's time and cost model (classification only)

### 1.1 Free tools and their time bounds

| Tool or route | What it fits | Time bound today | Where |
|---|---|---|---|
| `profile_data` | no model; pandas stats on at most 20,000 rows, predictiveness check stops at 1.5 s | `MAX_ROWS=20_000`, `TIME_BUDGET_S=1.5` | `services/data/profile.py:11-13` |
| `run_baseline` | one forest (100 trees) on 80% of rows, then timing fits on 5/10/20% of the prepared rows | none inside the service; only the agent's 60 s tool limit | `baseline.py:61-100`, `analysis.py:27-39` |
| `compare_models` | one small model of each of 3 families on at most 5,000 rows, then permutation importance on 800 rows x 3 repeats | `MAX_ROWS=5000`; soft `BUDGET_S=12` checked only BETWEEN families (`compare.py:111`); hard 45 s (`tools.py:323-337`, 60 s minus 15 s) | `compare.py:17-23` |
| `run_pilot` / `POST /chats/{id}/pilot` | successive halving: rungs P/4, P/2, P with 3-fold CV; 3 families -> 2 -> 1; then winner scored on 3 rungs again; then 3 timing fits at full size | pilot rows `min(max(8% of work, 100), 3000)`; no deadline inside | `pilot.py:27-30, 88-121` |

Count of fits in one pilot (read from `pilot.py`): rung 1 = 3 models x 3 folds, rung 2 = 2 x 3, rung 3 = 1 x 3, winner curve = 3 rungs x 3 folds, plus 3 timing fits = 30 fits (inferred arithmetic). Pilot models use `PILOT_SIZE` (60 trees, 60 rounds, 300 linear iterations, `families.py:23`); only the 3 timing fits use `FULL_SIZE` (300 / 200 / 300, `families.py:24`).

The agent wrapper applies `agent_tool_timeout_s=60` to level-0 tools only (`loop.py:266-267`, `config.py:83`). The HTTP routes `POST /projects/{id}/baseline` and `POST /chats/{id}/pilot` call the services directly with no timeout at all (inferred from `routes/` layout and `api.md` A0/A3). So a slow pilot is cut off in chat but runs unbounded from the button.

### 1.2 Cost samples and the quote

1. `sample_timings` fits the family on 5%, 10% and 20% of the prepared rows (min 30 rows) and records `(rows, seconds)` (`baseline.py:78-91`).
2. The pilot times the CHOSEN family at its `FULL_SIZE` and stores the result as `forecast.pilot.cost_samples` (`pilot.py:107, 117`). The baseline's own samples use 100 trees and are now only a fallback (`quotes.py:45`: `samples = pilot.cost_samples or run.samples`). So the "baseline times 100 trees, script uses 300" gap in `integration-testing.md` (4,800 rows: 2.3 s projected vs 2.1 s measured; 20,000 rows: 3.0 s vs 5.8 s) is closed on the pilot path since 2026-11-07, but stays on the fallback path and has never been re-measured (inferred).
3. `project_seconds` fits log(time) against log(rows), clips the slope to [1.0, 2.0], and returns `exp(...)` at `full_rows` plus a relative error of 2 x the residual scatter (`cost.py:33-48`).
4. `estimate_quote`: margin = max(0.30, error); estimate, low (x(1 - margin/2)) and high (x(1 + margin)) each go through `hours = (secs x speed_factor + startup_seconds) / 3600`, `cents = hours x hourly + STORAGE + PLATFORM_FEE`; cap = `ceil(high)`; refused above `max_job_cap_cents` (700) (`cost.py:51-70`).
5. `create_quote` passes `full_rows = version.rows` (ALL rows, including the locked ones) although training sees 80% of the work rows (`quotes.py:46`, `training script` `_split` 80/20 at `baseline.py:53-58`). The projection is therefore a few percent high (inferred, conservative).
6. The fee share is `ceil(0.05 x compute cents)`; the hold is `cap + max fee` (`quotes.py:48-55`).

### 1.3 Prices and overhead (all placeholders)

`prices.py:14-17`: `ml.m5.xlarge`, 25 cents/hour (real 23, `integration-testing.md` 2026-10-30), `speed_factor=1.0`, `startup_seconds=240`, storage 1 cent, platform fee 50 cents. One real job: 4,800 rows, forest 300 trees, 69 billable seconds, real AWS compute about 0.44 cents, app cost 52 cents. So 66 of those 69 seconds were overhead, not training (inferred: training was about 2 s). The platform fee is about 96% of every small quote.

### 1.4 MaxRuntimeInSeconds and the cap

`sagemaker_cost.py:22-31`: `floor((cap - 51) / hourly x 3600) - 120 grace - 60 safety`; below 60 s the run is refused (`CapTooSmall`, surfaced as `SageMakerJobError(kind="cap_too_small")`, `sagemaker.py:198-201`). AWS enforces it (`StoppingCondition`, `sagemaker.py:143`); our timer is a backstop at `max_runtime + 120 + 300 + max_pending` (`sagemaker.py:216`). At the 700-cent maximum the runtime ceiling is (649/25) x 3600 - 180 = about 93,300 s, about 26 hours: the per-job cap is a dollar limit and allows far longer jobs than the product expects (derived).

### 1.5 Known inaccuracies and a defect

1. **Cap floor defect (derived from the code, verify with the unit test in section 6).** `max_runtime_seconds` needs at least 240 s of compute budget after the fixed fees, which is 1.67 cents at 25 cents/hour, and the cap is whole cents, so the smallest cap that runs is 53 cents (matches "about 53 cents" in `training.md` 2b). Today the 240 s startup placeholder keeps every quote's high end above that (compute high >= 1.67 cents). If calibration sets `startup_seconds` to the measured value (about 65 s) a small job gets `high` = 51.4 cents, `cap` = ceil = 52, and the SageMaker backend refuses it with `cap_too_small` AFTER the user paid the hold. Calibration alone would break small quotes. The quote must floor the compute cap at the smallest runnable value (section 3.7).
2. The quote times one fit; a paid job that does more (search, backtests, several k) is under-quoted unless the timing samples run the same steps (section 2.3).
3. `speed_factor=1.0` assumes the local machine equals one m5.xlarge core. Boosting (`HistGradientBoosting`) uses all cores by OpenMP while the forest and the pilot use `n_jobs=1` (`families.py:58-59`); the local sample and the 4-vCPU instance can differ by 2 to 4 times for boosting (inferred).
4. HistGradientBoosting turns on early stopping automatically above 10,000 rows, so samples taken below that size over-state the large-data time (inferred, conservative).
5. Whether `MaxRuntimeInSeconds` and `BillableTimeInSeconds` include image and data download is still unverified (`training.md` 2a).

## 2. Per task type

### 2.1 What multiplies work

| Type | Free-tool work | Paid-job work | Multiplier vs one classification fit |
|---|---|---|---|
| classification (built) | 30 small fits | one fit of the chosen family | 1 |
| regression | same shape as classification; regression trees are deeper | one fit | 1 to 4 (forest regressor slower, inferred) |
| forecast | feature build (lags, rolling) + time-ordered backtests (3 to 5 folds) x families | final fit + backtest score + verification on the newest period | 5 to 8 |
| grouping | k from 2 to K, each a fit, plus a quality score (silhouette, O(n^2)) | final fit at the chosen k (the k search ran free) or the search again | up to 9 x fits + O(n^2) |
| unusual | one detector fit + scoring; LOF and one-class SVM are O(n^2) or worse | one fit | 1 (isolation forest) to 100+ (LOF, SVM at 50k) |

### 2.2 Runtime scale per family (EST, single core, about 20 mixed columns, binary or a few classes)

Anchors: forest 300 trees measured at 2.1 s on 4,800 rows and 5.8 s on 20,000 rows (`integration-testing.md`). Everything else is complexity reasoning. Replace each cell with a measurement (section 2.5).

| Task / family | 1k rows | 10k rows | 50k rows | Note |
|---|---|---|---|---|
| classification logistic (300 it) | 0.1-0.3 s | 0.5-2 s | 3-10 s | multiclass multiplies by classes |
| classification forest (300 trees) | 0.5-1 s | 3-6 s | 15-35 s | roughly n log n; wide one-hot slower |
| classification boosting (200 it) | 0.5-1.5 s | 1-4 s | 3-12 s | multi-threaded; early stopping above 10k |
| regression ridge | <0.1 s | <0.3 s | 0.5-2 s | closed form or sparse solver |
| regression forest (300 trees) | 1-2 s | 8-20 s | 50-150 s | no early purity stop (inferred 2 to 4 x classifier) |
| regression boosting (200 it) | 0.5-1.5 s | 1-4 s | 3-12 s | one tree per round |
| forecast (backtest 5 folds + final, boosting) | 3-8 s | 6-25 s | 20-70 s | rows = observations after lag building |
| forecast (forest) | 5-10 s | 30-100 s | 3-10 min | too slow for free tools |
| grouping k-means, k = 2..10 | 0.5-3 s | 3-15 s | 15-90 s | without scoring |
| grouping silhouette on a 2,000-row sample, per k | 0.1-0.3 s | same | same | sample keeps it flat; full 50k is 30-90 s per k |
| unusual isolation forest (100 trees, 256 per tree) | 0.2-0.5 s | 0.5-1.5 s | 1-4 s | near constant in n |
| unusual LOF, full data | 0.1 s | 3-15 s | 1-10 min and O(n^2) memory risk | sample or refuse |
| unusual one-class SVM | 0.1-0.5 s | 5-40 s | minutes | cap at 5,000 rows |

Overhead on SageMaker is about 60 to 70 billable seconds regardless of type (one observation, section 1.3).

### 2.3 Pilot time budget and quote impact per type

Principle: the quote must time what the paid script really does. If the paid job fits the model once, time one fit at `FULL_SIZE`; if it runs a k search or backtests, the timing samples run that whole routine on the 5/10/20% samples (`sample_timings` takes a callable per task, inferred design). Otherwise the quote under-prices exactly the types that multiply work.

| Type | Pilot time budget (soft / hard) | Row cap for the pilot | Quote impact |
|---|---|---|---|
| classification | 25 s / 45 s (today: none; est. 10-25 s at 50k) | 3,000 (exists) | none |
| regression | 25 s / 45 s; pilot set = ridge, boosting, forest limited to 100 trees and `min_samples_leaf>=5` (a plain forest regressor would breach 45 s at 50k, est.) | 3,000 | same formula; samples timed on the chosen regressor |
| forecast | 30 s / 50 s; max 3 backtest folds in the pilot, boosting and ridge only | most recent 5,000 observations | samples are the whole backtest + final fit; multiplier 5 to 8 shows in the compute line, still small money |
| grouping | 20 s / 40 s; k in 2..8; silhouette on a 2,000-row sample; k search is free and its result pins k in the quote | 20,000 for the fit, 2,000 for scoring | paid run is one final fit at the pinned k: cheap |
| unusual | 20 s / 40 s; isolation forest by default; LOF and SVM only on a 5,000-row sample | 50,000 isolation forest, 5,000 others | paid run one fit, cheap |

The quote shape does not change: estimate, range, cap, 5% success fee. Grouping and unusual have no target and no fee (`regression-and-task-types.md` 1.4): the compute-only variant needs its own wording and is a payment-model decision (open question 1).

### 2.4 Can the demo job reach 10 to 15 minutes, and when is SageMaker required

No, not honestly, with the current families and the 50,000-row fetch cap (`config.py:36`): a forest on 50k rows is est. 15 to 35 s of training plus about 65 s overhead, about 2 minutes billable, about 1 cent of AWS compute, and a quote of about 53 cents (placeholders) because the 50-cent platform fee dominates (`status.md` section 6, item 1). The wireframe "$5, 2 hours" cannot appear. Options for the owner (open question 2): (a) show the real small numbers and say so; (b) make the paid job do more useful work than the free pilot, such as a small hyper-parameter search (for example 5-fold CV over 12 candidates is 60 fits, est. 3 to 10 minutes at 50k) priced by the same timing routine. Option (b) is a product change and is not assumed anywhere in this spec.

When SageMaker is required: the free tools and the `local` backend run in the API process and must stay under the budgets of section 2.3. A paid run goes to SageMaker whenever the product is charging (`TRAINING_BACKEND=sagemaker`); `local` stays the dev and default-demo backend that costs nothing (`training_local/backend.py`). A rule for refusing instead of running locally: if the projected local seconds for the paid routine exceed 120 s or the projected matrix exceeds 500 MB (section 3.5), the run is only offered on SageMaker. The local backend cannot enforce a runtime cap (it stops between stages only, `backend.py:19-24`).

### 2.5 Measurement harness and results table

Add `backend/tests/perf/bench_tasks.py` (section 6.3). Run: `cd backend && RUN_PERF=1 python -m tests.perf.bench_tasks --rows 1000,10000,50000 --tasks classification,regression,forecast,grouping,unusual --repeats 3 --out ../backend/logs/perf-<date>.json`. It builds the synthetic frames in `evals/synth.py` style (20 columns, 3 of them categories with 5 / 50 / 2,000 levels) and records, per (task, family, rows): fit seconds (median of 3), peak RSS, matrix bytes after encoding, and for free tools the wall time of `pilot.run_pilot`, `compare.compare`, `baseline.run_baseline`, `profile.profile`. Paste the result into `specs/integration-testing.md` section 4 as a dated table:

| date | machine (cores, RAM) | task | family | rows | cols (encoded) | fit s | peak MB | tool wall s | note |
|---|---|---|---|---|---|---|---|---|---|

The same run records the local-versus-instance factor once paid runs exist (section 4.3).

## 3. Guard rails

### 3.1 Row and time sampling caps per tool (proposed constants)

One new module `services/data/timebox.py` (inferred name) holds the constants and a cooperative `Deadline(seconds)` with `.check()` raising `OutOfTime`. Services take an optional `deadline` and call `.check()` between fits (pilot: between folds and rungs; compare: between families AND inside permutation repeats; grouping: between k values). Today only `compare` has a soft budget and it only fires between families (`compare.py:111`).

| Constant | Value | Reason |
|---|---|---|
| `FREE_TOOL_SOFT_S` / `FREE_TOOL_HARD_S` | 25 / 45 | stay under the 60 s agent limit with margin for the DB and one more tool |
| `MAX_FIT_ROWS_QUADRATIC` | 5,000 (LOF, one-class SVM, agglomerative) | O(n^2) time and memory |
| `SILHOUETTE_SAMPLE` | 2,000 | O(n^2); full 50k is est. 30 to 90 s per k |
| `GROUPING_K_RANGE` | 2..8 | each k is a fit |
| `BACKTEST_FOLDS_PILOT` / `_PAID` | 3 / 5 | fits multiply by folds |
| `COMPARE_MAX_ROWS_BY_TASK` | classification 5,000; regression forest 2,000 | existing parameter `max_rows` (`compare.py:98`) |
| `MAX_ENCODED_COLUMNS` | 2,000 | memory, section 3.5 |

### 3.2 The 60 s tool timeout and the abandoned thread

`_call_with_timeout` shuts the pool down without waiting (`loop.py:51-57`): the worker thread keeps running after the turn ended, with the same SQLAlchemy `Session` the turn's `finally` block uses (`loop.py:99-103`), and may commit a forecast row after the user was told "this took too long". Sessions are not thread-safe (inferred risk, not reproduced). `compare_models` has the same pattern with its own pool (`tools.py:330-337`). Fix direction: the cooperative `Deadline` above makes the worker stop itself; as a belt, run level-0 heavy tools on a fresh session created inside the worker. A test for the late commit is in section 6.1. This is the main reason deadlines belong inside the services and not only in the agent wrapper: the HTTP routes have no wrapper at all (section 1.1).

### 3.3 Agent loop limits

12 steps, 80,000 tokens, 120 s per turn, repeat guard at the same call more than 3 times (`config.py:77-82`, `loop.py:148-158, 232-236`). The deadline is checked before each model call and tool call, never inside one, so a turn can end up to one tool call (up to 60 s) past 120 s (inferred). A new task type adds tools or choices, not steps; the budget rule is: the sum of the soft budgets of the free tools a typical flow calls in one turn (`profile` 2 s + `baseline` 25 s + `compare` 12 s + `pilot` 25 s) must stay under 120 s minus about 3 model calls (about 10 s each), so no more than two heavy tools per turn. Put that guidance in the system prompt only as a plain "one check at a time" rule; the code limits are the enforcement. The repeat guard is by identical arguments, so a slow tool re-asked with a different `target` bypasses it by design (the turn deadline still ends it).

### 3.4 Polling and rate limits

The training screen polls `GET /training` every 3 s (`frontend/lib/training-poll.ts:4`); the chat polls the activity feed every 2 s only while a turn runs (`chat-controller.ts:38`); SageMaker status is polled every 15 s (`config.py:63`). Long jobs (grouping or forecast paid runs of several minutes) add no new polling load. Rate limiters exist only for predict (120/min), batch predict (10/min) and the public result link (60/min), in memory per process (`routes/screens.py:18-20`, `services/ratelimit.py`); breakpoint E6 (shared limiter) stays open. The heavy free routes (readiness, baseline, pilot, fix, compare) have no limiter except the one-turn-per-project lock for chat (`loop.py:64-77`). Proposed: a process-wide semaphore of 2 concurrent heavy free tools, with a plain "the service is busy, try again in a moment" answer (HTTP 429/503), so that four users running a regression pilot cannot starve the API. In-memory is acceptable for the hackathon; note it does not hold across processes.

### 3.5 Memory

`families.build` uses dense one-hot output for logistic and boosting (`dense = family != "forest"`, `families.py:50-54`) and `features.prepare_features` caps nothing on category count (only ID-like columns at 95% unique, `features.py:8-15`). 50,000 rows x 2,000 encoded columns x 8 bytes = 800 MB per copy; a 5,000-level category is 2 GB per copy, and fit, train/test split and boosting's binning make several copies (inferred). Regression with many categories (zip code, product id) hits exactly this. Guard: `OneHotEncoder(max_categories=..., min_frequency=...)` in the shared `families.py` (it ships verbatim to SageMaker, so the script and the app change together), a `MAX_ENCODED_COLUMNS` check that answers a plain "this column has too many different values; I will group the rare ones" NOTE, and a memory estimate `rows x encoded_cols x 8` compared with 25% of instance RAM (m5.xlarge 16 GiB) before a quote is made. Grouping and unusual add the O(n^2) pairwise matrix of section 3.1 (5,000^2 x 8 = 200 MB).

### 3.6 SageMaker instance and quota

One instance type, `ml.m5.xlarge` (4 vCPU, 16 GiB), training quota 20 (`integration-testing.md`); one paid job at a time (`cost.md` section 4, Inngest `concurrency` 1, `inngest_runner.py:40`). The forest and pilot use `n_jobs=1` and leave 3 vCPUs idle: a paid forest or backtest could run 3 to 4 times faster and cheaper with `n_jobs=-1` inside the script (inferred). That changes `families.py` or the script and the speed factor, so it is a calibration decision, not assumed here. A larger instance for big grouping or forecast jobs is future work (`future-instances-and-gpu.md`); until then the row caps of section 3.1 protect the single instance.

### 3.7 Global budget, per-job cap and the cap floor

Global ceiling is 160 - 40 = 120 dollars of recorded spend, per-job maximum 700 cents (`budget.py:7-12`, `config.py:67-69`). Because the real compute of any capped job at these sizes is about 1 cent, the guard rarely binds; its value is as a backstop against a long job.

`cap_too_small` today: the quote is made and the hold is placed first, and the error is raised only when the backend starts, then the whole hold is voided (our failure, user pays $0, `training.py` `fail_run`). That is safe for the money but a bad experience. Proposed (HUMAN REVIEW, quote code): `create_quote` computes `min_cap = fixed_fees + ceil(minimum runtime window in cents)` from `sagemaker_cost` and sets `cap = max(high, min_cap)`, so a quote can never be unrunnable, and a unit test pins this for every instance in `prices.py`. When a type's projected runtime exceeds what 700 cents buys (about 26 h), the quote is refused with the existing `QuoteTooExpensive` text; with the row caps of section 3.1 this should not occur.

## 4. Cost accuracy loop

### 4.1 Fields stored on each finished job

No schema change: add to `TrainingRun.result` JSON a `cost_record` (inferred), written in `training.execute_run` (`training.py:~150-165`):

`task_type, family, rows_total, rows_train, encoded_cols, projected_seconds (from the quote), train_seconds (script metrics), billable_seconds, startup_seconds_observed = billable - train, instance_type, quote_estimate_cents, quote_low_cents, quote_high_cents, actual_cents, stopped_at_cap, prices_version`.

Needs: `projected_seconds` added to `quote.breakdown` (it exists on `CostEstimate`, `cost.py:30`, but is not stored, `quotes.py:57-61`); `billable_seconds` added to `TrainingResult` (`ports.py`) and set in `sagemaker.py:_finish` (it reads `BillableTimeInSeconds` but returns only cents). Both are HUMAN REVIEW (quote and ports). A repository function `repositories/cost_report.py` builds the `CostRecord` list (services have no SQL).

### 4.2 Report per task type

Extend `CostRecord` (`report.py:6-10`) with `task_type`, `family`, `rows`, `projected_seconds`, `actual_seconds`; `cost_accuracy_report` keeps its current keys and adds `by_task` (same keys per `task_type`/`family`) and `runtime_ratio` (median and p90 of `actual_seconds / projected_seconds`, per type). Success bar proposed: at least 80% of jobs inside the range per type once there are 8 or more jobs; a type under 60% inside or with p90 ratio above 1.5 does not ship to paid. The old contract test `test_cost_accuracy_report` (`tests/contract/test_sagemaker_backend.py:343`) must keep passing unchanged.

### 4.3 Calibration plan (needs owner approval; costs cents)

Three to four real capped jobs per (task, family) at 1k, 10k and 50k rows, smallest instance, cap 60 cents (`test_sagemaker_training.py` `CAP_CENTS`). About 12 classification, 12 regression, 8 forecast, 4 grouping, 4 unusual = about 40 jobs, each est. 0.4 to 1.5 cents of real AWS compute: about 30 to 60 cents total. Record `startup_seconds_observed` and the speed ratio between the local fit and the instance fit; then update `prices.py` (`startup_seconds`, `speed_factor`, a per-family factor table if the ratios differ, `hourly_cents` to 23). Do the cap floor of section 3.7 BEFORE lowering `startup_seconds`.

Exact commands (from `integration-testing.md`):

1. Free and read-only: `cd backend && RUN_REAL=1 pytest tests/integration -v -s`.
2. One existing paid job: `RUN_REAL=1 RUN_PAID=1 pytest tests/integration/test_sagemaker_training.py -v -s`.
3. New, opt-in, paid: `RUN_REAL=1 RUN_PAID=1 CALIBRATE_TASKS=classification,regression CALIBRATE_ROWS=1000,10000,50000 pytest tests/integration/test_sagemaker_calibration.py -v -s`, appending one JSON line per job to `backend/logs/calibration.jsonl` (git-ignored) and printing names, never secrets (safety rule 4). Tell the owner first and wait for a yes (`breakpoints.md` section 5).

## 5. Observability

Per run, in the existing `RunLog` (`services/agent/runlog.py`) and traces, no new store:

| Where | Add | Why |
|---|---|---|
| `tool_result` events (`loop.py:305`, already has `ms`) | `task_type`, `rows_used`, `deadline_hit` flag | find the slow type |
| pilot JSON (`pilot_seconds`, `pilot.py:119`) | per-rung seconds, `deadline_hit`, `sampled_rows` | tune section 3.1 |
| trace step `limit` (`loop.py:136`) | reason `timeout` plus the tool name active | which tool hit the 120 s turn limit |
| `cost_record` (4.1) | as listed | accuracy per type |
| `fail_run` trace | error kind (`cap_too_small`, `capacity`, `algorithm`) | caps |
| new counter in memory, logged at INFO | abandoned worker threads (count, tool, ms past timeout) | the thread problem |

Metrics to watch (no dashboard needed; run as read-only queries through a repository function, or `python -m evals.show` over the logs):

1. p50 and p90 of free-tool `ms` per tool and `task_type` (target: p90 under 25 s).
2. Share of tool calls ending `timed out` or `deadline_hit` (target: under 2%).
3. Share of turns ending `limit/timeout` (target: under 3%).
4. Share of quotes later failing `cap_too_small` (target: 0 after section 3.7).
5. `inside_share` and runtime ratio by type (section 4.2).
6. Share of runs `stopped_at_cap` (high means the quote's margin is too thin for that type).
7. Cumulative real AWS spend against the $120 ceiling (`BudgetRepository.spent`).

Queries, in words: group `training_runs` by `result.cost_record.task_type, family` with count, median `actual_cents`, share `actual between low and high`; group `agent_steps` of kind `tool_result` by tool name with p50/p90 of `ms`; count `agent_runs` by `stop_reason`.

## 6. Tests

### 6.1 Unit (offline, default suite, fake clocks)

| Test file and name | Asserts |
|---|---|
| `tests/unit/test_timebox.py::test_deadline_check_raises_between_fits` | a fake clock past the soft deadline stops a loop at the next `.check()` |
| `::test_pilot_returns_partial_forecast_or_not_eligible_when_out_of_time` | pilot with a tiny budget returns a plain "ran out of time" outcome, never raises, writes at most one forecast row |
| `::test_no_forecast_row_committed_after_tool_timeout` | the late-commit race of section 3.2 |
| `tests/unit/test_compare_budget.py::test_budget_checked_inside_permutation_repeats` | fake clock; total stays under the hard limit |
| `tests/unit/test_cost_floor.py::test_cap_never_below_min_runnable_for_every_instance` | for startup 0 to 300 s and compute 0 to 700 cents, `max_runtime_seconds(cap)` never raises `CapTooSmall` for a quote-made cap (property over a grid) |
| `::test_calibrated_prices_do_not_break_small_quotes` | with `startup_seconds=65`, `hourly=23`, a 1-second job still gets a runnable cap |
| `tests/unit/test_cost.py::test_project_seconds_quadratic_slope_clipped` | O(n^2)-shaped samples give slope 2.0, not more |
| `tests/unit/test_cost_report_by_task.py` | per-type grouping, empty types, old keys unchanged |
| `tests/unit/test_sampling_caps.py` | silhouette sample <= 2,000; LOF input <= 5,000; k range 2..8 |
| `tests/unit/test_encoding_guard.py` | a 5,000-level category triggers grouping of rare values and the NOTE; encoded columns <= 2,000 |
| `tests/unit/test_architecture.py` (existing) | still passes: `timebox.py` has no sqlalchemy, `repositories/cost_report.py` holds the SQL |

### 6.2 Contract (mocked boto3)

In `tests/contract/test_sagemaker_backend.py` style: `test_max_runtime_for_each_task_family` (cap -> `MaxRuntimeInSeconds` in `create_training_job`), `test_billable_seconds_returned_in_result`, `test_cap_too_small_raised_before_any_upload` (nothing put to S3), `test_hyperparameters_carry_task_and_family`, `test_resource_in_use_follows_existing_job` (unchanged). Existing tests must pass unchanged.

### 6.3 Performance benchmark (opt-in, never in the default suite)

`backend/tests/perf/bench_tasks.py`, pytest marker `perf` (add to `pyproject.toml` markers, excluded by default because `testpaths=["tests"]` would collect it: put `collect_ignore_glob=["perf/*"]` in `tests/conftest.py` unless `RUN_PERF=1`). Asserts only ratios and ceilings, never exact seconds: each free tool at 50,000 rows finishes under `FREE_TOOL_HARD_S`; fit time at 50k is at most 12 x the fit time at 5k for linear-ish families and at most 120 x for quadratic ones (catches an accidental O(n^2)); peak RSS under 2 GB at 50k x 200 encoded columns; results written to `backend/logs/perf-*.json`. Cost: nothing (local CPU, about 10 to 20 minutes).

### 6.4 Integration (opt-in, live)

| Test | Needs | Cost |
|---|---|---|
| `tests/integration/test_sagemaker_training.py` (exists) | `RUN_REAL=1 RUN_PAID=1` | about 1 cent |
| `tests/integration/test_sagemaker_calibration.py::test_calibrate_<task>` (new) | same plus `CALIBRATE_TASKS`, `CALIBRATE_ROWS` | about 30 to 60 cents for the full plan |
| `::test_cap_floor_job_runs` | `RUN_PAID=1`; a quote at the minimum cap (53 cents) completes | about 1 cent |
| `::test_no_job_left_running` (exists) | `RUN_REAL=1` | free |

## 7. Slices, acceptance, risks

### 7.1 Slices (each shippable, test first)

0. **Measure** (no app change): the harness of 2.5 and 6.3; fill the table. Not review-gated.
1. **Deadlines inside services** (free tools): `timebox.py`, pilot, compare, baseline, profile take a deadline; routes pass it; abandoned-thread fix. Not payment.
2. **Per-task caps and sampling constants** (free), applied as each type lands (regression families, grouping k search, detector choice). Not payment.
3. **Encoding guard** in `families.py` (shared with SageMaker; ships verbatim): HUMAN REVIEW because the paid script changes.
4. **Cap floor in `create_quote`** and its tests: HUMAN REVIEW (quote, cap).
5. **Cost record fields** (`quote.breakdown.projected_seconds`, `TrainingResult.billable_seconds`, `cost_record`) and the per-type report: HUMAN REVIEW (quote, ports, training).
6. **Calibration jobs** and `prices.py` update (startup, hourly, speed factors): HUMAN REVIEW (prices drive caps); owner approval for the paid runs.
7. **Whole-routine timing** for forecast, grouping and unusual quotes (section 2.3): HUMAN REVIEW (quote).

### 7.2 HUMAN REVIEW flags

`sagemaker_cost.py` (runtime formula, only read here), `quotes.py` cap floor, `cost.py` margin if the per-type error needs a wider band, `prices.py` values, `ports.py` `TrainingResult` field, `training.execute_run` `cost_record`, `families.py` encoder change, any change to `fee_of` (none proposed), the gate (none proposed).

### 7.3 Risks

1. The EST table is wrong by 3x either way: handled by slice 0 before any cap logic is trusted.
2. Early-stopping and multi-thread boosting break the speed factor: calibrate per family.
3. Calibrating startup downward without the cap floor makes small quotes unrunnable (1.5.1).
4. Forecast and grouping paid jobs are under-quoted if timed as one fit.
5. A late-committing abandoned thread creates a forecast the user was told did not finish.
6. Memory blow-up from dense one-hot of high-cardinality columns on the app machine, which also serves HTTP.
7. The demo cannot show a believable 10 to 15 minute job without a product decision (2.4).

### 7.4 Open questions for the owner

1. Do `grouping` and `unusual` get a compute-only price (no target, no fee), and is the 50-cent platform fee the same?
2. Show real small numbers in the demo, or make the paid job do a search so it runs minutes (option b of 2.4)?
3. Soft 25 s / hard 45 s for free tools: accepted, or tighter for the demo?
4. Allow `n_jobs=-1` on SageMaker (faster, cheaper, needs recalibration)?
5. Does `MaxRuntimeInSeconds` include data and image download? Verify with one live job before trusting the floor.
6. A per-family speed factor in `prices.py`, or one factor per instance?
7. Is a process-wide semaphore for heavy free tools acceptable, or is a shared limiter (E6) first?

### 7.5 Acceptance checklist

- [ ] Benchmark table for every (task, family, rows) recorded in `specs/integration-testing.md`, EST values replaced.
- [ ] Every free tool and route has an inside-the-service deadline; none exceeds 45 s at 50,000 rows on the benchmark machine.
- [ ] No result is committed after a tool timeout (test passes).
- [ ] Silhouette, LOF, SVM and agglomerative never see more than their row caps; k range capped.
- [ ] High-cardinality columns cannot create a matrix over 500 MB; plain NOTE shown.
- [ ] A quote can never produce `cap_too_small`; test passes with calibrated prices.
- [ ] Quote timing runs the same routine as the paid script for each type.
- [ ] `cost_record` stored on every finished run; `cost_accuracy_report` has `by_task` and `runtime_ratio`; old test unchanged.
- [ ] Calibration done for each type with the owner's yes; at least 80% inside range per type, or the type stays off paid.
- [ ] Offline suite (`pytest`) and the demo check (`pytest tests/e2e/test_payments_and_demo.py`) still pass; perf tests excluded from the default run.
- [ ] Every HUMAN REVIEW item in 7.2 has a small diff and a written explanation.
