# Testing AIOAC (for judges)

No keys, no accounts, no money needed. Everything below runs offline with a scripted AI model and a mock PayPal.
(The real PayPal sandbox and AWS paths are described in README.md.)

Needs: Python 3.11+, Node.js 20+, Git.

## 1. Get the code
```bash
git clone https://github.com/sanabatool15/aioac.git
cd aioac
```

## 2. Quick check (about 2 minutes): backend tests
```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .\.venv\Scripts\Activate.ps1
pip install -e '.[dev]'
pytest
```
All tests should pass. Tests that need live services are skipped.

The main demo check (describe, hold, train, verify, capture, void) on its own:
```bash
pytest tests/e2e/test_payments_and_demo.py
```

## 3. Click through the real UI (about 5 minutes)
Terminal 1 (test server: real app, scripted model, mock PayPal, throwaway database):
```bash
cd backend
python -m tests.browser_server --port 8765 --frontend http://localhost:3000
```
Terminal 2:
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8765" > .env.local
npm run dev
```
Open http://localhost:3000 and:
1. Sign up with any email and a password (8+ characters).
2. Describe a goal, for example "which customers may stop buying". Choose "I have no data".
3. Approve the dataset card.
4. Follow the steps: data check, free test, target and forecast, price estimate.
5. Click "Approve and pay". The mock PayPal returns you to the app and the server confirms the hold.
6. Watch training, then the result and the receipt: held, compute charged, success fee (only if verified), released.

All money here is a mock. Nothing real is used anywhere.

## 4. Automatic browser tests (optional)
```bash
cd frontend
npm run test:e2e
```

## If something fails
- Start the backend before the frontend.
- Delete any old local `aioac.db`.
- Use a new PowerShell/terminal window if the virtual environment is not active.
