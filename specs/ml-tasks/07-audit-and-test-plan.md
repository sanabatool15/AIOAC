# Audit and test plan for all ML task types (read LAST)

Status: PLAN. Nothing is built. Purpose: one place that says how every piece of code written for the other specs in this folder is tested and audited, and how progress is shown. The audit tests are written FIRST (slice S0) as a skeleton that SKIPS what is not built yet, then fill in as each slice lands. At the end the audit matrix must be all PASS or an explained SKIP.

## 1. The idea: an audit matrix

A matrix of task type (rows) by stage (columns). Each cell is a test. A cell is one of:
- PASS: built and working.
- SKIP (slice Sn not built): expected for now. The reason names the slice.
- FAIL: built but broken, or a hard rule broken. FAIL blocks the slice.

Task types: `classification` (built, must be PASS from day one), `regression`, `forecast`, `grouping`, `unusual`.
Stages (columns):

| # | Stage | What the cell proves |
|---|---|---|
| A1 | task type stored | `Project.task_type` is set by the allowed tool/route, default `classification`, survives reload, API returns it |
| A2 | data readiness | readiness and profile give plain findings for that type (no jargon words) |
| A3 | free test | baseline gives the plain score and the plain "simple guess" for that type, on held-out rows, deterministic |
| A4 | pilot and forecast | free pilot runs, forecast has band and confidence, Not-eligible reason is plain |
| A5 | quote | quote prices the pinned model type, cap and fee rules unchanged |
| A6 | hold and gate | training refused before a server-confirmed hold; refused if data or model type differs from the quote |
| A7 | training and verification | local backend trains the pinned type; locked rows never appear in work rows; verification computed once |
| A8 | settle | hit, miss, stop and our-failure on the mock provider; capture and void amounts correct; ledger entries correct; repeat is harmless |
| A9 | predict | one record, batch CSV, download; shape per type; plain note "an estimate, not a promise" |
| A10 | agent | scripted model chooses the right task type and tool order; never spends; plain words; no promise |
| A11 | blocks and activity | chat blocks and activity sentences for the type exist and contain no raw cents or jargon |
| A12 | UI | browser test of the screens for the type (phone and desktop) |
| A13 | tenant isolation | every new route is owner-scoped (404 for others) and classified in the isolation test |
| A14 | limits | time/row caps hold, tool result under 1800 chars, prompt under the length cap |

## 2. Files to create (slice S0 creates the skeletons)

Backend (all offline, no network, no real model):
- `backend/tests/e2e/test_ml_task_types_audit.py`: the matrix. Parametrised over the five task types and stages A1 to A14. Each parametrised case calls a small helper that checks `SLICES_BUILT` (a set in `backend/tests/helpers/ml_slices.py`, e.g. `{"S1", "S2"}`) and calls `pytest.skip("slice S3 not built")` when the slice that provides that stage is not in the set. When a slice is built, its id is added to the set in the SAME commit, which turns SKIP into a real test. A test that is built but FAILs fails the suite.
- `backend/tests/helpers/ml_slices.py`: `SLICES_BUILT`, a table `STAGE_NEEDS = {("regression", "A3"): "S2", ...}`, and synthetic data builders (shared with `evals/synth.py`).
- `backend/tests/unit/test_task_kind_contract.py`: iterates the `TaskKind` registry (see `01-backend-ml-core.md`) and asserts each implementation provides every method (target typing, split, families, score, simple guess, plain wording, predict shape), returns JSON-serialisable values, never uses jargon in strings, is deterministic for a fixed seed, and never reads locked rows.
- `backend/tests/unit/test_ml_plain_language.py`: scans every user-visible string produced for each type (findings, scores, forecast reasons, quote terms, receipt lines, block texts, activity lines, skills) against a banned-word list (f1, precision, recall, MAE, RMSE, R2, r-squared, train/test split, hyperparameter, instance type, leakage, feature importance) and checks money only via dollars.
- `backend/tests/e2e/test_ml_money_invariants.py`: for each task type the same payment scenarios on `MockPaymentProvider` (hit, miss, stop, our failure, repeated capture, hold never confirmed, cap reached, quote pin mismatch). Same assertions as `test_payments_and_demo.py`: never capture above the hold or the compute cap, success fee only if verified, void the rest, ledger append-only, repeat harmless. HUMAN REVIEW file.
- `backend/tests/e2e/test_ml_locked_rows.py`: locked rows never in work rows, root-version inheritance after a data fix, time-ordered locked rows for `forecast`.
- `backend/tests/unit/test_ml_tool_limits.py`: result size < 1800 characters for every free tool for each type on a wide synthetic file, runtime bounds (fake clock where possible), prompt length under the cap (currently 4800 in `tests/unit/test_context.py` and `test_agent_fixes.py`, 5200 for the long state block in `test_persona.py`; do not raise without saying so).
- `backend/tests/contract/test_sagemaker_task_types.py`: the training script gets `task_type` and `family` hyperparameters, builds the right pipeline, writes `metrics.json` with the normalised fields, partial save rules per family (mocked boto3, no AWS).
- `backend/tests/e2e/test_tenant_isolation.py` (edit): classify every new route in `OTHER_PROTECTED` or the project routes list.
- `backend/tests/unit/test_architecture.py` (existing): must stay green (no SQL in services, app never imports doubles).

