import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));
const URL = "/billing/review?plan=pro&cycle=monthly";

test("24: review shows plan, payment method, terms and gated Pay button", async ({
  page,
}) => {
  await page.goto(URL);
  await expect(
    page.getByRole("heading", { name: "Review and confirm" }),
  ).toBeVisible();
  const steps = page.getByRole("list", { name: "Steps" });
  await expect(steps.locator("[data-state=done]")).toHaveCount(2);
  await expect(steps.locator("[aria-current=step]")).toContainText("Review");
  const plan = page.getByLabel("Plan", { exact: true });
  await expect(plan).toContainText("Pro, billed monthly");
  await expect(plan).toContainText("$29.00 / month");
  await expect(plan).toContainText("Nov 24, 2026");
  await expect(
    page.getByLabel("Payment method", { exact: true }),
  ).toContainText("Visa ending 4242");
  const pay = page.getByRole("button", { name: "Pay $29.00" });
  await expect(pay).toBeDisabled();
  await page.screenshot({ path: "tests/shots/screen-24.png" });
  await page.getByText("I agree to the Terms").click();
  await expect(pay).toBeEnabled();
});

test("24: Change links and Back go to the earlier steps", async ({ page }) => {
  await page.goto(URL);
  await page.getByRole("link", { name: "Change plan" }).click();
  await expect(page).toHaveURL(/\/billing\/plan/);
  await page.goto(URL);
  await page.getByRole("link", { name: "Change payment method" }).click();
  await expect(page).toHaveURL(/\/billing\/payment\?plan=pro&cycle=monthly/);
});

test("24: failed payment says nothing was charged and can retry", async ({
  page,
}) => {
  await page.goto(URL);
  await page.getByText("I agree to the Terms").click();
  await page.waitForLoadState("networkidle");
  await page.evaluate(() =>
    history.replaceState(
      null,
      "",
      "/billing/review?plan=pro&cycle=monthly&mock=error",
    ),
  );
  await page.getByRole("button", { name: "Pay $29.00" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "You were not charged." }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Try again/ })).toBeEnabled();
  await expect(page).toHaveURL(/\/billing\/review/);
});
