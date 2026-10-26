import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results",
  use: {
    baseURL: "http://localhost:3000",
    viewport: { width: 1440, height: 900 },
    // Optional: point at a specific Chrome binary (CHROME_PATH). Default: Playwright's own browser.
    launchOptions: { executablePath: process.env.CHROME_PATH || undefined },
  },
  webServer: { command: "npm run dev", url: "http://localhost:3000", reuseExistingServer: true, timeout: 120000 },
});
