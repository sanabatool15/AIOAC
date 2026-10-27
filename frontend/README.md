# AIOAC frontend

Next.js 16 (App Router) + TypeScript + Tailwind v4. All 37 designed screens run on a typed mock API (`lib/mock-api.ts`, `lib/types.ts`); function names mirror the future FastAPI endpoints.

```
npm install
npm run dev        # http://localhost:3000 (opens on login; mock session)
npx tsc --noEmit && npx eslint .
npx playwright install chromium && npx playwright test
```
Add `?mock=error|empty|slow` to any URL to see those states. Design tokens live in `app/globals.css`. Read `AGENTS.md` first: this Next version has breaking changes (page `params` are Promises).
