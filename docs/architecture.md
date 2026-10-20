# Architecture

## Layers (backend/app)
- `routes/` : thin HTTP handlers. Validate input, call a service.
- `services/` : business logic (cost estimate, payment confirmation, job flow).
- `repositories/` : all database access. `ledger` and `webhooks` are insert-only.
- `providers/payments/` : `PaymentProvider` interface, `mock` (tests), `paypal` (sandbox).
- `providers/training/` : `TrainingBackend` interface, `local` (free baseline), `sagemaker` (paid).
- `models/tables.py` : SQLAlchemy schema. `config.py` : env settings.

## Job flow
described -> data_checked -> baseline_done -> quoted -> awaiting_payment -> paid -> training -> done
(failed / refunded as end states). `paid` is set only after the server confirms the capture.

## Schema (money in integer cents)
- jobs(id, description, status, dataset_path, readiness_score, baseline_result, created_at)
- quotes(id, job_id, instance_type, estimated_cost_cents, spend_cap_cents, approved_at)
- payments(id, job_id, provider, provider_order_id UNIQUE, provider_capture_id UNIQUE, amount_cents, captured_confirmed)
- ledger_entries(id, job_id, kind capture|usage|refund, amount_cents signed, idempotency_key UNIQUE) : append-only
- webhook_events(event_id PK, event_type, payload, received_at) : insert-only, PK gives idempotency

## API (initial)
- GET /health
- POST /jobs, GET /jobs/{id}
- POST /payments/orders, POST /payments/capture (TODO)
- POST /webhooks/paypal (TODO)

## Open decisions
- SQLite for the hackathon; swap `DATABASE_URL` for Postgres later.
- Auth/users are out of scope for the demo.
