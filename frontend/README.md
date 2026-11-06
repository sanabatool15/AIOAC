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
- `app/`: routes. `/login`, `/signup`, `/` (new project), `/c/{id}` (one screen chosen from the project status), `/projects`, `/pay/return`, `/pay/cancel` (PayPal sandbox returns; the backend's `PAYPAL_RETURN_URL` and `PAYPAL_CANCEL_URL` must point there).
- `lib/api.ts` (client), `lib/api-real.ts` (one function per endpoint), `lib/adapters.ts` (cents, percent, camelCase in one place), `lib/status.ts` (status to screen), `lib/chat.ts` (agent chat), `lib/session.ts` (signed-in state from `GET /auth/me`, memory only).
- `components/real/`: the screens that serve the demo path today (login aside). They are replaced step by step by the polished screens in `components/shell/` (plan: `specs/frontend-integration.md` section 9).
- `components/shell/`: polished shell. Some screens (`agreement-chat`, `budget-card`, `budget-panel`, `result-chat`, `round2-chat`, `sidebar`, `training-chat`, `verified-chat`) are not rewired yet and are excluded from `tsconfig.json` and `eslint.config.mjs`. Remove an entry from both when you port that screen.
- `unit/`: `npm run test:unit` (adapter, status, client, chat tests; fixtures copied from real backend JSON).

## Browser tests (Playwright)
TODO (plan step 10): real-mode specs against the real FastAPI app with the scripted model and the mock payment double. The old mock-based specs were deleted. `playwright.config.ts` and `npm test` still work (`npm test` passes with no specs). Install a browser with `npx playwright install chromium`.

Contract: `specs/api.md`. What is wired: `specs/frontend-integration.md`.
