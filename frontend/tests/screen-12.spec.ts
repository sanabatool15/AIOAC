import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 12 "Verified: target met, payment captured" (Figma 76:2693).
test("screen 12 shows verification, progress and payment capture", async ({ page }) => {
  await page.goto("/c/verified");
  await expect(page.getByText("Step 7 of 8")).toBeVisible();
  await expect(page.getByText("Capturing $18.60 of $40", { exact: true })).toBeVisible();
  const card = page.getByTestId("verification-card");
  await expect(card.getByText("INDEPENDENT VERIFICATION")).toBeVisible();
  await expect(card.getByText("Target met on locked test data")).toBeVisible();
  await expect(page.getByTestId("metric-precision")).toContainText("82.4%");
  await expect(page.getByTestId("metric-precision")).toContainText("target 80%");
  await expect(page.getByTestId("metric-recall")).toContainText("63.1%");
  await expect(page.getByTestId("metric-recall")).toContainText("minimum 60%");
  await expect(card.getByText("MET", { exact: true })).toHaveCount(2);
  await expect(card.getByText("Locked test set of 1,409 customers · tested once · no retries")).toBeVisible();
  await expect(page.getByText("7 of 8 steps")).toBeVisible();
  await expect(page.getByLabel("Overall progress").locator("[data-state=done]")).toHaveCount(3);
  await expect(page.getByLabel("Overall progress").locator("[data-state=run]")).toHaveText("Capture payment");
  const pay = page.getByTestId("payment-card");
  await expect(pay).toContainText("Capturing $18.60 of your $40.00 hold");
  await expect(pay).toContainText("Remaining $21.40 is released. Release time depends on PayPal.");
  await page.screenshot({ path: "tests/shots/screen-12.png" });
});

test("screen 12 shows an error state with retry", async ({ page }) => {
  await page.goto("/c/verified?mock=error");
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" }).first()).toBeVisible();
});
