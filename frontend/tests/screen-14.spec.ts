import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 14 "Result: live prediction and receipt" (Figma 76:3340).
test("screen 14 shows prediction, quick replies and receipt", async ({ page }) => {
  await page.goto("/c/result");
  await expect(page.getByText("Step 8 of 8")).toBeVisible();
  await expect(page.getByText("Captured $18.60", { exact: true })).toBeVisible();
  await expect(page.getByText("Your model is ready.")).toBeVisible();
  const result = page.getByTestId("prediction-result");
  await expect(result).toContainText("82% likely to stop buying");
  await expect(result).toContainText("Main reasons: month-to-month contract, short time as a customer.");
  for (const n of ["Download model", "Share results", "Train another"]) {
    await expect(page.getByRole("button", { name: n }).first()).toBeVisible();
  }
  const receipt = page.getByTestId("receipt-card");
  await expect(receipt).toContainText("$40.00");
  await expect(receipt).toContainText("$18.60 (actual compute)");
  await expect(receipt).toContainText("P 80% / 82.4%, R 60% / 63.1%");
  await expect(receipt).toContainText("SANDBOX-XXXXXXXX");
  await expect(page.getByRole("button", { name: "Download receipt (PDF)" })).toBeVisible();
  await expect(page.getByText("About 1 in 5 flagged customers may not leave.")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Receipt" })).toHaveAttribute("aria-selected", "true");
  await page.screenshot({ path: "tests/shots/screen-14.png" });
});

test("screen 14 predict changes with inputs", async ({ page }) => {
  await page.goto("/c/result");
  await page.getByRole("combobox").selectOption("Two year");
  await page.getByRole("button", { name: "Predict", exact: true }).click();
  await expect(page.getByTestId("prediction-result")).toContainText(/\d+% likely to stop buying/);
  await expect(page.getByTestId("prediction-result")).not.toContainText("82%");
  await expect(page.getByTestId("prediction-result")).toContainText("short time as a customer");
});

test("screen 14 download model toast and error state", async ({ page }) => {
  await page.goto("/c/result");
  await page.getByRole("button", { name: "Download receipt (PDF)" }).click();
  await expect(page.getByText("Receipt PDF is mocked")).toBeVisible();
  await page.goto("/c/result?mock=error");
  await expect(page.getByRole("alert").first()).toBeVisible();
});
