import { expect, test } from "@playwright/test";
import { signUp } from "./helpers";

const GOAL = "I want to predict which customers will leave. I have no data.";

async function startProject(page: import("@playwright/test").Page) {
  await page.getByRole("link", { name: "Start" }).click();
  await page.getByLabel("Message AIOAC").fill(GOAL);
  await page.getByLabel("Send message").click();
  await expect(page).toHaveURL(/\/c\/[0-9a-f]+$/);
}

test("Not now on an approval card survives a reload", async ({ page }) => {
  await signUp(page);
  await startProject(page);
  const card = page.getByLabel("Approval needed");
  await expect(card.getByRole("button", { name: "Approve", exact: true })).toBeVisible({ timeout: 30_000 });
  await card.getByRole("button", { name: "Not now" }).click();

  const calm = async () => {
    await expect(page.getByText("You chose not to use this one")).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Not now" })).toHaveCount(0);
    await expect(page.getByText(/No problem\. Tell me what you would like instead/)).toBeVisible();
  };
  await calm();
  await page.reload();
  await expect(page.getByLabel("Approval needed")).toBeVisible({ timeout: 30_000 });
  await calm();
});

test("the thinking indicator shows during the automatic first reply", async ({ page }) => {
  await signUp(page);
  // Hold the first /chat call for a few seconds, like a slow real model.
  await page.route("**/projects/*/chat", async (route) => {
    await new Promise((r) => setTimeout(r, 6_000));
    await route.continue();
  });
  await startProject(page);
  const status = page.getByRole("status").filter({ hasText: /Reading your goal|working|datasets|Thinking/ });
  await expect(status).toBeVisible({ timeout: 3_000 });
  await expect(status).toContainText("Reading your goal");
  await expect(page.getByLabel("Approval needed")).toBeVisible({ timeout: 30_000 });
  await expect(status).toHaveCount(0);
});
