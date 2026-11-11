# ML task types 05: data, readiness and discovery

Status: design only, 2026-11-11, branch `claude/ml-task-types-spec`. Nothing here is built. Companion to `specs/regression-and-task-types.md` (the overall design). This file covers the free, data-side work: how the answer column is chosen and typed, readiness, profile, fixes, dataset discovery, and the offline data for tests. Line numbers are from a read of the code on this branch and are approximate. Items marked (inferred) were not read in code or run. Items marked (verified) were checked against a live service or a downloaded file on 2026-11-11 (three files, 5 MB in total, kept outside the repo).

Task types in scope: `classification` (built), `regression`, `forecast`, `grouping`, `unusual`. The data tools stay free (gate level 0); only fixes are level 1.

## 0. Honest summary for the owner

Finding data mostly works for the new types already: the sources, storage, size caps, links and uploads do not care what the answer column is. What has to change is small but spread over many files, because "the answer is a few groups" is assumed in about twenty places:

1. **The answer column is assumed to exist, to be categorical, and to be typed by a guess.** Grouping and unusual (unlabelled) have no answer column at all.
2. **Readiness and the summary measure class balance** on the answer, which gives a nonsense finding on a number.
3. **Discovery only looks for classification** (prefilter, Hugging Face tag, ranking bonus, curated list, sample list).
4. **The locked-rows split is random.** For forecast it must be the last period, and a data fix must not break that.
5. **There is no offline data** for any new type.

Biggest risks: a forecast evaluated on shuffled rows (fake accuracy), a data fix that changes the locked rows by accident, and a number column silently treated as groups (verified example: Wine Quality, section 1).

## 1. Today's data flow and the classification assumptions in it

Flow: user brings data (upload `POST /projects/{id}/data`, link `POST .../data/link`, or discovery) -> `datasets.add_candidate` (`datasets.py:18`) stores a candidate -> `select_candidate` (`datasets.py:34`) copies it to `datasets/<project>/v1.csv` and deletes the other candidates -> `analysis.readiness` -> `analysis.baseline` -> pilot, quote, hold, train, verify on the locked rows.

| # | Assumption | Where |
|---|---|---|
| 1 | A target column is required and must exist | `datasets.py:40-41`; routes `projects.py:171-176`; `DatasetVersion.target_column` is already nullable (`tables.py:82`), `Project.task_type` exists, unused (`tables.py:53`) |
| 2 | Target typing is a guess inside the profile: at most 20 distinct values means "category", even if the values are numbers | `profile.py:18`, `101-125`. (Verified: UCI Wine Quality `quality` holds the whole numbers 3 to 9, so it is read as groups; Abalone `Rings` has 28 values, so it is read as a number) |
| 3 | Number targets get a one-line stub: "a number, not a few groups" and no spread, skew or zeros | `profile.py:111-113` |
| 4 | Suspect checks use group shares for a category target; the number branch only checks a near-perfect rank correlation | `profile.py:160-166`, `209-214` |
| 5 | Readiness penalises "smaller group" using `value_counts` of the target. On a number every value is unique, so the "smaller group" is about 0 percent and the finding is wrong and costs 12 points | `insights.py:48-49`, `78-81` |
| 6 | The agent summary reports `balance` ("smallest of N groups") the same way | `insights.py:109-113` |
| 7 | Trust level is an accuracy lift over a simple guess | `insights.py:126-135`, called at `analysis.py:34` |
| 8 | Free test, pilot, verification score accuracy; the splits are stratified random | `baseline.py:53-58`, `70-71`; `pilot.py:39-50`; `verification.py:72-74` (the `except ValueError` fallback hides a stratify failure) |
| 9 | Copy-of-answer leak check compares text equality only, so "the answer is the sum of two columns" passes | `features.py:20-34`. (Verified: UCI Bike Sharing `cnt` equals `casual + registered` in 100 percent of 17,379 rows) |
| 10 | Row-ID test drops text or integer columns that are at least 95 percent unique. A daily date column is unique per row, so it would be dropped as an "ID" and a forecast would lose its time axis | `features.py:8-17`, applied by `prepare_features` (`features.py:49-55`) |
| 11 | Missing-value markers are text only (`?`, `na`, `-`). A numeric sentinel is not seen. (Verified: UCI Air Quality uses `-200`: 1,683 of 9,357 rows in `CO(GT)`) | `profile.py:22` |
| 12 | Discovery: pre-filter drops any candidate whose task list lacks "Classification" (UCI lists plain "Regression" and "Clustering", so Concrete, Bike Sharing and Traffic are dropped) | `discovery.py:126` |
| 13 | Curated and sample candidates are hard-wired as "Classification"; the quality score gives +0.5 for it | `discovery.py:108`, `114`, `183` |
| 14 | Hugging Face search uses the tabular-classification tag first | `huggingface.py:17`, `51` |
| 15 | OpenML marks a dataset "Classification" only when it has 2 or more classes; a numeric target gives an empty list | `openml.py:77` |
| 16 | UCI hits keep only the first target and drop the "Time-Series" characteristic; multi-target sets (Energy Efficiency has `Y1`, `Y2`) lose the second | `uci.py:53-58`; "not a classification task" note at `uci.py:84` |
| 17 | Curated entries must have a target and are all classification; the sample list has one churn file | `curated.py:32-41`; `curated.json` (12 items); `samples.py:24-27` |
| 18 | The first words of a time goal do not count: "forecast", "predict", "growth" are filler, so "forecast my sales" has one content word and the clarity guard answers "ask what to predict" | `clarity.py:10-20`, `34-38` (inferred from the word lists, not run) |
| 19 | The base prompt says only categories can be predicted | `context.py:24` |
| 20 | Fixes: two allow-listed fixes, both row or column removal; the locked rows of a child are found by matching the CONTENT of each row against the root's locked rows | `fixes.py:33`, `72-87`; `verification.py:64-69` |
| 21 | Fetchers keep the FIRST 50,000 rows. For a time-sorted file that drops the newest period | `uci.py:95`, `101`; `openml.py:130-131`; `huggingface.py:115` |

