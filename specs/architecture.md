# Architecture

Backend layout and rules. Behaviour lives in the other specs; this file says where code goes.

## Folder tree (`backend/`)

```
app/
  main.py  config.py  deps.py   app start, settings (one place), FastAPI dependencies
  ports.py                      all interfaces and shared data types: PaymentProvider, TrainingBackend,
                                DatasetSource, LLM client, Storage, JobRunner
  db/                           engine, session, tables. Nothing else
  repositories/                 the ONLY code that talks to the database, one file per thing
                                (projects, datasets, quotes, payments, ledger, webhooks, training_runs, traces, ...)
  services/                     business logic, no SQL
    agent/                      loop, tools, context, memory, run log, guards, skills loader
    data/                       datasets, discovery, features, analysis, insights, baseline, samples
    cost/                       cost estimate, prices, quotes, budget guard, accuracy report
    payments.py training.py gate.py lifecycle.py
  integrations/                 everything outside our process, one folder per system
    paypal/  aws/  llm/  datasets/  jobs/  storage/  training_local/
    factory.py                  builds the configured integration for each port
  routes/                       HTTP only: parse, call a service, return
  skills/                       markdown playbooks for the agent (not code)
doubles/                        in-memory stand-ins (mock payments, scripted model, offline dataset source)
tests/  unit/ contract/ e2e/ integration/ helpers/    see testing.md
evals/                          real-model evaluation harness (see agent/07)
```
Outside `backend/`: `infra/terraform/` (AWS bucket, roles, budget alert), `specs/`, `frontend/` (Next.js app on a mock API; backend wiring is planned in `frontend-integration.md`).

## Dependency direction

`routes -> services -> repositories / integrations -> db / ports`

- Services get integrations through `ports.py` types, never import a vendor library.
- Repositories take a session and return rows or plain values; they contain no business rules.
- `app/` never imports `doubles/`. Tests and evals inject doubles by monkeypatch, dependency override or constructor argument.
- `tests/unit/test_architecture.py` fails if a service imports sqlalchemy or runs SQL, or if `app/` imports `doubles`.

## Add an integration (new outside system)

1. If it is a new kind of thing, add a Protocol to `ports.py`. Otherwise reuse the existing one.
2. Create `integrations/<system>/` with the implementation. Keep all of that vendor's code there (clients, cost math, scripts).
3. Add a `get_...` branch in `integrations/factory.py` and a setting in `config.py` plus a placeholder in `.env.example`.
4. Add a contract test in `tests/contract/` on mocked HTTP or boto3. Add a small `tests/integration/` check if live access is cheap and safe.
5. If tests need a stand-in, add it to `doubles/`, not to `app/`.

## Add a repository

1. Create `repositories/<thing>.py` with functions that take a session. All SQL for that table goes here.
2. Add a table in `db/tables.py` if needed (delete the old local `aioac.db`; there are no migrations).
3. Services call the repository; they never build queries. Ledger and webhook repositories are insert-only (CLAUDE.md hard rule 4).
4. Cover it with a unit test on in-memory SQLite.
