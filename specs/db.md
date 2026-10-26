# Database Schema

Design level only. Exact column types are decided when the code is written.

## 1. Principles

- Money is stored as whole cents, never decimals.
- The ledger and webhook records are insert-only.
- Every table has an id, a created time, and a reserved `org_id` (empty for now) so multi-tenancy can be added later without a rewrite. Nothing enforces it yet.
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

### Payment hold (`payment_holds`)
Fields: project, quote, provider, provider order id, authorization id, hold amount, compute amount, fee amount, state (`none`, `held`, `compute_captured`, `fee_captured`, `fee_skipped`, `released`, `voided`, `expired`, `declined`), capture ids, captured and released amounts, verified flag (set only in `held`). Unused holds expire after 24 hours. See `payments.md`.

### Forecast
Fields: project (the job), target, confidence, band low, band high, predicted metric, eligible flag, reason, pilot details.

### Ledger entry (append-only)
Fields: project, kind (`compute_capture`, `fee_capture`), positive amount charged to the buyer, unique key, time. A void moves no money and is recorded on the hold, not in the ledger.

### Webhook event (insert-only)
Fields: event id (unique), type, raw content, received time.

### Training run
Fields: project, backend, instance type, start and end times, accumulated cost, stopped-at-cap flag, result, status.

### Model
Fields: project, training run, storage location, quality measures, visibility (private or public).

### Agent run and agent step
The trace of everything the agent did.
Fields: run (project, start, end, limits used) and steps (order, kind: model call, tool call, gate decision, tool result, summary, cost of the call).

### Spend budget
A single running record of actual AWS spend, used by the global guard.

### Funding campaign and contribution (removed, unused)
Crowdfunding was dropped from the product. The tables may still exist in the code but nothing uses them.

### User (placeholder)
Minimal identity for the demo; real login is deferred.

## 3. Relationships

A project has many candidates, dataset versions, quotes and agent runs. A quote leads to at most one payment hold. A hold has up to two ledger entries (compute and fee). A project has at most one forecast per pilot run. A project has at most one active training run and ends with at most one model.

## 4. Integrity rules

1. A project can only be marked paid if a server-confirmed hold exists for its approved quote.
2. A training run cannot start without that paid state.
3. Ledger and webhook tables accept inserts only.
4. Total captures for a hold never exceed the hold, and compute is never captured above the compute cap. A capture on a voided or fully captured hold is refused.
5. Accumulated training cost can never exceed the quote's cap.

## 5. Not decided yet

- How long traces and model files are kept.
- Whether cleaned versions are stored in full or as change lists.
