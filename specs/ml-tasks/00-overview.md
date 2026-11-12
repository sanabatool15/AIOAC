# All classical ML on AIOAC: overview and index

Status: BUILT (2026-11-12): regression, forecast, grouping and unusual records are implemented (task_wording, pilot, forecast, verification, model_use, SageMaker script, UI). Not yet run in a paid end-to-end check on AWS. The text below is the original design record. Written 2026-11-11 on branch `claude/ml-task-types-spec` (made from `claude/brave-hypatia-6hf77z`, tip `ce72a07`). Read `CLAUDE.md` and `specs/status.md` first.

## 1. Goal in one paragraph

Today AIOAC predicts only a yes/no answer or a few groups ("classification"). The product promise is "describe any prediction problem in plain words". So the platform must support ALL classical (scikit-learn, tabular) machine learning: predicting a number, forecasting over time, finding groups, and spotting unusual records. Finding data already works. What changes is the model code, how success is measured and verified, what the agent says, and a few UI places where a result or prediction is shown. Deep learning, text, images and audio stay OUT of scope.

## 2. The five task types (ids are used in code, DB, API and tests)

| id | Plain name shown to the user | Example | Has an answer column? | Status |
|---|---|---|---|---|
| `classification` | yes/no or a few groups | will this customer leave? | yes | BUILT |
| `regression` | a number | what price will this house sell for? | yes (a number) | plan |
| `forecast` | numbers over time | how many orders next month? | yes (a number) plus a date column | plan |
| `grouping` | natural groups | which kinds of customers do I have? | no | plan |
| `unusual` | records that look unlike the rest | which payments look strange? | no (or rare labels) | plan |

`Project.task_type` already exists in `backend/app/db/tables.py` (unused). Default stays `classification` so every existing project and test behaves exactly as today.

## 3. Rules that never change (CLAUDE.md)

1. Paid training starts only after the SERVER has confirmed the PayPal hold. 2. Sandbox only. 3. No secrets in the repo. 4. Ledger append-only, webhooks idempotent. 5. Hard spend cap per job; compute always captured at actual cost; success fee only if verified on the locked test set; the rest voided; our failure voids everything. 6. Never guess PayPal endpoints. 7. Never promise accuracy: estimates are labelled, results are measured on held-out data. 8. Plain language in the UI and agent: no F1, MAE, R2, "train/test split", instance names.

HUMAN REVIEW (small diffs, explained): payments, webhooks, ledger, secrets, spend caps, gate, lifecycle, quotes, verification split, SageMaker packaging. Each spec marks the slices that touch these.

## 4. The spec set (read the one you need)

| File | Covers |
|---|---|
| `01-backend-ml-core.md` | model families, scores, baselines, pilot, forecast, locked verification, training local and SageMaker, predict, data model, the `TaskKind` strategy refactor |
| `02-success-and-payments.md` | what "success" means per type, targets, eligibility, success fee, quote, receipt wording, money invariants, OWNER DECISIONS |
| `03-agent.md` | task-type decision step, prompt, tools, skills, guards, tone cases and evals |
| `04-ui.md` | screens and components that change, copy, blocks, adapters, UI tests |
| `05-data-and-discovery.md` | target typing, readiness and profile per type, discovery filters, offline sample datasets |
| `06-latency-cost-and-limits.md` | run times, quotes, caps, free-tool time budgets, calibration, benchmarks |
| `07-audit-and-test-plan.md` | the audit test file design, slice-by-slice tests, definition of done (LAST) |

Older, related: `specs/regression-and-task-types.md` (first design), `specs/agent-data-scientist.md` (agent plan, phases 1-5 built), `specs/audit-2026-11-11.md` (fix list for the merged UI).

## 5. Build order (summary; each spec has the detailed slices)

