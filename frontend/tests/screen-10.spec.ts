import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 10 "Training in progress" (Figma 76:2216).
test("screen 10 shows live chart, ETA, stages and next decision", async ({ page }) => {
  await page.goto("/c/training");
  await expect(page.getByText("Experiment 1 is training.")).toBeVisible();
  await expect(page.getByText("Step 5 of 8")).toBeVisible();
  await expect(page.getByText("Held $40 · Used $3.40")).toBeVisible();
  const chart = page.getByTestId("live-chart");
  await expect(chart.getByText("UPDATING")).toBeVisible();
  await expect(chart.getByRole("img")).toHaveAttribute("aria-label", /75%.*80% target/);
  await expect(chart.getByText("Dashed line: your 80% target")).toBeVisible();
  const eta = page.getByTestId("eta-card");
  await expect(eta.getByText("about 7 to 10 min")).toBeVisible();
  await expect(eta.getByText("LIVE")).toBeVisible();
  const stages = page.getByLabel("Stages");
  await expect(stages.locator("[data-state=done]")).toHaveCount(3);
  await expect(stages.locator("[data-state=run]")).toContainText("4:20 of about 9:00");
  await expect(stages.locator("[data-state=pending]")).toHaveCount(2);
  await expect(page.getByTestId("decision-card")).toContainText("Backend approves any spend.");
  await expect(page.getByLabel("Tool activity").locator("[data-state=done]")).toHaveText("Tools");
  await expect(page.getByLabel("Tool activity").locator("[data-state=running]")).toHaveText("Training");
  await page.screenshot({ path: "tests/shots/screen-10.png" });
});

test("screen 10 files tab and close", async ({ page }) => {
  await page.goto("/c/training");
  await page.getByRole("tab", { name: "Files & links" }).click();
  await expect(page.getByText("test_locked.csv")).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("complementary", { name: "Canvas" })).toHaveCount(0);
});

test("screen 10 shows an error state with retry", async ({ page }) => {
  await page.goto("/c/training?mock=error");
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" }).first()).toBeVisible();
});
