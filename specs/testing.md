# Testing Strategy

The demo is what gets judged, so testing aims at one result: the core path works every time we record it. Time is spent where failure is most likely and most embarrassing.

## 1. Priorities

1. **Dataset search, storage and cleanup.** Does the agent find a usable dataset, store it, and remove the rest?
2. **Insights.** Are the findings correct and plainly worded for known datasets?
3. **Cost estimation.** How far is the estimate from the actual cost?
4. **Permission gate.** Can the agent ever spend or start paid work without approval and a verified payment?
5. **Payments and ledger.** Are repeats harmless and refunds correct?

## 2. Layers

Four test folders under `backend/tests/`. Only `real/` touches outside services; the other three are offline and never read the developer's `.env` (`conftest.py` isolates them).

| Layer | What it checks | Real or double |
|---|---|---|
| `unit/` | Pure logic on in-memory SQLite: estimator math, ledger, gate, lifecycle, readiness, agent tools and guards, architecture rules | No outside systems |
| `contract/` | Our code against each outside API as recorded or mocked HTTP, or mocked boto3: PayPal, OpenRouter, Azure, Hugging Face, UCI, OpenML, SageMaker | Mocked transport |
| `e2e/` | Full flows through the API on doubles: approve, pay, train, refund; payment never confirmed; repeated webhook; cap reached; Stop; agent flows. `test_payments_and_demo.py` is the demo check | `MockPaymentProvider` and scripted model from `backend/doubles/`; local training, local storage, SQLite are real |
| `real/` | Live PayPal sandbox, AWS, LLM, database and dataset sources, tiny and cheap | Real services. Skipped unless `RUN_REAL=1` and the keys exist |

Commands (from `backend/`): `pytest` (unit, contract, e2e; real skips), `pytest tests/e2e/test_payments_and_demo.py` (demo check), `RUN_REAL=1 pytest tests/real -v -s`.

### Agent evaluations
A small fixed set of goals and datasets. For each we record what the agent searched, what it chose, and whether the result was sensible. Run these repeatedly, because agents vary between runs. The goal is a pass rate we can watch, not a single green tick.

### Cost accuracy checks
For each finished test job, compare estimate, range and actual. Track how often the actual falls inside the range. This is the main measure of the estimator.

## 3. Safety checks that must always pass

- No paid action runs without an approved, unexpired quote.
- Training never starts before a verified payment.
- Actual cost never exceeds the cap.
- A repeated payment event changes nothing the second time.
- Leftover cloud resources are detected.

## 4. Demo check

`pytest tests/e2e/test_payments_and_demo.py` runs the core path on the mock payment double and fixed datasets, with no network, and reports pass or fail. It must pass before any task is called finished and before recording the video.

## 5. Real-service tests

Tests in `tests/real/` touch real AWS, the PayPal sandbox, the LLM, the database and live datasets. They are kept few, run deliberately with `RUN_REAL=1`, and counted against the budget. Each one is logged with its cost.

## 6. Agent harness (planned)

- **Rules:** short rule files describing the hard rules (no paid training before confirmed payment, sandbox only, no secrets, estimates always labeled).
- **Skills:** the PayPal toolkit guidance, the AWS cost notes, and the agent playbooks.
- **Hooks:** block commits that contain secrets, require a review note on edits to payment code, run the tests before a task is marked done.
