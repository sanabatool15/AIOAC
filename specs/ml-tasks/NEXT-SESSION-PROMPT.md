# Prompts for a new session

Copy ONE of these into a fresh Claude Code session. Branch: `claude/ml-task-types-spec` (specs only). Make the working branch from it, for example `claude/ml-task-types-build`.

## First, get the branch (on your PC, PowerShell)

```bash
git fetch origin
git checkout claude/ml-task-types-spec
git checkout -b claude/ml-task-types-build
```

## Prompt A: start building (recommended)

> Read `CLAUDE.md`, `specs/status.md`, `specs/audit-2026-11-11.md` and everything in `specs/ml-tasks/` (start with `00-overview.md`, then `07-audit-and-test-plan.md`). Work on branch `claude/ml-task-types-build`.
>
> Rules: ONE slice at a time, tests first; after each slice run `cd backend && env -u DATABASE_URL python -m pytest -q`, `cd frontend && npm run test:unit` and the matching Playwright spec, then commit that slice alone with a short plain explanation. Use sub-agents for read-only checks if useful. Slices that touch payments, the gate, lifecycle, quotes, verification or SageMaker packaging are HUMAN REVIEW: keep the diff tiny, explain it, and stop for my approval before moving on. Never call a real model, AWS or PayPal without asking me first. Never change the hard rules in CLAUDE.md.
>
> Order: (1) the four fixes in `specs/audit-2026-11-11.md` (data picker, done-screen receipt, ask_choice guard hole, claim guard narrowing as a reviewed diff); (2) slice S0, the audit test skeleton from `07-audit-and-test-plan.md` (`backend/tests/e2e/test_ml_task_types_audit.py` and `python -m evals.audit_ml_tasks`); (3) slice S1, `task_type` plumbing with classification moved behind the `TaskKind` interface and no behaviour change; then regression slices S2 to S5 as in `01-backend-ml-core.md`. After each slice run the audit matrix and paste it. Stop after S1 and show me the result before continuing.

## Prompt B: only review the specs

> Read `CLAUDE.md` and everything in `specs/ml-tasks/`. Do not change code. List contradictions between the files, missing slices, places where a hard rule in CLAUDE.md could be broken, and the OWNER DECISIONS I must answer before building (collect them from `02-success-and-payments.md` and the others into one numbered list with a recommendation each).

## Prompt C: owner decisions first

> Read `specs/ml-tasks/02-success-and-payments.md` and `00-overview.md`. Ask me the OWNER DECISIONS one group at a time (success fee for each task type, target wording, price impact, eligibility bar, unit/currency label), record my answers in a new file `specs/ml-tasks/decisions.md`, and update the specs to match. No code.
