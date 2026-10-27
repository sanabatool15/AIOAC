import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 4 "Baseline result (inline visuals in chat)" at 1440x900. Compare tests/shots/screen-4.png with Figma node 76:1216.
test("screen 4 renders thread, readiness card and baseline results", async ({ page }) => {
  await page.goto("/c/baseline");
  await expect(page.getByRole("heading", { name: /Churn prediction\s+\/\s+Chat/ })).toBeVisible();
  await expect(page.getByText("Step 2 of 6")).toBeVisible();
  await expect(page.getByText("Free baseline · $0")).toBeVisible();
  await expect(page.getByText("Nothing charged")).toBeVisible();
  await expect(page.getByText("Predict which customers may stop buying next month.")).toBeVisible();
  await expect(page.getByText("Read churn_sample.csv · 7,043 rows")).toBeVisible();
  await expect(page.getByTestId("readiness-card")).toContainText("Data readiness: good to train");
  await expect(page.getByTestId("readiness-card")).toContainText("Eligible for pay-on-success");
  const result = page.getByTestId("baseline-result");
  await expect(result).toContainText("Free baseline results");
  await expect(result.getByRole("img", { name: "Baseline 71%" })).toBeVisible();
  await expect(result.getByRole("img", { name: "Target 80%" })).toBeVisible();
  await expect(page.getByPlaceholder("Ask AIOAC anything, or describe what to predict...")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-4.png" });
});

test("screen 4 shows error with retry and empty state", async ({ page }) => {
  await page.goto("/c/baseline?mock=error");
  await expect(page.getByRole("button", { name: "Try again" }).first()).toBeVisible();
});

test("sample data from home lands on the baseline view", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Try sample data/ }).click();
  await expect(page).toHaveURL(/\/c\/chat-/);
  await expect(page.getByTestId("baseline-result")).toBeVisible();
});
