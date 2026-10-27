import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 13 "Target missed: hold voided, model kept" (Figma 76:3086).
test("screen 13 shows the miss, voided hold, recap and best model", async ({ page }) => {
  await page.goto("/c/missed");
  await expect(page.getByText("Hold voided · You pay $0")).toBeVisible();
  const card = page.getByTestId("verification-card");
  await expect(card.getByText("Target not reached")).toBeVisible();
  await expect(page.getByTestId("metric-precision")).toContainText("77.9%");
  await expect(page.getByTestId("metric-precision").getByText("NOT MET")).toBeVisible();
  await expect(page.getByTestId("metric-recall").getByText("MET", { exact: true })).toBeVisible();
  await expect(page.getByText("You pay $0. The PayPal hold was voided.")).toBeVisible();
  const model = page.getByTestId("best-model");
  await expect(model).toContainText("Best model so far: v1");
  await expect(model).toContainText("SAVED IN PROJECT");
  await expect(model).toContainText("Download unlocks once a target is met.");
  const recap = page.getByTestId("money-recap");
  await expect(recap).toContainText("$40.00");
  await expect(recap).toContainText("$0.00");
  await expect(recap).toContainText("Release timing depends on PayPal and your payment method.");
  await expect(page.getByLabel("Steps").locator("[data-state=done]")).toHaveCount(4);
  await page.screenshot({ path: "tests/shots/screen-13.png" });
});

test("screen 13 actions: delete model and go to a lower target", async ({ page }) => {
  await page.goto("/c/missed");
  await page.getByRole("button", { name: "Delete model" }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toContainText("Delete model v1?");
  await expect(dialog.getByRole("button", { name: "Delete model" })).toBeDisabled();
  await dialog.getByText("I understand I cannot get it back").click();
  await dialog.getByRole("button", { name: "Delete model" }).click();
  await expect(page.getByTestId("best-model")).toHaveCount(0);
  await expect(page.getByText("Model deleted from your project.")).toBeVisible();
  await page.goto("/c/missed");
  await page.getByRole("button", { name: "Try a lower target" }).click();
  await expect(page).toHaveURL(/\/c\/agreement/);
});
