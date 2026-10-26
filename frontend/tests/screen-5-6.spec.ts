import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 5 "Performance agreement" (Figma 76:2) and screen 6 "PayPal authorization" (Figma 76:1558), 1440x900.
test("5: agreement card shows presets, terms and a disabled approve button", async ({ page }) => {
  await page.goto("/c/agreement");
  await expect(page.getByText("Step 3 of 6")).toBeVisible();
  await expect(page.getByText("Max $40 · not held yet")).toBeVisible();
  await expect(page.getByText("Nothing authorized")).toBeVisible();
  const card = page.getByTestId("agreement-card");
  await expect(card.getByText("You pay $0 unless the target is verified.")).toBeVisible();
  await expect(card.getByRole("radio", { name: /RECOMMENDED/ })).toHaveAttribute("aria-checked", "true");
  await expect(card).toContainText("Flag customers who may stop buying, with precision at least 80% and recall at least 60%.");
  await expect(card).toContainText("never above $40.");
  await expect(card.getByRole("button", { name: "Approve and authorize with PayPal" })).toBeDisabled();
  await page.screenshot({ path: "tests/shots/screen-5.png" });
});

test("5: choosing a preset updates the terms; custom target warns when unrealistic", async ({ page }) => {
  await page.goto("/c/agreement");
  const card = page.getByTestId("agreement-card");
  await card.getByRole("radio", { name: /SAFE/ }).click();
  await expect(card).toContainText("precision at least 76% and recall at least 55%");
  await expect(card).toContainText("never above $25.");
  await card.getByRole("button", { name: "Change target" }).click();
  await card.getByLabel("Precision %").fill("95");
  await expect(card.getByRole("status")).toContainText("unlikely for your data");
  await card.getByLabel("Precision %").fill("120");
  await expect(card.getByRole("alert")).toContainText("must be 1 to 99");
  await expect(card.getByRole("button", { name: "Approve and authorize with PayPal" })).toBeDisabled();
});

test("5 to 6 to 7: approve opens PayPal, authorize starts the job, cancel returns", async ({ page }) => {
  await page.goto("/c/agreement");
  const card = page.getByTestId("agreement-card");
  await card.getByText("I understand and agree to these terms.").click();
  await card.getByRole("button", { name: "Approve and authorize with PayPal" }).click();

  await expect(page).toHaveURL(/\/c\/agreement\/pay\?a=agr-/);
  const paypal = page.getByRole("dialog", { name: /PayPal/ });
  await expect(paypal.getByText("SANDBOX")).toBeVisible();
  await expect(paypal.getByText("AIOAC wants to hold up to $40.00")).toBeVisible();
  await expect(paypal.getByText("Charged today")).toBeVisible();
  await expect(paypal.getByText("$0.00")).toBeVisible();
  await expect(paypal.getByText("Test mode. No real money is used.")).toBeVisible();
  await expect(page.getByText("Authorizing up to $40")).toBeVisible();
  await expect(page.getByText("Step 4 of 6")).toBeVisible();
  await expect(page.getByTestId("agreement-summary")).toContainText("Target: precision 80%, recall 60%");
  await page.screenshot({ path: "tests/shots/screen-6.png" });

  await paypal.getByRole("button", { name: "Cancel and return" }).click();
  await expect(page).toHaveURL(/\/c\/agreement$/);
  await expect(page.getByTestId("agreement-card")).toBeVisible();

  await page.getByText("I understand and agree to these terms.").click();
  await page.getByRole("button", { name: "Approve and authorize with PayPal" }).click();
  await page.getByRole("button", { name: "Authorize with PayPal", exact: true }).click();
  await expect(page).toHaveURL(/\/c\/exp-1$/);
  await expect(page.getByText("Where your $40 hold goes")).toBeVisible();
});

test("6: opening the PayPal page without an agreement goes back to the agreement", async ({ page }) => {
  await page.goto("/c/agreement/pay");
  await expect(page).toHaveURL(/\/c\/agreement$/);
});

test("5: error state offers retry", async ({ page }) => {
  await page.goto("/c/agreement?mock=error");
  await expect(page.getByRole("button", { name: "Try again" }).first()).toBeVisible();
});
