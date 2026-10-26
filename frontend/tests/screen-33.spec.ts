import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

async function openTab(page: import("@playwright/test").Page) {
  await page.goto("/account/billing");
  await page.getByRole("tab", { name: "Payment methods" }).click();
}

test("33: payment methods tab lists three methods and billing details", async ({
  page,
}) => {
  await openTab(page);
  await expect(
    page.getByRole("tab", { name: "Payment methods" }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("button", { name: "+ Add payment method" }),
  ).toBeVisible();
  await expect(page.getByRole("listitem")).toHaveCount(3);
  const visa = page.getByLabel("Visa ending 4242", { exact: true });
  await expect(visa).toContainText("DEFAULT");
  await expect(visa).toContainText("Expires 08/28 · David");
  await expect(
    page.getByLabel("Mastercard ending 0099", { exact: true }),
  ).toContainText("EXPIRES SOON");
  await expect(page.getByLabel("Email for invoices")).toHaveValue(
    "mwmfigma@gmail.com",
  );
  await page.screenshot({ path: "tests/shots/screen-33.png" });
});

test("33: make default moves the DEFAULT tag; removing the default is refused", async ({
  page,
}) => {
  await openTab(page);
  await page.getByRole("button", { name: "Make default PayPal" }).click();
  await expect(page.getByLabel("PayPal", { exact: true })).toContainText(
    "DEFAULT",
  );
  await expect(
    page.getByLabel("Visa ending 4242", { exact: true }),
  ).not.toContainText("DEFAULT");
  await page.getByRole("button", { name: "Remove PayPal" }).click();
  await page
    .getByRole("alertdialog")
    .getByRole("button", { name: "Remove" })
    .click();
  await expect(
    page.getByText("Choose another default method before removing this one."),
  ).toBeVisible();
});

test("33: remove a non-default method with confirmation", async ({ page }) => {
  await openTab(page);
  await page
    .getByRole("button", { name: "Remove Mastercard ending 0099" })
    .click();
  await expect(page.getByRole("alertdialog")).toContainText(
    "Remove Mastercard ending 0099?",
  );
  await page
    .getByRole("alertdialog")
    .getByRole("button", { name: "Remove" })
    .click();
  await expect(page.getByRole("listitem")).toHaveCount(2);
  await expect(page.getByText("Mastercard ending 0099 removed.")).toBeVisible();
});

test("33: save billing details validates the email", async ({ page }) => {
  await openTab(page);
  await page.getByLabel("Email for invoices").fill("not-an-email");
  await page.getByRole("button", { name: "Save details" }).click();
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Enter a valid email for invoices." }),
  ).toBeVisible();
  await page.getByLabel("Email for invoices").fill("billing@example.com");
  await page.getByRole("button", { name: "Save details" }).click();
  await expect(page.getByText("Billing details saved.")).toBeVisible();
});

test("33: empty state when there are no saved methods", async ({ page }) => {
  await page.goto("/account/billing?mock=empty");
  await page.getByRole("tab", { name: "Payment methods" }).click();
  await expect(page.getByText("No saved payment methods")).toBeVisible();
});
