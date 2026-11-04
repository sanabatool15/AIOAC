# AIOAC frontend

Next.js 16 (App Router) + TypeScript + Tailwind v4. All 35 numbered screens (16 route pages) run on a typed mock API (`lib/mock-api.ts`, `lib/types.ts`); function names mirror the future FastAPI endpoints.

```
npm install
npm run dev        # http://localhost:3000 (opens on login; mock session)
npx tsc --noEmit && npx eslint .
npx playwright install chromium && npx playwright test
```
Add `?mock=error|empty|slow` to any URL to see those states. Design tokens live in `app/globals.css`. Read `AGENTS.md` first: this Next version has breaking changes (page `params` are Promises).

## Wiring to the backend
The screens still read the mock API. To connect them: `specs/api.md` is the HTTP contract (section A built, section B planned, plus the status-to-screen table and unit conversions), and `specs/frontend-integration.md` is the step-by-step plan and the list of mismatches. Set `NEXT_PUBLIC_USE_MOCK_API=false` and `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`). The backend needs CORS first (`specs/breakpoints.md`, U1).
