# Testing Strategy

The demo is what gets judged, so testing aims at one result: the core path works every time we record it. Time is spent where failure is most likely and most embarrassing.

## 1. Priorities

1. **Dataset search, storage and cleanup.** Does the agent find a usable dataset, store it, and remove the rest?
2. **Insights.** Are the findings correct and plainly worded for known datasets?
3. **Cost estimation.** How far is the estimate from the actual cost?
4. **Permission gate.** Can the agent ever spend or start paid work without approval and a verified payment?
5. **Payments and ledger.** Are repeats harmless, and are captures and voids correct (never a capture above the hold or the compute cap)?

## 2. Layers

### Unit tests (fast, no network)
Estimator math, ledger rules, gate rules, readiness grading, plain-language formatting.

### Scenario tests with the mock provider
Full flows with a mock payment provider and a local training backend: approve then hold then train then verify then capture and void; hold never confirmed; repeated webhook; cap reached mid-run; user presses Stop (compute used so far, no fee); target missed (compute captured, no fee); our own failure (whole hold voided); forecast too low (not sold).

### Agent evaluations
A small fixed set of goals and datasets. For each we record what the agent searched, what it chose, and whether the result was sensible. Run these repeatedly, because agents vary between runs. The goal is a pass rate we can watch, not a single green tick.

### Cost accuracy checks
For each finished test job, compare estimate, range and actual. Track how often the actual falls inside the range. This is the main measure of the estimator.

## 3. Safety checks that must always pass

- No paid action runs without an approved, unexpired quote.
- Training never starts before a server-confirmed hold.
- A capture or void repeated with the same request id moves no money a second time.
- The success fee is never captured unless verification passed.
- Actual cost never exceeds the cap.
- A repeated payment event changes nothing the second time.
- Leftover cloud resources are detected.

## 4. Demo check

A single command (defined when the project is scaffolded) runs the core path against the mock provider and fixed datasets, and reports pass or fail. It must pass before any task is called finished and before recording the video.

## 5. Real-service tests

Tests that touch real AWS or the PayPal sandbox are kept few, run deliberately, and counted against the budget. Each one is logged with its cost.

## 6. Agent harness (planned)

- **Rules:** short rule files describing the hard rules (no paid training before confirmed payment, sandbox only, no secrets, estimates always labeled).
- **Skills:** the PayPal toolkit guidance, the AWS cost notes, and the agent playbooks.
- **Hooks:** block commits that contain secrets, require a review note on edits to payment code, run the tests before a task is marked done.