0. Do the audit fixes first (`specs/audit-2026-11-11.md`: data picker render, done-screen receipt, ask_choice guard hole, claim guard narrowing). They are independent of ML types but the UI depends on them.
1. S0: audit test skeleton (`07-audit-and-test-plan.md`): a matrix test that shows PASS, SKIP (slice not built) or FAIL per task type and stage, so progress is visible from day one.
2. S1: `task_type` plumbing, target typing, `TaskKind` interface with `classification` moved behind it, no behaviour change (all existing tests must stay green).
3. Regression end to end (free test, pilot and forecast, training and verification, predict, UI copy, agent). First new type: most asked for, same pipeline shape.
4. Forecast (time-ordered split, naive baselines).
5. Grouping and unusual (no accuracy; different success definition, see `02`).
6. Improve and "Try a higher target" per type; data-fix tools per type.
7. Calibration of cost with real capped jobs (needs owner approval, `RUN_REAL=1 RUN_PAID=1`).

## 6. Time reality

The hackathon deadline is 2026-11-12 12:00 pm PT (internal target 2026-11-11). None of this is needed for that demo. For the demo the agent says plainly "I cannot predict exact numbers yet" and offers the nearest yes/no or price-band version. This plan is the post-hackathon roadmap. Each type is a multi-day, reviewed piece of work, not a one-session change.

## 7. How to work on it (for every session)

One slice at a time. Tests first. Run `cd backend && env -u DATABASE_URL python -m pytest -q` (about 4.5 min), `cd frontend && npm run test:unit`, and the matching Playwright spec. Commit each slice separately with a short explanation; payment, gate, verification, quote and lifecycle slices are explained for human review and never merged silently. No real-model, AWS or PayPal call without the owner's yes. Record results in `specs/status.md` and `specs/integration-testing.md`.

## 8. Known open facts (from audits and from writing these specs)

Defects in code that exists TODAY (found while reading; fix independent of the ML work, see each spec for file and line):
- Money wording contradicts CLAUDE.md rule 5 (compute is always captured): `frontend/components/shell/pay-prompt.tsx:17` ("If it is missed, the hold is released") and `frontend/lib/pay-timeline.ts:56-59` ("Target missed. Charged $0"). Copy only, but money wording: HUMAN REVIEW. (02, 04)
- The "Try a higher target" card is not rendered on the done screen (`result-view.ts:102-108` helpers have no callers) while `tests/higher-target.spec.ts` expects it. (04)
- `blocks.py:57-59` and `context.py:174-176` read `accuracy` keys directly; they would break a turn for any other task type. (03)
- `features.py:8-17,49-55` drops a mostly-unique date column as a row ID and drops duplicate rows: fatal for forecast. `verification.py` splits with a shuffle: invalid for time series. Data fetchers keep the FIRST 50,000 rows, losing the newest period. (01, 05)
- `gate.py:97-99` pins data version and model family but not the task type (tiny change, HUMAN REVIEW). (01)
- `clarity.py:10-20` filler list contains "forecast" and "growth": "forecast my sales" is probably rejected as vague (inferred). (05)
- Calibration risk: replacing the 240 s startup placeholder with the measured ~65 s can make `CapTooSmall` appear AFTER the hold is placed; propose a cap floor in `create_quote` (HUMAN REVIEW). A 10-15 minute demo job is not reachable with the current families; fixed fees dominate (about 53 cents). (06)
- Free routes `POST /projects/{id}/baseline` and `POST /chats/{id}/pilot` have no timeout (only the agent path has 60 s); one-hot encoders are dense and uncapped (memory risk). (06)

Where the OWNER DECISIONS are collected (answer these before building the matching slices): `02-success-and-payments.md` D1-D10 (success fee per type, target form, wording), `01-backend-ml-core.md` OQ1-OQ10, `03-agent.md` (8 questions), `04-ui.md` (10 questions, e.g. who sets the unit label), `05-data-and-discovery.md` (7 questions), `06-latency-cost-and-limits.md` section 7.4.

Other open facts:
- 2 frontend unit tests fail on the UI-pass code (`no-raw-money`, card gradient) and 14 browser tests wait for a data picker that is not rendered; see `specs/audit-2026-11-11.md`.
- Real PayPal sandbox plus SageMaker has never been clicked through in a browser (breakpoints F2).
- The tone eval has one real-model run only (gpt-5.4, mean 4.62); re-run after changes.
- These spec files are long (each 4,000-8,500 words) because of tables with file:line references. Read the section you need; each ends with an acceptance checklist.
