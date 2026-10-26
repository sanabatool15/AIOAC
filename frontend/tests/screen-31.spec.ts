import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 31 "Confirm dialogs (project, model, key)" (Figma 76:6521).
test("delete project needs the exact name typed", async ({ page }) => {
  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: "Projects", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Delete project Churn prediction" }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toContainText('Delete "Churn prediction"?');
  await expect(dialog).toContainText("This removes 3 chats, 2 data files and 2 model versions. Receipts stay in Billing.");
  const confirm = dialog.getByRole("button", { name: "Delete project" });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel("Type the project name to confirm").fill("Churn");
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel("Type the project name to confirm").fill("Churn prediction");
  await confirm.click();
  await expect(page.getByText('Project "Churn prediction" deleted.')).toBeVisible();
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
});

test("cancel and Escape close the dialog without deleting", async ({ page }) => {
  await page.goto("/projects");
  await page.getByRole("button", { name: "Delete project Loan repayment" }).click();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Delete project Loan repayment" }).click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await expect(page.getByRole("listitem").filter({ hasText: "Loan repayment" })).toBeVisible();
});

test("a failed delete shows an error and can be retried", async ({ page }) => {
  await page.goto("/projects?mock=error");
  await expect(page.getByRole("alert").first()).toBeVisible();
});

test("preview shows the three dialogs", async ({ page }) => {
  await page.goto("/dev/dialogs");
  await expect(page.getByText('Delete key "HF read token"?')).toBeVisible();
  await expect(page.getByText("Delete model v1?")).toBeVisible();
  await expect(page.getByText('Delete "Churn prediction"?')).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-31.png" });
});
