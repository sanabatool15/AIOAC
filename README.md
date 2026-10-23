# AIOAC (AI on a Click)

Describe a prediction problem in plain words. An AI agent checks the data, runs a free baseline test, quotes an estimated cost, takes payment through PayPal (sandbox), trains the model, and refunds any unused amount.

Status: backend and agent core built and tested; AWS training, PayPal sandbox and the web app are not. See `specs/status.md`. The web app is not built yet.

## Run the backend

```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp ../.env.example .env      # fake placeholders; defaults use the mock payment provider
uvicorn app.main:app --reload
pytest                       # no network needed
```

By default payments use a mock provider and training runs locally, so nothing here spends money. PayPal sandbox and AWS SageMaker are not wired up yet.

License: MIT
