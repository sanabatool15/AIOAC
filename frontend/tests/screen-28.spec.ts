import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => {
  await signIn(page);
});

test("28: eligibility card shows reasons, options and footnote", async ({
  page,
}) => {
  await page.goto("/c/ineligible");
  const card = page.getByTestId("eligibility-card");
  await expect(
    card.getByRole("heading", { name: "Not eligible for a guaranteed price" }),
  ).toBeVisible();
  await expect(
    card.getByText("Dataset is 4.2 GB. Your Starter plan allows up to 500 MB."),
  ).toBeVisible();
  await expect(
    card.getByText("Estimated cost is above your $40 maximum."),
  ).toBeVisible();
  await expect(card.getByText("RECOMMENDED")).toBeVisible();
  await expect(
    page.getByText("You are never charged for this check."),
  ).toBeVisible();
  const sample = card.getByRole("radio", { name: /smart 500 MB sample/ });
  await expect(sample).toHaveAttribute("aria-checked", "true");
  await page.screenshot({ path: "tests/shots/screen-28.png" });
});

test("28: sidebar budget says nothing held", async ({ page }) => {
  await page.goto("/c/ineligible");
  await expect(page.getByText("Guarantee not available yet")).toBeVisible();
  await expect(page.getByText("Nothing held")).toBeVisible();
});

test("28: picking another option moves the selection", async ({ page }) => {
  await page.goto("/c/ineligible");
  const card = page.getByTestId("eligibility-card");
  await card.getByRole("radio", { name: /Lower the target/ }).click();
  await expect(
    card.getByRole("radio", { name: /Lower the target/ }),
  ).toHaveAttribute("aria-checked", "true");
  await expect(
    card.getByRole("radio", { name: /smart 500 MB sample/ }),
  ).toHaveAttribute("aria-checked", "false");
});

test("28: continue goes to the agreement", async ({ page }) => {
  await page.goto("/c/ineligible");
  await page.getByRole("button", { name: "Continue with sample" }).click();
  await expect(page).toHaveURL(/\/c\/agreement/);
});

test("28: run free baseline only goes to the baseline", async ({ page }) => {
  await page.goto("/c/ineligible");
  await page.getByRole("button", { name: "Run free baseline only" }).click();
  await expect(page).toHaveURL(/\/c\/baseline/);
});

test("28: error state retries", async ({ page }) => {
  await page.goto("/c/ineligible?mock=error");
  await expect(
    page.getByRole("button", { name: "Try again" }).first(),
  ).toBeVisible();
});
