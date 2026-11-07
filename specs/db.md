# Database Schema

Design level only. Exact column types are decided when the code is written.

## 1. Principles

- Money is stored as whole cents, never decimals.
- The ledger and webhook records are insert-only.
- Every table has an id and a created time. Ownership: a project has `user_id` and `org_id` (both set for every new row; foreign keys, indexed together as `ix_projects_org_user`). All other tables belong to a project and reach their owner through `project_id`; they carry no owner columns. The API enforces the rule (`specs/api.md` section C). The inherited `org_id` column on other tables is unused.
- SQLite for the demo, written so it works on Postgres.
- The database records what exists; files themselves live in object storage.

## 2. Entities

### Project
One prediction problem from start to finish.
Fields: goal text, task type, status (see spec1.md section 5), chosen dataset version, readiness grade, trust level, baseline result, timestamps.

### Dataset candidate
A dataset found during search, held temporarily.
Fields: project, source, source link, license, size, expiry time, status (candidate, chosen, discarded).

### Dataset version
The chosen dataset and each cleaned version of it.
Fields: project, parent version, storage location, row and column counts, target column, notes on what was changed.

### Insight report
Measurements and plain-language findings for a dataset version.
Fields: dataset version, measurements, findings (OK or NOTE), readiness grade.

### Baseline run
The free test.
Fields: project, dataset version, result, comparison with a simple guess, sample sizes and timings used by the cost estimator.

### Quote
Fields: project, estimate, low, high, cap (estimate, low, high and cap include the success fee), compute cap, success fee, forecast, breakdown, price config version, expiry, approved time.

### Payment (a PayPal hold, table `payments`)
Fields: project, quote, provider, provider order id, authorization id, hold amount, compute amount, fee amount, state (`none`, `held`, `compute_captured`, `fee_captured`, `fee_skipped`, `released`, `voided`, `expired`, `declined`), capture ids, captured and released amounts, verified flag (set only in `held`). Unused holds expire after 24 hours. See `payments.md`.

### Forecast
Fields: project, target, confidence, band low, band high, predicted metric, eligible flag, reason, pilot details.

### Ledger entry (append-only)
Fields: project, kind (`compute_capture`, `fee_capture`), positive amount charged to the buyer, unique key, time. A void moves no money and is recorded on the hold, not in the ledger.

### Webhook event (insert-only)
Fields: event id (unique), type, raw content, received time.

### Training run
Fields: project, backend, instance type, start and end times, accumulated cost, stopped-at-cap flag, result, status, `dataset_version_id` (nullable: the data the run trained on).

### Model
Fields: project, training run, storage location, quality measures, visibility (private or public). Version fields (all nullable except `is_current`, added by `--upgrade`): `version_no` (1..n per project), `dataset_version_id`, `forecast_id`, `quote_id`, `is_current` (bool, default false), `verified_value` (score on the locked rows), `passed` (met the target).
Rule: at most one model per project is current (`set_current` clears the others in one transaction). Training makes the new model current if it passed verification and the current one did not or is no better, or if no model passed and its verified value is the best; a newer worse model never replaces a better current one. Old rows have none of these set: they are read as version 1..n by creation time, the newest being current unless some row has `is_current` set. Nothing is back-filled.

### Agent run and agent step
The trace of everything the agent did.
Fields: run (project, start, end, limits used) and steps (order, kind: model call, tool call, gate decision, tool result, summary, cost of the call).

### Spend budget
A single running record of actual AWS spend, used by the global guard.

### Share (public result link, table `shares`)
Fields: id, `project_id` (foreign key, indexed), `token` (unique, `secrets.token_urlsafe(32)`), created time, `revoked_at` (null while active). A project has at most one active share; revoking sets `revoked_at` and keeps the row. The public route finds a share by token and only while `revoked_at` is null. HUMAN REVIEW: the token is the only secret. New table: run `python -m app.db.init` to create it, and on Supabase enable row level security on `shares` (no policies; the API connects with the table owner role).

### Funding campaign and contribution (removed, unused)
Crowdfunding was dropped from the product. The tables may still exist in the code but nothing uses them.

### Organization
A tenant. Fields: id, name, created time. Signup creates a personal one named after the email.

### User
Fields: unique indexed `email` (stored lower-case), `password_hash` (salted scrypt, never the password), `org_id` (foreign key to organizations). Created together with its organization in one transaction. Projects created before login have no owner and cannot be reached; there are no migrations, so delete an old local `aioac.db`.

## 3. Relationships

A project has many candidates, dataset versions, quotes and agent runs. A quote leads to at most one payment hold. A hold has up to two ledger entries (compute and fee). A project has at most one forecast per pilot run. A project has at most one active training run and ends with at most one model.

## 4. Integrity rules

0. A project is only served to the user and org that own it; anything else is a 404.

1. A project can only be marked paid if a server-confirmed hold exists for its approved quote.
2. A training run cannot start without that paid state.
3. Ledger and webhook tables accept inserts only.
4. Total captures for a hold never exceed the hold, and compute is never captured above the compute cap. A capture on a voided or fully captured hold is refused.
5. Accumulated training cost can never exceed the quote's cap.

## 4a. Upgrading an existing database

There are no migrations. `python -m app.db.init --check` reports what an existing database lacks compared with the models (read-only, exit 1 if anything is missing). `--upgrade` (dry run) and `--upgrade --yes` add only missing tables, columns (nullable, or NOT NULL with a safe default) and indexes, in one transaction. It never drops, renames or alters an existing column. Changing or removing a column still means a new database. Code: `app/db/check.py`.

## 5. Not decided yet

- How long traces and model files are kept.
- Whether cleaned versions are stored in full or as change lists.
