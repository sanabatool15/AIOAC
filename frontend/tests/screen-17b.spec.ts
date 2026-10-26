import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 17b "API key details: project access" (Figma 76:4053).
test("screen 17b drawer shows facts and per-project access", async ({
  page,
}) => {
  await page.goto("/settings/keys");
  await page.getByRole("link", { name: "Details for HF read token" }).click();
  const d = page.getByRole("complementary", { name: "HF read token details" });
  await expect(d).toBeVisible();
  await expect(d.getByText("Key is on")).toBeVisible();
  await expect(d.getByText("Hugging Face")).toBeVisible();
  await expect(d.getByText("••••••••••  8f2a")).toBeVisible();
  await expect(d.getByText("Oct 20, 2026")).toBeVisible();
  await expect(d.getByText("2 min ago by Churn prediction")).toBeVisible();
  await expect(
    d.getByRole("switch", { name: "Allow all projects" }),
  ).toBeChecked();
  const rows = d.getByLabel("Project access").getByRole("listitem");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText("Used 2 min ago");
  await expect(rows.nth(2)).toContainText("Never used");
  await page.screenshot({ path: "tests/shots/screen-17b.png" });
});

test("screen 17b access changes update the table; key can be turned off", async ({
  page,
}) => {
  await page.goto("/settings/keys?details=k1");
  const d = page.getByRole("complementary", { name: "HF read token details" });
  await d.getByRole("switch", { name: "Allow Lead scoring" }).click();
  await expect(
    d.getByRole("switch", { name: "Allow all projects" }),
  ).not.toBeChecked();
  await expect(page.getByRole("row", { name: /HF read token/ })).toContainText(
    "2 projects",
  );
  await d.getByRole("switch", { name: "Allow all projects" }).click();
  await expect(page.getByRole("row", { name: /HF read token/ })).toContainText(
    "All projects",
  );
  await d.getByRole("switch", { name: "HF read token is on" }).click();
  await expect(d.getByText("Key is off")).toBeVisible();
});

test("screen 17b delete from the drawer and close", async ({ page }) => {
  await page.goto("/settings/keys?details=k3");
  const d = page.getByRole("complementary", { name: "OpenRouter details" });
  await d.getByRole("button", { name: "Delete key" }).click();
  await page
    .getByRole("alertdialog")
    .getByRole("button", { name: "Delete key" })
    .click();
  await expect(d).toHaveCount(0);
  await expect(page).toHaveURL(/\/settings\/keys$/);
  await page.goto("/settings/keys?details=k2");
  await page
    .getByRole("complementary", { name: "Kaggle key details" })
    .getByRole("button", { name: "Close" })
    .click();
  await expect(
    page.getByRole("complementary", { name: "Kaggle key details" }),
  ).toHaveCount(0);
});

test("screen 17b shows an error state with retry", async ({ page }) => {
  await page.goto("/settings/keys?details=k1&mock=error");
  await expect(page.getByRole("alert").first()).toBeVisible();
});
