import { expect, test } from "@playwright/test";
import { signUp } from "./helpers";

const SHOTS = "/tmp/claude-0/-home-user-AIOAC/7911dd15-399d-5960-9538-0dfae2b20d81/scratchpad/shots6";

test("approval card shows the dataset title and facts; assistant markdown renders as formatting", async ({ page }) => {
  await signUp(page);
  await page.getByRole("link", { name: "Start" }).click();
  await page.getByLabel("Message AIOAC").fill("I want to predict which customers will leave. I have no data.");
  await page.getByLabel("Send message").click();

  // Card: title is the dataset name, then a facts grid (no bare ids).
  const card = page.getByLabel("Approval needed");
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card.getByRole("heading", { name: "Telco customer churn" })).toBeVisible();
  const facts = card.locator("dl");
  for (const label of ["Source", "Rows", "Columns", "Answer column", "License"]) {
    await expect(facts.locator("dt", { hasText: label })).toBeVisible();
  }
  await expect(facts.locator("dd", { hasText: "left" })).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/card.png` });

  await card.getByRole("button", { name: "Approve", exact: true }).click();

  // The model's reply has **bold** and `code`: shown as formatting, with no markers.
  await expect(page.locator("strong", { hasText: "the churn dataset" })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("code", { hasText: /^left$/ })).toBeVisible();
  await expect(page.getByText("**the churn dataset**")).toHaveCount(0);
  await expect(page.getByText("`left`")).toHaveCount(0);
  await page.screenshot({ path: `${SHOTS}/markdown.png` });
});
