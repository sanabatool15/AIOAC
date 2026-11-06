# AIOAC frontend

Next.js 16 (App Router) + TypeScript + Tailwind v4. All 35 numbered screens (16 route pages) run on a typed mock API (`lib/mock-api.ts`, `lib/types.ts`); function names mirror the future FastAPI endpoints.

```
npm install
npm run dev        # http://localhost:3000 (opens on login; mock session)
npm run typecheck && npm run lint && npm run test:unit
npx playwright install chromium && npx playwright test
```
Add `?mock=error|empty|slow` to any URL to see those states. Design tokens live in `app/globals.css`. Read `AGENTS.md` first: this Next version has breaking changes (page `params` are Promises).

## Wiring to the backend
Mock mode is the default and needs no backend. For the demo path against the real backend:
```
# terminal 1 (backend/): uvicorn app.main:app --reload      (CORS allows http://localhost:3000)
# terminal 2 (frontend/):
NEXT_PUBLIC_USE_MOCK_API=false NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```
Real mode: `/` creates a project, `/c/{id}` shows one screen chosen from the project status (`lib/status.ts`), PayPal returns to `/pay/return` or `/pay/cancel` (the backend's `PAYPAL_RETURN_URL` and `PAYPAL_CANCEL_URL` must point there; sandbox only). Real mode uses real login: `/login` and `/signup` call `POST /auth/login` and `/auth/signup`; the server sets an httpOnly cookie, the browser keeps no token. The signed-in state comes from `GET /auth/me` (memory only, `lib/session.ts`). A 401 from any call sends the browser to `/login?next=...`. Log out is in the sidebar and clears per-user browser memory. Set `NEXT_PUBLIC_DEMO_LOGIN=true` to show a 'Try the demo' button (needs the server to enable `POST /auth/demo`). Layout: `lib/api.ts` (client), `lib/api-real.ts` (endpoints), `lib/adapters.ts` (cents, percent, camelCase in one place), `lib/status.ts`, `components/real/` (screens). Describe step (`components/real/chat.tsx`, `lib/chat.ts`): the agent chat. It reads `GET /projects/{id}/messages` first and sends the goal to `POST /chat` once only when there is no history; every later `/chat` is one click or Enter (no polling, no auto-retry). Approving a card sends `approve: [card.tool]` and only a click does it. 'Upload my own CSV' stays below. `npm run test:unit` runs the adapter, status and client tests (fixtures copied from real backend JSON). Contract: `specs/api.md`; what is wired and what is not: `specs/frontend-integration.md` section 8.
