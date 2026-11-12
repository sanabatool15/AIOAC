import { expect, test } from "@playwright/test";
import { API, runDemoPath, signUp } from "./helpers";

test("project detail tabs, Model tab (one record and CSV), Usage and Billing history", async ({ page }) => {
  await signUp(page);
  const id = await runDemoPath(page);

  await page.goto(`/projects/${id}`);
  for (const tab of ["Overview", "History", "Activity", "Model"]) {
    await expect(page.getByRole("tab", { name: tab })).toBeVisible();
  }
  await expect(page.getByText("Your progress").first()).toBeVisible();

  await page.getByRole("tab", { name: "History" }).click();
  await expect(page.getByText(/rows/i).first()).toBeVisible();

  // Activity: steps done with buttons are in the feed (they come from stored rows), in plain sentences.
  await page.getByRole("tab", { name: "Activity" }).click();
  const feed = page.getByLabel("What the agent did");
  await expect(feed.getByText(/Checked data readiness: grade/)).toBeVisible();
  await expect(feed.getByText(/Ran the free test: about \d+ out of 100 right/)).toBeVisible();
  await expect(feed.getByText(/Forecast ready/)).toBeVisible();
  await expect(feed.getByText("You approved the price estimate")).toBeVisible();
  await expect(feed.getByText(/Training finished/)).toBeVisible();
  await expect(feed).not.toContainText(/[{}]|storage|Traceback/);

  // Model tab: one record.
  await page.getByRole("tab", { name: "Model" }).click();
  await expect(page.getByLabel("Try it on one record")).toBeVisible();
  // Plain-English label as the main text, raw column name kept as small text; the field id stays on the raw name.
  const form = page.getByLabel("Try it on one record");
  await expect(form.getByText("Months as a customer", { exact: true })).toBeVisible();
  await expect(form.locator("#f-months_active")).toBeVisible();
  await expect(form.getByText("months_active", { exact: true })).toBeVisible();
  await expect(form.locator("label[for=f-plan]")).toHaveText("plan"); // no label known: the raw name only
  await page.getByLabel("months_active").fill("12");
  await page.getByLabel("Try it on one record").getByRole("button", { name: "Predict" }).click();
  await expect(page.getByTestId("prediction")).toBeVisible();
  await expect(page.getByTestId("prediction")).toContainText(/estimate|not a promise/i);

  // Model tab: a CSV built from the model's own input columns.
  const model = await (await page.request.get(`${API}/projects/${id}/model`)).json();
  const cols: { name: string; example: string | number | null }[] = model.columns;
  const csv = `${cols.map((c) => c.name).join(",")}\n${cols.map((c) => c.example ?? 1).join(",")}\n${cols.map((c) => c.example ?? 2).join(",")}\n`;
  await page.getByLabel("CSV text").fill(csv);
  await page.getByRole("button", { name: "Predict for every row" }).click();
  await expect(page.getByRole("button", { name: "Download results (CSV)" })).toBeVisible();

  // Usage and Billing history count this project.
  await page.goto("/account/usage");
  await expect(page.getByRole("heading", { name: "Usage", exact: true })).toBeVisible();
  await expect(page.getByLabel("Recent activity")).toBeVisible();
  await page.goto("/account/billing");
  await expect(page.getByRole("heading", { name: "Billing history", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /predict which customers will leave/i })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Total charged" })).toBeVisible();
});