Frontend:
- `frontend/unit/ml-task-views.test.ts`: pure view functions for each type (target card copy, free-test lines, result lines, metric/groups/forecast_series/unusual blocks) including null handling and no raw cents or decimals.
- `frontend/tests/ml-task-types.spec.ts` (Playwright, uses `backend/tests/browser_server.py` with a scripted model and offline datasets per type): one flow per type from goal to result and Model tab, at desktop and phone width.
- Existing guards stay green: `unit/no-raw-money.test.ts`, the a11y checks, `unit/ui-*.test.ts`.

Evals (offline by default):
- `backend/evals/cases/*`: one new case per type plus "not supported" (goal to expected task type and tool order), using the scripted model.
- `backend/evals/tone_cases/*.json`: new tone cases from `03-agent.md` (house price, sales next month, customer segments, strange payments, tiny data, flat result, "why is it off by $20,000?"). Real-model runs only with the owner's yes, 1 repeat first, pass bar mean >= 4 and no score < 3.
- `python -m evals.audit_ml_tasks`: prints the audit matrix (PASS / SKIP(Sn) / FAIL) from a pytest run's JUnit XML or by calling the same helpers; exit code 1 if any FAIL. Use it in every slice report.

Opt-in (never in the default run; each needs `RUN_REAL=1`, paid ones also `RUN_PAID=1`, and the owner's yes):
- `backend/tests/integration/test_ml_task_types_live.py`: tiny live checks (dataset sources per type, LLM answers a task-type decision on 3 goals, one capped SageMaker job per new family at about 1 cent each).
- `backend/tests/perf/` (marker `perf`, excluded by default): timing benchmark per family and size (see `06-latency-cost-and-limits.md`); writes a table to paste into `specs/integration-testing.md`.

## 3. Slice by slice: tests written first

| Slice | What it builds | Tests that must exist and fail first |
|---|---|---|
| S0 | audit skeleton | the matrix runs, every non-classification cell SKIPs with its slice id, classification cells that already work PASS |
| S1 | `task_type` plumbing, target typing, `TaskKind` with classification behind it (no behaviour change) | contract test for the interface; all existing suites unchanged and green; A1 and the classification row stay PASS |
| S2 | regression free test (baseline) | A2, A3 for regression: typical error and "simple guess = the average", jargon scan, determinism |
| S3 | regression pilot and forecast | A4, A5: eligibility, Not-eligible reasons, quote pins family and type |
| S4 | regression training and verification (HUMAN REVIEW) | A6, A7, A8 on the mock provider: hit, miss, stop, failure, repeat; locked rows; ledger |
| S5 | regression predict and model tab | A9, A11, A12 (UI copy and blocks) |
| S6 | agent: task-type decision and tools | A10 for all five types with the scripted model; claim-guard honest-phrase tests; ask_choice hole fixed |
| S7 | forecast (time-ordered split, naive baselines) | A2 to A9, A12 for forecast incl. time-ordered locked rows |
| S8 | grouping | A2 to A9, A12 for grouping with its own honest success definition (see `02`) |
| S9 | unusual | same for unusual |
| S10 | Improve, "Try a higher target", data-fix tools per type | A8 for the second round; fixes allow-list tests |
| S11 | cost calibration and perf | measured table recorded; cost accuracy report per type |

Rule: a slice is not done until (1) its new tests pass, (2) the full backend suite, `npm run test:unit` and its Playwright spec pass, (3) `python -m evals.audit_ml_tasks` shows no FAIL and the expected cells changed from SKIP to PASS, (4) the slice id is added to `SLICES_BUILT` in the same commit, (5) human-review slices were explained and approved.

## 4. Hard-rule checks that run in every slice

1. No paid work before a server-confirmed hold (gate tests, A6).
2. Never capture above the hold or the compute cap; success fee only if verified; void the rest (A8).
3. Ledger and webhook tables insert-only; a repeated capture or webhook changes nothing (A8).
4. No secrets in the repo or logs: `RunLog` scrubbing test stays green; secret scan of new files.
5. Plain language: banned-word scan on all user-visible strings (`test_ml_plain_language.py`) and `JARGON` in `evals/run.py`.
6. No accuracy promise: `makes_promise` on agent replies and on all static copy; every estimate carries `is_estimate` or an estimate note.
7. Locked test rows never used for choices (A7).
8. Owner scoping for every new route (A13).
9. Sandbox only: PayPal provider refuses other hosts (existing contract test stays green).

## 5. Commands (from `/home/user/AIOAC`)

```bash
cd backend && env -u DATABASE_URL python -m pytest -q
cd backend && env -u DATABASE_URL python -m pytest -q tests/e2e/test_ml_task_types_audit.py
cd backend && env -u DATABASE_URL python -m evals.run --fake --repeats 1
cd backend && env -u DATABASE_URL python -m evals.audit_ml_tasks
cd frontend && npm run test:unit
cd frontend && npm run test:e2e
```

Opt-in, only with the owner's yes: `RUN_REAL=1 python -m evals.tone --model <deployment> --repeats 1`, and `RUN_REAL=1 RUN_PAID=1 pytest tests/integration/test_ml_task_types_live.py -v -s`.

Tip: `npm run test:e2e` takes about 10 minutes; run it in the background and wait for the summary.

## 6. Final audit (end of the whole project)

1. The matrix has no FAIL and no SKIP except cells explained in `specs/status.md` (for example "grouping has no success fee by decision").
2. Four read-only sub-agent audits, like `specs/audit-2026-11-11.md`: (a) backend routes vs `specs/api.md`, (b) frontend client vs backend, (c) UI flow and browser tests, (d) agent tools, blocks, gate and prompt. Each reports a severity table; no high items open.
3. One real-model tone run per new type (1 repeat) with the owner's yes; scores recorded in `specs/integration-testing.md`.
4. One real capped SageMaker job per new family (about 1 cent each) with the owner's yes; cost accuracy report per type.
5. Update `specs/status.md`, `specs/api.md`, `specs/db.md`, `specs/agent.md`, `specs/training.md`, `specs/payments.md` (HUMAN REVIEW), `specs/breakpoints.md` so the older specs match reality.
6. Owner click-through with the real PayPal sandbox buyer for one regression project (breakpoints F2).

## 7. Open questions

1. Where should `SLICES_BUILT` live if the owner prefers markers? (Option: `@pytest.mark.slice("S3")` plus a conftest hook that skips when not built; same effect.)
2. Is the audit command allowed in CI? (Offline, about 5 minutes.)
3. Which task type is the demo for the next video: regression is recommended.
