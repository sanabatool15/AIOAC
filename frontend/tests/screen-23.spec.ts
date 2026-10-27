import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));
const URL = "/billing/payment?plan=pro&cycle=monthly";

test("23: payment step shows method options, card form and order summary", async ({
  page,
}) => {
  await page.goto(URL);
  await expect(
    page.getByRole("heading", { name: "Add a payment method" }),
  ).toBeVisible();
  const steps = page.getByRole("list", { name: "Steps" });
  await expect(steps.locator("[data-state=done]")).toHaveCount(1);
  await expect(steps.locator("[aria-current=step]")).toContainText("Payment");
  await expect(
    page.getByRole("radio", { name: /Debit or credit card/ }),
  ).toBeChecked();
  await expect(
    page.getByRole("radio", { name: /PayPal account/ }),
  ).not.toBeChecked();
  const form = page.getByRole("form", { name: "Card details" });
  await expect(form.getByLabel("Name on card")).toHaveValue("David");
  const sum = page.getByTestId("order-summary");
  await expect(sum).toContainText("Pro plan (monthly)");
  await expect(sum).toContainText("Due today");
  await expect(sum).toContainText("$29.00");
  await page.screenshot({ path: "tests/shots/screen-23.png" });
});

test("23: empty or invalid card shows errors and does not continue", async ({
  page,
}) => {
  await page.goto(URL);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Enter a valid card number.")).toBeVisible();
  await expect(page.getByText("Use MM / YY.")).toBeVisible();
  await expect(page.getByText("Enter the 3 or 4 digit code.")).toBeVisible();
  await expect(page).toHaveURL(/\/billing\/payment/);
  await page.getByRole("textbox", { name: "Card number" }).fill("4242 4242 4242 4241");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Enter a valid card number.")).toBeVisible();
});

test("23: a valid test card continues to review with only brand and last 4", async ({
  page,
}) => {
  await page.goto(URL);
  await page.getByRole("textbox", { name: "Card number" }).fill("4242 4242 4242 4242");
  await page.getByLabel("Expiry").fill("08 / 28");
  await page.getByLabel("CVC").fill("123");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/billing\/review\?plan=pro&cycle=monthly/);
  const stored = await page.evaluate(
    () => sessionStorage.getItem("aioac.billing") ?? "",
  );
  expect(stored).toContain("4242");
  expect(stored).not.toContain("4242424242424242");
});

test("23: PayPal skips the card form; Back returns to plans", async ({
  page,
}) => {
  await page.goto(URL);
  await page
    .getByRole("radio", { name: /PayPal account/ })
    .check({ force: true });
  await expect(page.getByRole("form", { name: "Card details" })).toHaveCount(0);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(/\/billing\/review/);
  await page.goto(URL);
  await page.getByRole("button", { name: "Back" }).click();
  await expect(page).toHaveURL(/\/billing\/plan/);
});
