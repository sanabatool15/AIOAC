import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => {
  await signIn(page);
});

test("29: round 2 plan and agreement render", async ({ page }) => {
  await page.goto("/c/round2");
  const changes = page.getByTestId("round2-changes");
  await expect(changes.getByText("Fix class imbalance with weighted training")).toBeVisible();
  await expect(changes.getByText("77.9% / 61.2%")).toBeVisible();
  await expect(changes.getByText("80% / 60%")).toBeVisible();
  const ag = page.getByTestId("round2-agreement");
  await expect(ag.getByText("$25.00 max")).toBeVisible();
  await expect(ag.getByText("Hold voided, you pay $0")).toBeVisible();
  await expect(page.getByText("Round 2", { exact: true })).toBeVisible();
  await expect(page.getByText("New hold not placed yet")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-29.png" });
});

test("29: approve opens the PayPal hold step", async ({ page }) => {
  await page.goto("/c/round2");
  await page.getByRole("button", { name: "Approve and authorize with PayPal" }).click();
  await expect(page).toHaveURL(/\/c\/round2\/pay\?a=/);
});

test("29: change target goes to the agreement", async ({ page }) => {
  await page.goto("/c/round2");
  await page.getByRole("button", { name: "Change target" }).click();
  await expect(page).toHaveURL(/\/c\/agreement/);
});

test("29: hold failure shows an error and stays", async ({ page }) => {
  await page.goto("/c/round2");
  await page.evaluate(() => window.history.replaceState(null, "", "/c/round2?mock=error"));
  await page.getByRole("button", { name: "Approve and authorize with PayPal" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve and authorize with PayPal" })).toBeEnabled();
});
