import { expect, test } from "@playwright/test";
import { APP, signUp } from "./helpers";

// While the assistant works, the chat shows its steps (GET /activity every 2 s). The server's /chat answer is held back
// here so the lines can be seen, and /activity is answered with fixed sentences (the real feed is tested in the backend).
test("live steps appear while the assistant works and clear when the turn ends", async ({ page }) => {
  await signUp(page);
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  const chatPosts: string[] = [];
  let polls = 0;
  await page.route("**/projects/*/chat", async (route) => {
    if (route.request().method() === "POST") chatPosts.push(route.request().url());
    await gate;
    await route.continue();
  });
  await page.route("**/projects/*/activity", async (route) => {
    polls++;
    const when = new Date(Date.now() + 5000).toISOString();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": APP, "access-control-allow-credentials": "true" },
      body: JSON.stringify([
        { when, kind: "you", text: 'You said: "x"' },
        { when, kind: "search", text: "Searched open datasets for customer churn" },
        { when, kind: "search", text: 'Found 2 possible datasets: "Telco customer churn", "Bank churn"' },
        { when, kind: "working", text: "Looking at a dataset…" },
      ]),
    });
  });

  await page.getByRole("link", { name: "Start" }).click();
  await page.getByLabel("Message AIOAC").fill("I want to predict which customers will leave. I have no data.");
  await page.getByLabel("Send message").click();
  await expect(page).toHaveURL(/\/c\/[0-9a-f]+$/);

  const live = page.getByLabel("What the assistant is doing");
  await expect(live.getByText("Searched open datasets for customer churn")).toBeVisible({ timeout: 15_000 });
  await expect(live.getByText(/Found 2 possible datasets/)).toBeVisible();
  await expect(live.getByText("Looking at a dataset…")).toBeVisible();
  await expect(live.getByText(/You said/)).toHaveCount(0); // the user's own message is already in the thread

  release();
  await expect(page.getByLabel("Approval needed")).toBeVisible({ timeout: 30_000 });
  await expect(live).toHaveCount(0); // cleared when the turn ended
  expect(chatPosts.length).toBe(1); // polling sends no extra /chat
  const after = polls;
  await page.waitForTimeout(4500);
  expect(polls).toBe(after); // and stops polling
});
