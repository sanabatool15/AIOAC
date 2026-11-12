import { expect, test } from "@playwright/test";
import { signUp } from "./helpers";

test("the three-way picker comes first; nothing is searched until 'No data' is chosen", async ({ page }) => {
  await signUp(page);
  await page.getByRole("link", { name: "Start" }).click();
  await page.getByLabel("Message AIOAC").fill("I want to predict which customers will leave.");
  await page.getByLabel("Send message").click();
  await expect(page).toHaveURL(/\/c\/[0-9a-f]+$/);

  const noData = page.getByRole("button", { name: /I have no data/ });
  await expect(noData).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: /Upload a file/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Paste a link/ })).toBeVisible();

  // The assistant answers the goal by pointing at the choices: no card, no search spinner.
  await expect(page.getByText(/pick one of the three choices/i)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByLabel("Approval needed")).toHaveCount(0);
  await expect(page.getByText(/Looking for open datasets/)).toHaveCount(0);

  // Upload opens its own panel and needs no assistant.
  await page.getByRole("button", { name: /Upload a file/ }).click();
  await expect(page.getByRole("region", { name: "Upload your own data" }).getByLabel("CSV file")).toBeAttached();
  await page.keyboard.press("Escape"); // the panel is a modal: close it before using the page behind it

  // Only now does the search start, and it ends in the approval card.
  await noData.click();
  await expect(page.getByText("I have no data. Please find a dataset.")).toBeVisible();
  await expect(page.getByLabel("Approval needed")).toBeVisible({ timeout: 30_000 });
});

test("pasting a dataset link: a bad address is refused in plain words, a good one is fetched and used", async ({ page }) => {
  await signUp(page);
  await page.getByRole("link", { name: "Start" }).click();
  await page.getByLabel("Message AIOAC").fill("I want to predict which customers will leave.");
  await page.getByLabel("Send message").click();
  await expect(page).toHaveURL(/\/c\/[0-9a-f]+$/);
  await page.getByRole("button", { name: /Paste a link/ }).click();

  await page.getByLabel("Dataset link").fill("https://example.com/data.csv");
  await page.getByRole("button", { name: "Get this dataset" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Hugging Face" })).toBeVisible();
  await expect(page.getByLabel("Approval needed")).toHaveCount(0); // no search started

  await page.getByLabel("Dataset link").fill("https://huggingface.co/datasets/eval/churn-table");
  await page.getByRole("button", { name: "Get this dataset" }).click();
  await expect(page.getByText(/1,500 rows · 5 columns/)).toBeVisible({ timeout: 30_000 });
  await page.getByLabel("Which column should we predict?").selectOption("left");
  await page.getByRole("button", { name: "Use this data" }).click();
  await expect(page.getByRole("button", { name: "Check my data" })).toBeVisible({ timeout: 30_000 });
});
