# Run AIOAC with real services (for judges)

This runs the real app: real AI model, PayPal **sandbox** (test money only), and local training. You need the keys listed in step 3. Never use a real PayPal account, real card or real money.

You need: Python 3.11+, Node.js 20+ and Git.

## 1. Get the code
```bash
git clone https://github.com/sanabatool15/aioac.git
cd aioac
```

## 2. Install the backend (terminal 1)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e .
```

## 3. Add the keys
Copy the template to `backend/.env` (Windows PowerShell: `Copy-Item ..\.env.example .env`):
```bash
cp ../.env.example .env
```
Open `backend/.env` and set these values (keys are supplied separately with the submission):

| Name | Value |
|---|---|
| `SECRET_KEY` | any random text of 32+ characters |
| `LLM_PROVIDER` | `azure` or `openrouter` |
| `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_MODEL` | if `LLM_PROVIDER=azure` |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | if `LLM_PROVIDER=openrouter` |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | PayPal SANDBOX app keys |
| `PAYPAL_WEBHOOK_ID` | PayPal sandbox webhook id (can stay as is for a quick test) |

Leave the rest as it is (`TRAINING_BACKEND=local`, `CORS_ORIGINS=http://localhost:3000`, the PayPal return URLs). Do not commit `.env`; it is git-ignored.

## 4. Start the backend
```bash
uvicorn app.main:app --port 8000
```
Leave it running.

## 5. Start the website (terminal 2)
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local     # Windows PowerShell: Set-Content .env.local "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000"
npm run dev
```

## 6. Use it
Open http://localhost:3000 and:
1. Sign up with any email and a password of 8+ characters.
2. Describe a goal, for example "which customers may stop buying", then choose "I have no data".
3. Approve the dataset card.
4. Follow the steps: data check, free test, target and forecast, price estimate.
5. Click "Approve and pay". PayPal opens: sign in with the **PayPal sandbox buyer** account (from sandbox.paypal.com > Accounts) and approve.
6. You return to the app, the server confirms the hold, training runs, then see the result and receipt (held, compute charged, success fee only if verified, released).

## If something does not work
- Start the backend before the website, and create `.env.local` before `npm run dev`.
- If login says "login is not set up", `SECRET_KEY` is missing or too short.
- If chat says the assistant is unavailable, the AI key in `.env` is missing or wrong.
- Delete any old `backend/aioac.db` and start again if the database errors.
