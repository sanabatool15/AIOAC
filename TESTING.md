# Try AIOAC in your browser (for judges)

No keys, no accounts and no real money are needed. This runs a demo server with a scripted AI model and a mock PayPal, so everything you see is safe test data.

You need: Python 3.11+, Node.js 20+ and Git.

## 1. Get the code
```bash
git clone https://github.com/sanabatool15/aioac.git
cd aioac
```

## 2. Start the backend (terminal 1)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e .
python -m tests.browser_server --port 8765 --frontend http://localhost:3000
```
Leave this terminal running.

## 3. Start the website (terminal 2)
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8765" > .env.local     # Windows PowerShell: Set-Content .env.local "NEXT_PUBLIC_API_BASE_URL=http://localhost:8765"
npm run dev
```

## 4. Use it
Open http://localhost:3000 and:
1. Sign up with any email and a password of 8+ characters (it only exists in this throwaway test database).
2. Describe a goal, for example "which customers may stop buying", then choose "I have no data".
3. Approve the dataset card.
4. Follow the steps: data check, free test, target and forecast, price estimate.
5. Click "Approve and pay". The mock PayPal sends you back and the server confirms the hold.
6. Watch training, then the result and the receipt (held, compute charged, success fee only if verified, released).

## If something does not work
- Start the backend (step 2) before opening the website.
- Create `.env.local` before running `npm run dev`; if you did it later, stop and start `npm run dev` again.
- If port 8765 or 3000 is busy, close the program using it.
