# AIOAC frontend

Next.js 16 (App Router) + TypeScript + Tailwind v4. The app always talks to the real FastAPI backend. There is no mock mode.

```
npm install
cp .env.example .env.local     # only NEXT_PUBLIC_API_BASE_URL matters (default http://localhost:8000)
npm run dev                    # http://localhost:3000 (opens on login)
npm run typecheck && npm run lint && npm run test:unit && npm run build
```

Backend (in `backend/`): `uvicorn app.main:app --reload` (CORS allows `http://localhost:3000`). Sign up on `/signup`; the server sets an httpOnly cookie and the browser keeps no token. Set `NEXT_PUBLIC_DEMO_LOGIN=true` to show a "Try the demo" button (the server must enable `POST /auth/demo`).

Read `AGENTS.md` first: this Next version has breaking changes (page `params` are Promises).

## Environment
- `NEXT_PUBLIC_API_BASE_URL`: backend address, no trailing path.
- `NEXT_PUBLIC_DEMO_LOGIN`: optional, `true` shows the demo login button.

## Layout
- `app/`: routes. `/login`, `/signup`, `/` (new project), `/c/{id}` (one screen chosen from the project status), `/projects`, `/pay/return`, `/pay/cancel`, `/projects/{id}` (tabs), `/account/usage`, `/account/billing`, `/welcome`, `/s/{token}` (public result link, no login) (PayPal sandbox returns; the backend's `PAYPAL_RETURN_URL` and `PAYPAL_CANCEL_URL` must point there).
- `lib/api.ts` (client), `lib/api-real.ts` (one function per endpoint), `lib/adapters.ts` (cents, percent, camelCase in one place), `lib/status.ts` (status to screen), `lib/chat.ts` (agent chat), `lib/session.ts` (signed-in state from `GET /auth/me`, memory only).
- `components/shell/`: all screens (sidebar, chat thread, step cards, quote, pay return, training, result and receipt, project detail with Model tab, usage, billing history, share dialog, public result page). `components/ui/`: small shared pieces.
- `lib/screens.ts`, `lib/result-view.ts`, `lib/pay-flow.ts`, `lib/chat-controller.ts`, `lib/welcome.ts`, `lib/nav.ts`: pure logic with no React, covered by `unit/`.
- `unit/`: `npm run test:unit` (adapter, status, client, chat tests; fixtures copied from real backend JSON).

## Browser tests (Playwright)
`npm run test:e2e` runs `tests/*.spec.ts` (6 files, 11 tests) in real mode. `playwright.config.ts` starts two servers and reuses them if they are already up:
1. the TEST launcher of the real FastAPI app: `cd ../backend && python -m tests.browser_server --port 8765 --frontend http://localhost:3100` (scripted model, mock PayPal, local training, throwaway SQLite; never reads real keys, refuses a Postgres `DATABASE_URL`);
2. the frontend built against it: `npm run build && npm run start -- -p 3100` with `NEXT_PUBLIC_API_BASE_URL=http://localhost:8765`.

To start them yourself, run those two commands in two terminals (set the variable first; PowerShell: `$env:NEXT_PUBLIC_API_BASE_URL="http://localhost:8765"`), then `npm run test:e2e`. Needs a browser: set `CHROME_PATH` to a Chrome, or `npx playwright install chromium`. `npm test` runs only the unit tests. Not covered: real PayPal, real model, real SageMaker.

Contract: `specs/api.md`. What is wired: `specs/frontend-integration.md`.
