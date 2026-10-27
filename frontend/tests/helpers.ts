import type { Page } from "@playwright/test";

// Mock session: same flag the login screen sets.
export async function signIn(page: Page) {
  await page.addInitScript(() => localStorage.setItem("aioac.session", "1"));
}
