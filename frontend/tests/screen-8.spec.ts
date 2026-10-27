import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 8 "Agent working: Files and links tab" (Figma 76:1748). Tab content only; the shell follows screen 7.
test("files & links tab lists tools, files and data links", async ({ page }) => {
  await page.goto("/c/exp-1");
  await page.getByRole("tab", { name: "Files & links" }).click();
  const panel = page.getByRole("tabpanel");
  await expect(panel.getByLabel("Tool activity").getByRole("listitem")).toHaveText(["Tools", "Browser", "Research", "Training", "Payment"]);
  await expect(panel.getByText("FILES THE AGENT CAN USE")).toBeVisible();
  for (const name of ["churn_sample.csv", "train_split.csv", "test_locked.csv", "baseline_model.pkl"]) {
    await expect(panel.getByText(name, { exact: true })).toBeVisible();
  }
  await expect(panel.getByText("1,409 rows · answers hidden")).toBeVisible();
  await expect(panel.getByText("LOCKED", { exact: true })).toBeVisible();
  await expect(panel.getByText("DATA LINKS")).toBeVisible();
  const link = panel.getByRole("link", { name: "huggingface.co/datasets/telco-churn" });
  await expect(link).toHaveAttribute("href", "https://huggingface.co/datasets/telco-churn");
  await expect(link).toHaveAttribute("rel", /noopener/);
  await expect(panel.getByText("Read", { exact: true })).toHaveCount(2);
  await page.screenshot({ path: "tests/shots/screen-8.png" });
});

test("files tab shows an empty state without a job", async ({ page }) => {
  await page.goto("/c/exp-1?mock=empty");
  await page.getByRole("tab", { name: "Files & links" }).click();
  await expect(page.getByText("No files yet")).toBeVisible();
});
