import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => {
  await signIn(page);
});

test("30: model tab opens first with the three ways to use it", async ({ page }) => {
  await page.goto("/c/use-model");
  await expect(page.getByTestId("ways-card").getByText("Call the API from your own app")).toBeVisible();
  await expect(page.getByText("Step 8 of 8")).toBeVisible();
  const canvas = page.getByRole("complementary", { name: "Canvas" });
  await expect(canvas.getByRole("tab", { name: "Model" })).toHaveAttribute("aria-selected", "true");
  await expect(canvas.getByRole("region", { name: "Download" }).getByText("Precision 82.4% · recall 63.1% · 4.1 MB")).toBeVisible();
  await expect(canvas.getByText("API KEY ON")).toBeVisible();
  await expect(canvas.getByText("0 calls this month · 1,000 free calls on Starter")).toBeVisible();
  await expect(page.getByText("Captured $18.60")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-30.png" });
});

test("30: downloads and copy give feedback", async ({ page }) => {
  await page.goto("/c/use-model");
  await page.getByRole("button", { name: "Download (.pkl)" }).click();
  await expect(page.getByText(/\.pkl\) is mocked/)).toBeVisible();
  await page.getByRole("button", { name: "Copy snippet" }).click();
  await expect(page.getByText(/Snippet copied|Could not copy/)).toBeVisible();
});

test("30: manage key goes to API keys", async ({ page }) => {
  await page.goto("/c/use-model");
  await page.getByRole("link", { name: "Manage key" }).click();
  await expect(page).toHaveURL(/\/settings\/keys/);
});

test("30: a CSV is predicted and a non-CSV is rejected", async ({ page }) => {
  await page.goto("/c/use-model");
  const input = page.getByLabel("Choose a CSV file");
  await input.setInputFiles({ name: "customers.txt", mimeType: "text/plain", buffer: Buffer.from("a") });
  await expect(page.getByRole("complementary", { name: "Canvas" }).getByRole("alert")).toContainText("Only .csv files");
  await input.setInputFiles({ name: "customers.csv", mimeType: "text/csv", buffer: Buffer.from("a,b\n1,2") });
  await expect(page.getByTestId("batch-done")).toContainText("customers_predictions.csv · 1,204 rows, 231 flagged");
});

test("30: batch failure shows an error", async ({ page }) => {
  await page.goto("/c/use-model");
  await expect(page.getByRole("button", { name: "Copy snippet" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => window.history.replaceState(null, "", "/c/use-model?mock=error"));
  await page.getByLabel("Choose a CSV file").setInputFiles({ name: "c.csv", mimeType: "text/csv", buffer: Buffer.from("a") });
  await expect(page.getByRole("complementary", { name: "Canvas" }).getByRole("alert")).toContainText("did not finish");
});

test("14: the Model tab on the result screen now shows the model", async ({ page }) => {
  await page.goto("/c/result");
  const canvas = page.getByRole("complementary", { name: "Canvas" });
  await canvas.getByRole("tab", { name: "Model" }).click();
  await expect(canvas.getByRole("button", { name: "Download (ONNX)" })).toBeVisible();
});