## 2. Per type: what a suitable dataset is, readiness, profile, fixes

### 2.0 Shared design

**`task_type` is chosen by the user, proposed by code.** A new pure module `services/data/target_kind.py` (NOT in `features.py` or `baseline.py`, which ship verbatim to SageMaker) holds `target_kind(series) -> {kind, distinct, parsed_from_text, ambiguous}` and `find_time_column(df) -> {column, ...} | None`. `profile._target_part` calls it instead of its own inline rule. Rules:

- numeric or text-that-parses (section 2.2), more than 20 distinct values -> propose `regression` (or `forecast` when a time column exists and the goal says over time);
- bool, 2 values, or text that does not parse -> `classification`;
- numeric with 3 to 20 distinct values (ratings, counts) -> **ambiguous**: never decided by code. The select card shows both ("pick a group" or "predict a number") and the user picks. The pick is stored in `projects.task_type`.
- a goal with no outcome column ("group my customers", "find odd records") -> `grouping` or `unusual`, no target asked.

`select_candidate(..., target: str | None, task_type)` accepts `target=None` only for `grouping` and for `unusual` marked unlabelled; otherwise `DatasetError("which column should we predict?")` stays. `routes/projects.py:171-176` and the card `detail` gain `task_type`. All of this is level 1 already (the user's click or approval card).

**Grade semantics stay the same.** `analyze(df, target, task_type="classification")` dispatches. A shared `_common` part (row labels, text numbers, rows, duplicates, missing, constant columns, leaky copies) is the current code; the class-balance block moves into the classification branch unchanged. Per-type findings come from small pure functions returning `(findings, penalty, measurements)`. Same `GRADES` table (`insights.py:11`), same OK/NOTE shape, same start of 100. **Type-specific penalties are capped at 45 in total**, so an otherwise clean file is never worse than a C for type reasons alone, except the hard floor in the forecast rules (no usable date: F). Golden test: classification output is byte-identical before and after.

### 2.1 Regression (the answer is a number)

Suitable data: at least 300 rows (1,000 is better), one numeric answer with a real spread, a mix of numeric and category inputs, under 50,000 rows after the cap.

| Check | Rule (inferred thresholds, tune on real data) | Plain finding | Penalty |
|---|---|---|---|
| Answer stored as text | at least 90 percent parse after removing `$ € £ ¥ , %`, spaces, and `(12.5)` as negative | "The answer column holds numbers written as text (like $1,200); they are read as numbers." | 0 |
| Few distinct values | 3 to 20 | asks the user (2.0), no finding | 0 |
| Empty answers | share missing | "N rows have no answer and are left out" | 0 if under 10 percent, else 15 |
| Same answer everywhere | spread is 0 | "Every row has the same answer, so there is nothing to learn." | 100 (F) |
| Skew | absolute skew above 2 (above 5) | "A few very large answers pull the average up; typical errors will be driven by them." | 5 (10) |
| Extreme values | share above Q3 + 3 x IQR over 3 percent (over 10) (same rule as `profile.py:17`, `235`) | "Some answers are far bigger than the rest." | 5 (10) |
| Many zeros | exact zeros over 30 percent | "More than a third of the answers are exactly 0, which is hard to predict well." | 5 |
| Answer given away | a column, or the sum or difference of two columns, with R-squared at least 0.99 against the answer (checked on at most 20 numeric columns) | "'X' and 'Y' together add up to the answer, so they are ignored." | 25 (same as `insights.py` leak) |
| Rows, duplicates, missing, IDs, constants | unchanged | unchanged | unchanged |

Removed for this type: the smaller-group finding and the `balance` summary, replaced by `target_summary`: median, middle 80 percent range, skew words. The simple guess for trust is "always the average" (owned by the scoring spec; `trust_level` needs a regression branch, `insights.py:126`).

`profile_data` additions: `target: {kind:"number", min, median, max, zeros_percent, skew_text, extreme_note, parsed_from_text, could_be_groups}`; suspect checks `sum_of_columns` (strong) and `target_like_name`; sentinel detection (a number repeated in over 5 percent of rows that is far outside the rest, like -200 or -999: "looks like a code for missing") added beside `MISSING_MARKERS`.

### 2.2 Forecast (a number over time)

Suitable data: a date or time column that parses, one numeric answer, at least 500 usable rows (`forecast_min_rows`, `config.py:73`) AND at least 50 distinct periods (more for seasonality), reasonably regular spacing, no unknown future columns.

`find_time_column`: candidates are columns that `profile._kind` calls "date" (`profile.py:57-88`) plus a pair like Date + Time (Air Quality, verified) joined into one stamp; whole-number year or month columns are allowed only if no better one exists; pick the one with the most distinct, mostly ordered values. The column is stored on the dataset version (new nullable `dataset_versions.time_column`; `python -m app.db.init --upgrade --yes` adds it).

| Check | Rule | Plain finding | Penalty |
|---|---|---|---|
| No usable date column | none found | "I could not find a date column. Without one I cannot test a forecast fairly." | hard floor F; free test refused with the nearest reframe |
| Dates that do not parse | over 5 percent fail | "N dates could not be read" | 15 |
| Day/month ambiguity | all values with day at most 12 | "I read 3/10/2004 as day/month. Tell me if that is wrong." | 0, shown on the card |
| Not sorted | rows out of order | "Rows were out of order; I sorted them by date." | 0 |
| Few periods | under 50 (under 100) | "Only N dates of history, which is short for a forecast." | 30 (12) |
| Short for seasons | under 2 yearly cycles at daily/weekly/monthly spacing | "Less than two full years, so yearly ups and downs cannot be learned." | 5 |
| Irregular spacing | the most common gap is under 80 percent of gaps | "The time between rows varies." | 8 |
| Gaps | missing periods over 5 percent (over 20) | "N stretches have no data, the longest about X." | 10 (20) |
| Repeated timestamps | the same stamp on several rows | "Several rows share a date; this looks like several series (for example stores). Which column tells them apart?" | 8; asks the user |
| Same-period columns | strong suspects, see profile | "'X' is recorded in the same period as the answer, so you may not know it ahead of time." | 25 per unresolved strong suspect |

Verified shapes to design against: Traffic Volume has 48,204 hourly rows with **7,629 repeated timestamps**, **2,588 gaps** and one gap of about 308 days; Bike Sharing is clean and hourly but carries the `casual + registered` leak; Air Quality has Date and Time as two text columns, D/M/YYYY, and `-200` codes.

`profile_data` additions: `time: {column, first, last, periods, spacing, gaps_percent, repeated_timestamps, order}`; suspect `same_period_column` (name hints plus any column that is a function of the answer); sentinel codes as in 2.1.

### 2.3 Grouping (no answer column)

Suitable data: at least 100 rows (300 preferred; the 300-row discovery floor, `discovery.py:22`, becomes 150 for this type), at least 2 usable numeric or category columns after IDs are removed, no answer needed. An existing label (Wholesale `Channel`, Credit-card `Y`) can be kept aside as a `reference_column`, used only to sanity-check the groups, never to train.

| Check | Rule | Plain finding | Penalty |
|---|---|---|---|
| Too few columns | under 2 usable | "Fewer than 2 useful columns, so there is nothing to group on." | 40 |
| Row labels | existing ID rule | existing text | 0 |
| Very different scales | column spreads differ over 100 times | "Columns are on very different scales (like dollars and counts); I will put them on one scale." | 0 (automatic) |
| Heavy skew | skew over 5 in over a third of columns | "Most spending is concentrated in a few customers; groups may be dominated by them." | 8 |
| Near-copies | two columns correlate at 0.98 or more | "'A' and 'B' say the same thing; one is kept." | 3 |
| Mostly one value / empty | existing constant and missing rules | existing | existing |
| Too many columns for rows | columns over rows / 5 | "Many columns for few rows." | 10 |
| No structure | (cannot be known before the run; no finding) | none | 0 |

`measurements` has no `minority_share`. `trust_level` does not apply (no accuracy); the scoring spec owns how groups are judged.

### 2.4 Unusual records

Two sub-cases, chosen by the user (they say whether a column marks the odd rows):

- **Labelled** (a 0/1 or yes/no column marks odd rows). Treated as classification with a rare group, plus checks: rare share (under 5 percent is normal here), odd rows in total under 30 -> "Only N odd examples; too few to test a catch rate" (penalty 25), rare share under 0.1 percent (penalty 15), and the existing lopsided note is reworded to "odd rows are rare, which is expected". The locked rows are drawn stratified so the locked set holds enough odd rows (at least 10; else the run is not eligible). This part is a data-side input to the lopsided scoring design (regression spec 1.1).
- **Unlabelled.** No locked truth exists, so no verification. Findings: at least 2 usable columns, rows at least 1,000 (penalty 15 under), duplicates ("repeated rows look normal because they repeat"), missing, constants. The agent asks for the expected share of odd rows ("about how many in 100?"), stored as an input, not a promise.

### 2.5 Fixes per type (level 1, approval card, max 3 per project, unchanged)

Principle: **a child version may only change which rows and columns exist, never the values of a row that is kept.** This is forced by the current locked-rows rule: a child finds its locked rows by matching row content against the root's locked rows (`verification.py:64-69`). If a fix rewrote a value (capped an extreme answer, parsed a date), the content would differ, the locked rows would no longer match, and they would be treated as work rows: the model would be trained on the rows it is scored on (HUMAN REVIEW, section 6).

Therefore value-changing preparation happens once, at the root, before the split is drawn (one approval at selection), or later as recorded "prep steps" applied identically to work and locked rows (deferred, section 6 slice 6).

| Type | v1 allow-list (row or column removal only) | Done at the root when the user selects | Deferred (prep steps) |
|---|---|---|---|
| classification | `drop_duplicate_rows`, `drop_mostly_empty_columns` (`fixes.py:33`, unchanged) | none | none |
| regression | the two above, `drop_rows_without_answer`, `drop_answer_copies` (sum-of-columns leak) | answer text to number ("$1,200" -> 1200), recorded in `notes` | `cap_extreme_values` on feature columns only, bounds from work rows |
| forecast | `drop_mostly_empty_columns`, `drop_same_period_columns` (user-approved), `drop_duplicate_rows` only for rows before the cutoff | dates to ISO text, sorted | `fill_feature_gaps` (last known value); never fill the answer |
| grouping | `drop_mostly_empty_columns`, `drop_duplicate_rows`, `drop_near_copy_columns` | none | `cap_extreme_values` |
| unusual | `drop_mostly_empty_columns`, `drop_near_copy_columns` (not duplicates: repeats can be the signal) | none | none |

`apply_fix` keeps its status rule (`baseline_done` or `quoted`, `fixes.py:123`) and its quote-expiry and re-run behaviour.

### 2.6 Locked rows per type, and how child versions interact (HUMAN REVIEW)

- **classification, regression:** unchanged random split from the root (`verification.py:72`). For regression the stratify argument is dropped (it only works by accident through the `ValueError` fallback at `verification.py:73-74`; make it an explicit branch).
- **forecast:** the locked rows are the **newest period**: the last 20 percent of DISTINCT timestamps, never fewer than 10 periods, cut on a whole timestamp so ties do not straddle. Rows are time-ordered, never shuffled. The cutoff timestamp is stored with the root split (`splits/<root>/cutoff.json`). An optional gap of one forecast horizon is left unused between work and locked rows when lag features are used (scoring spec decides). A child inherits **by cutoff, not by content**: its locked rows are exactly the root's locked rows; every fix runs on the work part (before the cutoff) only, and the child file is `fixed work + root locked rows, untouched`. A fix that would add rows after the cutoff (filling gaps there) is refused. A fix that changes the time column is refused. This keeps every version scored on the same newest period and cannot leak the future into training.
- **grouping, unusual unlabelled:** no locked rows exist; `prepare_split` is not called (the quote and verification path for these types is the scoring spec's decision; flagged in section 7).
- **unusual labelled:** a stratified split that guarantees at least 10 odd rows in the locked part.

## 3. Discovery

### 3.1 Tool changes

`discover_datasets` and `search_datasets` (`tools.py:136`, `118`, schemas at `525-528`) gain an optional `task_type` enum (default `classification`; the model fills it from the goal after the decision step in regression spec section 3). Code, not the model, applies it. `ports.DatasetSource.search(query, limit, task=None)` gets an optional argument; sources that cannot use it ignore it. The gate action stays `DISCOVER`/`SEARCH`, level 0.

`prefilter` (`discovery.py:126`) becomes: drop a candidate only when its task list is KNOWN and lacks the wanted type. Mapping: classification <- "Classification"; regression <- "Regression"; forecast <- "Regression" AND (Time-Series characteristic OR a time-like column name); grouping <- "Clustering" or any plain table; unusual <- a rare-group dataset (OpenML minority share under 10 percent) or "Anomaly". An unknown list passes (as today for Hugging Face). `_quality` (`discovery.py:183`) gives the +0.5 to the wanted type. `from_curated` and `from_sample` read `task` from the data instead of hard-coding "Classification" (`discovery.py:108`, `114`). `explain` says in plain words what the dataset predicts ("a number: price").

For forecast, ranking adds a small bonus when column names contain date, time, year, month, week, day, or timestamp, and `look_at_dataset` returns a `time_column_guess`. The clarity filler list must stop treating "forecast", "growth" as empty (`clarity.py:15`), or "forecast my sales" is never searched (row 18, section 1).

### 3.2 Sources

| Source | Today | Change |
|---|---|---|
| UCI | `tasks` from the API (verified values: "Classification", "Regression", "Clustering"); "Time-Series" is under `characteristics` | Copy "Time-Series" into `tasks`; keep all targets (`target_col` is a list); drop the "not classification" note for other types (`uci.py:84`) |
| OpenML | `tasks` only from class count (`openml.py:77`) | classes 0 -> "Regression"; list filters exist and work (verified: `data/list/number_classes/0` returns numeric-target sets such as liver-disorders; `data/list/tag/time_series` works but is loosely used, since it returned JapaneseVowels); minority share from `MinorityClassSize / NumberOfInstances` (verified present) marks rare-group sets |
| Hugging Face | tag `tabular-classification` first (`huggingface.py:17`) | Tag by type: `tabular-regression`, `time-series-forecasting` (both verified to exist). Weak in practice: the top results by downloads were huge, "other"-licensed, multi-task or nested time-series sets that fail the plain-table test (`huggingface.py:82`). Keep HF last in the order; the hand-checked list carries the demo |
| Curated list | 12 classification items | Add `task` (default "classification") and `time_column`; `target` may be empty for grouping (`curated.py:41`) |

Row caps still apply. Forecast needs a fetch that keeps the NEWEST rows when a time-ordered file is truncated: add `keep: "head" | "tail"` to `fetch_csv`; the tool passes `tail` when `task_type` is forecast and a time column is found (`uci.py:101`, `openml.py:131`, `huggingface.py:115`). For rare-event sets the head cut can drop odd rows; the readiness finding "only the first N rows were kept" already exists in the tool result.

### 3.3 Proposed hand-checked entries (3 per new type)

Rows and targets are as read from the live services (verified) unless marked. Licences follow the existing convention: UCI pages state CC BY 4.0 (the UCI API has no licence field, so (unverified per id)); OpenML states `Public` or `public`.

**Regression**

| Id | Rows | Target | Licence | Why it is a safe demo |
|---|---|---|---|---|
| `uci:165` Concrete compressive strength | 1,030 (verified) | `Concrete compressive strength` | CC BY 4.0 (unverified per id) | 8 numeric inputs, no missing values, clear signal. Quick. Small: "1,030 rows is on the small side" shows honest wording |
| `oml:43939` California housing | 20,640 (verified) | `median_house_value` | `public` (verified) | Big enough for noticeable training; one text input (ocean proximity); the answer is cut off at the top (known, inferred), so the extreme-values finding fires honestly |
| `uci:1` Abalone | 4,177 (verified) | `Rings` | CC BY 4.0 (unverified per id) | Text input `Sex`; the answer has 28 values, a clean number case |

Optional fourth: `oml:42165` Ames house prices (1,460 rows, 81 columns, `SalePrice`, licence "NA": do not list without a human look). Typing-trap test only, not a demo: `uci:186` Wine Quality (answer 3 to 9).

**Forecast**

| Id | Rows | Time / target | Why |
|---|---|---|---|
| `uci:275` Bike Sharing (hourly) | 17,379 in the file (the UCI page says 17,389; verified) | `dteday` + `hr` / `cnt` | Clean and regular. Safe demo only after `casual` and `registered` are dropped (they add up to `cnt`, verified), which makes it the best leak demo |
| `uci:492` Metro Interstate Traffic Volume | 48,204 (verified; fits the cap) | `date_time` / `traffic_volume` | Real mess: repeated timestamps, many gaps, a 308-day hole. Good for the gap and duplicate findings; not the first demo |
| `uci:360` Air Quality | 9,357 in the file (page says 9,358; verified) | `Date` + `Time` (D/M/YYYY) / pick one column such as `C6H6(GT)` (UCI names no target) | The `-200` sentinel and two-column date; tests the sentinel and date-parsing findings. Needs a chosen target, so it exercises the target-choice card |

**Grouping** (reuse where possible, no new ids to trust)

| Id | Rows | Use | Why |
|---|---|---|---|
| `uci:292` Wholesale customers | 440 (verified) | six spending columns; `Channel`, `Region` as reference | Classic segmentation; small (flagged) |
| `uci:468` Online shoppers | 12,330 (curated) | visit behaviour columns; `Revenue` as reference | Large, mixed numeric and category |
| `uci:350` Credit card default | 30,000 (curated) | billing and payment columns; `Y` as reference | Already hand-checked; same dataset serves two types |

**Unusual**

| Id | Rows | Odd rows | Why |
|---|---|---|---|
| `oml:310` Mammography | 11,183 (verified) | 260, 2.3 percent (verified) | Labelled, 6 numeric columns, licence `Public` (verified) |
| `oml:40983` Wilt | 4,839 (verified) | 261, 5.4 percent (verified) | Labelled, near the upper edge of "rare" |
| `oml:1068` PC1 software defects | 1,109 (verified) | 77, 6.9 percent (verified) | Labelled, small, tests the "few odd examples" finding. Licence (unverified) |

Not listed: OpenML `1597` credit-card fraud (284,807 rows, 492 odd). It is far over the 50,000-row cap, and its download is probably over the 50 MB cap (inferred), so it would be refused or truncated into a different problem. UCI `53` Iris (150 rows) and `109` Wine (178 rows) are below the current 300-row floor; fine as tests, not as demo picks.

## 4. Offline sample datasets and synthetic generators

All are seeded numpy generators returning CSV bytes, like `samples.churn_csv` (`samples.py`) and `synth.make_csv` (`synth.py:14`). No network, no files committed.

### 4.1 Catalog entries (`samples.py` `CATALOG`, line 24; add keys `task` and `time_column`; `target` may be None)

| Id (`sample-...`) | Rows, seed | Columns | Designed to test |
|---|---|---|---|
| `sample-house-prices` | 3,000, seed 0 | `sqft`, `bedrooms`, `age_years`, `neighborhood` (4 values), `has_garage`, `price` (target, price = linear terms + one interaction + noise, R-squared about 0.8) | Strong-signal regression demo; keywords house, price, sale |
| `sample-store-sales` | 1,095 (3 years daily), seed 0 | `date` (ISO, sorted), `promo`, `temperature`, `units_sold` (target; weekly and yearly pattern plus trend plus noise) | Clean forecast demo; keywords sales, demand, orders |
| `sample-customer-segments` | 1,200, seed 0 | `customer_id` (unique), `annual_spend`, `visits_per_month`, `avg_basket`, `tenure_months`, `channel`; three separated groups; no target | Grouping demo, ID column ignored |
| `sample-odd-transactions` | 5,000, seed 0 | `amount`, `hour`, `merchant_type`, `distance_from_home`, `is_odd` (1.5 percent) | Labelled unusual demo; an unlabelled variant drops `is_odd` |

`from_sample` and the `search_datasets` sample match read `task` (`discovery.py:114`, `tools.py:70-79`).

### 4.2 Test generators (`synth.py` `KINDS`, line 11; prefix per type; each is 1,500 rows unless stated)

| Kind | Seed | Designed to test |
|---|---|---|
| `reg_flat` | 1 | Answer is pure noise: the free test cannot beat the average; trust Low; "not eligible" |
| `reg_strong` | 2 | R-squared about 0.9: eligible, High trust |
| `reg_tiny` | 3 (80 rows) | Too-little-data finding and penalty |
| `reg_leak_sum` | 4 | Columns `part_a` and `part_b` add up to the answer: sum leak finding, strong suspect |
| `reg_outliers` | 5 | 2 percent of answers 50 times larger: extreme-values and skew findings |
| `reg_text_target` | 6 | Answer written as `"$1,234.50"`, `"(12.00)"`, 5 percent blank: parse at selection, finding, locked rows unaffected |
| `reg_zeros` | 7 | 45 percent exact zeros |
| `reg_few_values` | 8 | Integer rating 1 to 5: ambiguous typing, user must pick |
| `reg_sentinel` | 9 | `-999` used for missing in two features |
| `ts_clean` | 10 (730 daily) | Regular series, passes all checks |
| `ts_gaps` | 11 | 15 percent of days missing in blocks |
| `ts_dup` | 12 | Three stores on the same dates: repeated-timestamp question |
| `ts_short` | 13 (40 periods) | Too little history, hard penalty |
| `ts_unsorted` | 14 | Shuffled rows: sorted, finding shown, split still time-ordered |
| `ts_future_col` | 15 | `returns_today` computed from the answer: same-period suspect |
| `ts_mixed_dates` | 16 | `3/10/2004` ambiguity plus 5 percent unparseable |
| `ts_irregular` | 17 | Random gaps between stamps |
| `ts_no_date` | 18 | No time column: floor F, reframe to regression |
| `grp_blobs` | 19 | Three clean groups |
| `grp_scale` | 20 | One column in the millions |
| `grp_one_col` | 21 | An ID plus one number: too few columns |
| `grp_noise` | 22 | Uniform noise: no structure (a later scoring test) |
| `grp_tiny` | 23 (60 rows) | Under the grouping floor |
| `odd_labelled` | 24 (5,000; 1.5 percent) | Rare group, enough odd rows |
| `odd_rare` | 25 (3,000; 3 odd rows) | Too few odd examples |
| `odd_unlabelled` | 26 (5,000) | No label: no verification |

`make_csv(kind, seed)` keeps its signature; classification kinds are untouched. A test asserts every kind is deterministic (same bytes for the same seed).

### 4.3 Offline source (`doubles/datasets.py`)

Add `eval/house-prices-table`, `eval/store-sales-table`, `eval/segments-table`, `eval/odd-table`, built from the catalog functions. `OfflineSource.search` returns the hit that matches `task` (today it ignores the query and returns one churn hit). The existing churn ids are unchanged so the current evals stay green.

## 5. Limits, cost and target-typing safety

- **Caps unchanged:** 50,000 rows and 50 MB (`config.py:36-37`). The only behavioural addition is `keep="tail"` for time-ordered files (section 3.2).
- **Cost:** every tool in this file is free (level 0), except applying a fix (level 1, still free). No AWS, no PayPal. The profile sample stays at 20,000 rows and 1.5 s (`profile.py:11-13`); the pairwise sum check is capped at 20 numeric columns so it stays inside that budget (inferred).
- **Storage:** unchanged lifecycle. The only new stored items are the forecast `cutoff.json` beside the split files and a nullable `time_column` on the version.
- **Target typing safety:**
  1. Code only proposes a type. The user's click or approval card decides, and the card states it in plain words ("predict a number" or "pick a group").
  2. Ambiguous numbers (3 to 20 values) always ask.
  3. Converting text to a number happens once, at the root, with a visible note, and only when at least 90 percent parse; the rest become empty and are counted in the finding.
  4. A column with a near-copy of the answer is dropped before any model sees it, for every type.
  5. A forecast without a verified time column never reaches the pilot.
  6. Wrong type means wrong score. Selecting a different type later re-runs readiness and invalidates the forecast and quote, as a data fix does today (`lifecycle.reopen_for_new_data`).

## 6. Tests first, slices, review flags

### 6.1 Tests to write before the code

Unit (`backend/tests/unit/`): `test_target_kind.py` (`test_numeric_many_values_is_number`, `test_wine_quality_style_is_ambiguous`, `test_text_money_parses`, `test_percent_and_parentheses`, `test_bool_is_category`), `test_find_time_column.py` (`test_iso_dates`, `test_date_plus_time_pair`, `test_ambiguous_day_month_flagged`, `test_unique_dates_not_dropped_as_ids`), `test_insights_regression.py` (`test_continuous_answer_no_smaller_group_finding`, `test_skew_zeros_outliers_findings`, `test_sum_of_columns_leak`, `test_penalty_cap_45`), `test_insights_forecast.py` (`test_no_date_is_F`, `test_gaps_and_duplicates`, `test_short_history`), `test_insights_unlabelled.py`, `test_insights_classification_golden.py` (**classification output byte-identical on the existing fixtures; write first**), `test_profile_types.py` (sentinel, `could_be_groups`, `time` part), `test_fixes_types.py` (per-type allow-list; no value-changing fix in v1; `test_fix_never_touches_rows_after_cutoff`), `test_discovery_task_filter.py` (`test_regression_dataset_not_dropped`, `test_forecast_prefers_time_series`, `test_unknown_task_passes`), `test_clarity_forecast_goal.py`, `test_synth_kinds.py` (determinism, row counts, planted property per kind), `test_samples_catalog_types.py`.

Contract (`tests/contract/`): `test_uci_source.py` additions (recorded detail for 165, 275, 492: tasks and Time-Series characteristic, multi-target), `test_openml_source.py` (regression from classes 0, minority share, `number_classes/0` list), `test_hf_source.py` (tag per type, nested columns rejected).

E2E (`tests/e2e/`): `test_regression_data_flow.py` (upload sample-house-prices, pick "a number", readiness, no balance finding, free steps up to the guard that stops before pilot), `test_forecast_split.py` (locked rows are the last period; a data fix leaves them byte-identical; a fix touching the newest period is refused), `test_text_target_select.py`, `test_discovery_by_type.py` (offline source returns a type-matching hit).

### 6.2 Slices

| # | Slice | Files | Acceptance | Review |
|---|---|---|---|---|
| 1 | Golden tests + `target_kind.py` + `profile._target_part` uses it | `target_kind.py`, `profile.py` | classification goldens unchanged; ambiguity cases pass | none |
| 2 | Offline data: samples, synth kinds, doubles | `samples.py`, `synth.py`, `doubles/datasets.py` | all kinds deterministic and have their planted property | none |
| 3 | `select_candidate` takes `task_type` and optional target; select card | `datasets.py`, `routes/projects.py`, `tools.py` | grouping selects with no target; ambiguous asks | gate unchanged |
| 4 | Readiness per type, profile additions | `insights.py` (+ small modules), `features.py` (sum-leak helper only if it does not change shipped behaviour), `profile.py` | findings and penalties of section 2; cap 45; goldens | none |
| 5 | Discovery by type, source changes, `keep="tail"`, clarity words, curated entries | `discovery.py`, `curated.py`, `curated.json`, sources, `ports.py`, `clarity.py` | filter and ranking tests; curated entries re-checked live before listing | none |
| 6 | Fixes per type, root-time cleanup, later prep steps | `fixes.py`, `datasets.py` | v1 allow-list only; prep steps need their own design | **HUMAN REVIEW** |
| 7 | Time-ordered locked rows and child inheritance by cutoff | `verification.py`, `tables.py` (`time_column`) | section 2.6 | **HUMAN REVIEW** (fee depends on it) |

Slices 1 to 5 are free and non-payment. Slice 7 touches the verification split, which decides whether the success fee is charged: flag it, keep the diff small, test on the mock provider.

### 6.3 Risks

- Thresholds in sections 2.1 to 2.4 are untested on real data (inferred). Expect tuning.
- A random split on a time series is the most damaging mistake: a model that has seen "tomorrow" scores high. Slice 7 must land before forecast is offered.
- `profile` must not slow down: the new pairwise and gap checks run inside the existing 1.5 s budget or are skipped.
- Hugging Face tag results are poor for the new types; discovery quality rests on the curated list and OpenML/UCI.
- Child versions after a value-changing fix are unsafe until prep steps exist; v1 avoids them on purpose.
- `-200`-style sentinels are only detected by a rule; unusual codes will pass.

### 6.4 Open questions for the owner

1. Panel data (several stores on the same dates): support one group column in v1, or refuse and ask for one series?
2. Grouping and unlabelled unusual: is there a locked-rows idea at all (for example stability on a second half), or compute-only with no check? (Decided in the scoring/payment spec; data tools assume none.)
3. Lower the grouping floor from 300 to 150 rows, and the unusual floor to 1,000?
4. Should the user pick the type on a card every time, or may the agent state it and the user correct it? (This spec: card every time.)
5. Are the Wine Quality style ambiguous numbers worth a two-button card, or default to groups?
6. Forecast gap between work and locked rows: one horizon, or none?
7. May we list `oml:1068` and `oml:40983` after a licence check?

## 7. Acceptance checklist

- [ ] Classification readiness, profile, discovery and fixes produce identical output on all existing fixtures.
- [ ] A numeric answer never produces a "smaller group" finding or a `balance` summary.
- [ ] Ambiguous numeric answers (3 to 20 values) always ask the user; the choice is stored in `projects.task_type`.
- [ ] Text answers like `$1,200` and `(12.00)` are read as numbers once, at selection, with a plain note.
- [ ] A sum-of-columns leak (Bike Sharing `casual + registered`) is found and dropped for regression and forecast.
- [ ] A forecast dataset keeps its date column, is time-sorted, and is refused (floor F) when none exists.
- [ ] The locked rows of a forecast are the newest period; a child version keeps them untouched; no fix may add or change rows after the cutoff.
- [ ] No v1 fix changes the values of a kept row.
- [ ] `discover_datasets` and `search_datasets` take `task_type`; regression, forecast, grouping and unusual datasets are no longer dropped by the classification filter.
- [ ] "forecast my sales" is not rejected as vague.
- [ ] Time-ordered files are truncated to the newest 50,000 rows, not the oldest.
- [ ] 12 hand-checked entries (3 per new type) re-checked live before they are shipped; unverified licences marked.
- [ ] Four sample catalog entries and all synth kinds exist, are seeded, deterministic and tested.
- [ ] `doubles/datasets.py` serves one hit per type offline.
- [ ] No payment, gate, ledger or webhook code changed; slice 7 reviewed by a person.
- [ ] `pytest` offline and the demo check (`tests/e2e/test_payments_and_demo.py`) pass.
