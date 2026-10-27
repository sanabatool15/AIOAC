import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

test("25: full wizard ends on Done with receipt and the plan upgrade shows in the app", async ({
  page,
}) => {
  await page.goto("/billing/plan");
  await page.getByRole("button", { name: "Choose Pro" }).click();
  await page
    .getByRole("textbox", { name: "Card number" })
    .fill("4242 4242 4242 4242");
  await page.getByLabel("Expiry").fill("08 / 28");
  await page.getByLabel("CVC").fill("123");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByText("I agree to the Terms").click();
  await page.getByRole("button", { name: "Pay $29.00" }).click();
  await expect(page).toHaveURL(/\/billing\/done/);
  await expect(
    page.getByRole("heading", { name: "You are on Pro" }),
  ).toBeVisible();
  const steps = page.getByRole("list", { name: "Steps" });
  await expect(steps.locator("[data-state=done]")).toHaveCount(3);
  const receipt = page.getByTestId("receipt");
  await expect(receipt).toContainText("INV-2026-0015");
  await expect(receipt).toContainText("Pro, monthly");
  await expect(receipt).toContainText("Visa ending 4242");
  await expect(receipt).toContainText("$29.00");
  await expect(
    page.getByText("A copy was sent to mwmfigma@gmail.com"),
  ).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-25.png" });
  await page.getByRole("link", { name: "Back to chat" }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/account/usage");
  await expect(page.getByTestId("current-plan")).toContainText("Pro");
});

test("25: opening Done without paying shows an empty state, not a fake receipt", async ({
  page,
}) => {
  await page.goto("/billing/done");
  await expect(page.getByText("No receipt to show")).toBeVisible();
  await expect(page.getByRole("heading", { name: /You are on/ })).toHaveCount(
    0,
  );
});

test("25: Download invoice is mocked with a toast", async ({ page }) => {
  await page.goto("/billing/plan");
  await page.getByRole("button", { name: "Choose Pro" }).click();
  await page
    .getByRole("radio", { name: /PayPal account/ })
    .check({ force: true });
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByText("I agree to the Terms").click();
  await page.getByRole("button", { name: "Pay $29.00" }).click();
  await expect(page.getByTestId("receipt")).toContainText("PayPal account");
  await page.getByRole("button", { name: "Download invoice" }).click();
  await expect(
    page.getByText("Invoice download is mocked in this build."),
  ).toBeVisible();
});
