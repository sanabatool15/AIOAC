import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

test("26: billing shows five rows, filters, and the Loan repayment receipt detail", async ({
  page,
}) => {
  await page.goto("/account/billing");
  await expect(
    page.getByRole("heading", { name: "Billing and invoices", level: 1 }),
  ).toBeVisible();
  const table = page.getByRole("table", { name: "Invoices and receipts" });
  await expect(table.getByRole("row")).toHaveCount(6);
  const detail = page.getByTestId("receipt-detail");
  await expect(detail).toContainText("Loan repayment");
  await expect(detail).toContainText("REC-2026-0031");
  await expect(detail).toContainText("$27.40");
  await expect(detail).toContainText("$12.60");
  await page.screenshot({ path: "tests/shots/screen-26.png" });
  await page.getByRole("button", { name: "Job receipts" }).click();
  await expect(table.getByRole("row")).toHaveCount(4);
  await page.getByRole("button", { name: "Voided", exact: true }).click();
  await expect(table.getByRole("row")).toHaveCount(3);
  await page.getByRole("button", { name: "Plan invoices" }).click();
  await expect(table.getByRole("row")).toHaveCount(3);
});

test("26: picking a row swaps the detail card; PDF is mocked", async ({
  page,
}) => {
  await page.goto("/account/billing");
  await page
    .getByRole("button", { name: "Show receipt for Pro, monthly" })
    .click();
  const detail = page.getByTestId("receipt-detail");
  await expect(detail).toContainText("INV-2026-0014");
  await expect(detail).toContainText("Visa ending 4242");
  await detail.getByRole("button", { name: "Download PDF" }).click();
  await expect(
    page.getByText("PDF download is mocked in this build."),
  ).toBeVisible();
});

test("26: Download all (CSV) downloads a real file", async ({ page }) => {
  await page.goto("/account/billing");
  const [dl] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download all (CSV)" }).click(),
  ]);
  expect(dl.suggestedFilename()).toBe("aioac-billing.csv");
  await expect(page.getByText("Exported 5 rows.")).toBeVisible();
});

test("26: error retries and empty state; usage Manage link lands here", async ({
  page,
}) => {
  await page.goto("/account/billing?mock=error");
  await expect(
    page
      .getByRole("region", { name: "Billing and invoices" })
      .getByText("We could not reach the server."),
  ).toBeVisible();
  await page.goto("/account/billing?mock=empty");
  await expect(page.getByText("No invoices yet")).toBeVisible();
  await page.goto("/account/usage");
  await page.getByRole("link", { name: "Manage" }).click();
  await expect(page).toHaveURL(/\/account\/billing/);
});
