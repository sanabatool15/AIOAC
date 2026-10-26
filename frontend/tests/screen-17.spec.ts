import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 17 "Settings: API keys" (Figma 76:3812).
test("screen 17 lists keys with masked values and project scope", async ({
  page,
}) => {
  await page.goto("/settings/keys");
  await expect(
    page.getByRole("heading", { name: "Settings", level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "API keys", level: 2, exact: true }),
  ).toBeVisible();
  const rows = page.getByRole("row");
  await expect(rows).toHaveCount(4); // header + 3
  await expect(rows.nth(1)).toContainText("HF read token");
  await expect(rows.nth(1)).toContainText("••••••••••  8f2a");
  await expect(rows.nth(1)).toContainText("All projects");
  await expect(rows.nth(2)).toContainText("2 projects");
  await expect(rows.nth(3)).toContainText("Churn prediction");
  await expect(
    page
      .getByRole("region", { name: "Settings" })
      .getByRole("switch", { name: "OpenRouter enabled" }),
  ).not.toBeChecked();
  await expect(
    page
      .getByRole("region", { name: "Settings" })
      .getByRole("switch", { name: "Kaggle key enabled" }),
  ).toBeChecked();
  await page.screenshot({ path: "tests/shots/screen-17.png" });
});

test("screen 17 toggle, reveal and delete a key", async ({ page }) => {
  await page.goto("/settings/keys");
  const sw = page
    .getByRole("region", { name: "Settings" })
    .getByRole("switch", { name: "OpenRouter enabled" });
  await sw.click();
  await expect(sw).toBeChecked();
  await page.getByRole("button", { name: "Reveal HF read token" }).click();
  await expect(page.getByRole("row", { name: /HF read token/ })).toContainText(
    "mock_huggingface_key",
  );
  await page.getByRole("button", { name: "Hide HF read token" }).click();
  await expect(page.getByRole("row", { name: /HF read token/ })).toContainText(
    "••••••••••  8f2a",
  );
  await page.getByRole("button", { name: "Delete Kaggle key" }).click();
  const dlg = page.getByRole("alertdialog");
  await expect(dlg).toContainText('Delete key "Kaggle key"?');
  await expect(dlg).toContainText("2 projects use this key.");
  await dlg.getByRole("button", { name: "Delete key" }).click();
  await expect(page.getByText('Key "Kaggle key" deleted.')).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(3);
});

test("screen 17 add key validates and saves", async ({ page }) => {
  await page.goto("/settings/keys");
  const form = page.getByRole("form", { name: "Add a new key" });
  await form.getByLabel("Name").fill("my key");
  await form.getByLabel("Value").fill("abcdefgh1234");
  await form.getByRole("button", { name: "Save key" }).click();
  await expect(form.getByRole("alert")).toHaveText(
    "Names cannot contain spaces.",
  );
  await form.getByLabel("Name").fill("MY_KAGGLE_KEY");
  await form.getByLabel("Value").fill("short");
  await form.getByRole("button", { name: "Save key" }).click();
  await expect(form.getByRole("alert")).toContainText("too short");
  await form.getByLabel("Value").fill("abcdefgh1234");
  await form.getByRole("button", { name: "Save key" }).click();
  await expect(page.getByText('Key "MY_KAGGLE_KEY" saved.')).toBeVisible();
  await expect(page.getByRole("row", { name: /MY_KAGGLE_KEY/ })).toContainText(
    "••••••••••  1234",
  );
});

test("screen 17 shows an error state with retry", async ({ page }) => {
  await page.goto("/settings/keys?mock=error");
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Try again" }).first(),
  ).toBeVisible();
});

test("screen 17 shows an empty state", async ({ page }) => {
  await page.goto("/settings/keys");
  for (const n of ["HF read token", "Kaggle key", "OpenRouter"]) {
    await page.getByRole("button", { name: `Delete ${n}` }).click();
    await page
      .getByRole("alertdialog")
      .getByRole("button", { name: "Delete key" })
      .click();
    await expect(page.getByRole("alertdialog")).toHaveCount(0);
  }
  await expect(page.getByText("No keys yet")).toBeVisible();
});
