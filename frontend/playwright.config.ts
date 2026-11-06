import { defineConfig } from "@playwright/test";

// Real-mode browser tests. They need two servers, both started here:
//   1. the TEST launcher of the real FastAPI app (backend/tests/browser_server.py): scripted model, mock PayPal, local
//      training, throwaway SQLite. It never reads real keys and refuses to start on a Postgres DATABASE_URL.
//   2. the frontend, built against that launcher and started with `next start`.
// `npm run test:e2e` runs everything. To start the servers yourself (reused when already up), see frontend/README.md.
const API = "http://localhost:8765";
const APP = "http://localhost:3100";
const backendDir = "../backend";

export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results",
  timeout: 150_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: APP,
    viewport: { width: 1440, height: 900 },
    // Optional: point at a specific Chrome binary (CHROME_PATH). Default: Playwright's own browser.
    launchOptions: { executablePath: process.env.CHROME_PATH || undefined },
  },
  webServer: [
    {
      command: `python -m tests.browser_server --port 8765 --frontend ${APP}`,
      cwd: backendDir,
      url: `${API}/health`,
      reuseExistingServer: true,
      timeout: 60_000,
      // The launcher refuses a Postgres URL, so make sure a real one in your shell never reaches it.
      env: { DATABASE_URL: "" },
    },
    {
      command: "npm run build && npm run start -- -p 3100",
      url: `${APP}/login`,
      reuseExistingServer: true,
      timeout: 300_000,
      env: { NEXT_PUBLIC_API_BASE_URL: API },
    },
  ],
});
