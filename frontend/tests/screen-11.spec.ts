import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 11 "Budget panel" (Figma 76:2458).
test("screen 11 budget panel opens from the sidebar and shows allocations", async ({
  page,
}) => {
  await page.goto("/c/budget");
  await expect(page.getByText("Experiment 1 is running.")).toBeVisible();
  await expect(page.getByText("Held $40 · Used $9.80")).toBeVisible();
  await page.getByRole("button", { name: "Open budget details" }).click();
  const panel = page.getByRole("dialog", { name: "Budget for this job" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText("LIVE")).toBeVisible();
  await expect(panel.getByText("$40.00")).toBeVisible();
  await expect(panel.getByText("$9.80", { exact: true })).toBeVisible();
  await expect(panel.getByText("$0.00")).toBeVisible();
  const rows = panel.getByLabel("Allocations").getByRole("listitem");
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(1)).toContainText("Up to $14 · used $9.80");
  await expect(rows.nth(1)).toContainText("RUNNING");
  await expect(rows.nth(2)).toContainText("LOCKED");
  await expect(rows.nth(3)).toContainText("RESERVED");
  await expect(
    panel.getByText("The backend sets every allocation."),
  ).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-11.png" });
  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);
});

test("screen 11 stop job asks for confirmation and voids the hold", async ({
  page,
}) => {
  await page.goto("/c/budget");
  await page.getByRole("button", { name: "Open budget details" }).click();
  await page.getByRole("button", { name: "Stop job" }).click();
  await expect(
    page.getByRole("alertdialog", { name: /Stop this job/ }),
  ).toBeVisible();
  await page
    .getByRole("alertdialog", { name: /Stop this job/ })
    .getByRole("button", { name: "Stop job" })
    .click();
  await expect(
    page.getByText("Job stopped. Your PayPal hold was voided."),
  ).toBeVisible();
});

test("screen 11 shows an empty state when nothing is held", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Open budget details" }).click();
  await expect(page.getByText("No budget yet")).toBeVisible();
});

test("screen 11 shows an error state with retry", async ({ page }) => {
  await page.goto("/c/budget");
  await expect(page.getByText("Held $40 · Used $9.80")).toBeVisible();
  await page.evaluate(() =>
    history.replaceState(null, "", "/c/budget?mock=error"),
  );
  await page.getByRole("button", { name: "Open budget details" }).click();
  const panel = page.getByRole("dialog", { name: "Budget for this job" });
  await expect(panel.getByRole("alert")).toBeVisible();
  await expect(panel.getByRole("button", { name: "Try again" })).toBeVisible();
});
