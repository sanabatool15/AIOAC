import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 9 "Agent working: Live view tab" (Figma 76:1987).
test("screen 9 shows tool calls, browser window and research notes", async ({
  page,
}) => {
  await page.goto("/c/research");
  await expect(page.getByText("While Experiment 1 trains")).toBeVisible();
  await expect(page.getByText("Step 5 of 8")).toBeVisible();
  await expect(page.getByText("Held $40 · Used $0")).toBeVisible();
  const calls = page.getByLabel("Tool calls");
  await expect(calls.locator("[data-state=done]")).toContainText(
    "Open Hugging Face dataset card",
  );
  await expect(calls.locator("[data-state=run]")).toContainText("running");
  await expect(calls.locator("[data-state=pending]")).toContainText(
    "Compare with your target",
  );
  await expect(page.getByRole("tab", { name: "Live view" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  const tools = page.getByLabel("Tool activity");
  await expect(tools.locator("[data-state=running]")).toHaveText([
    "Browser",
    "Research",
  ]);
  await expect(tools.locator("[data-state=done]")).toHaveText("Training");
  const win = page.getByTestId("browser-window");
  await expect(win.getByLabel("Page address")).toHaveText(
    "huggingface.co/datasets/telco-churn",
  );
  await expect(
    win.getByText("Typical precision for this dataset: 0.78 to 0.84"),
  ).toBeVisible();
  await expect(page.getByText("RESEARCH NOTES")).toBeVisible();
  await expect(
    page.getByLabel("Research notes").getByRole("listitem"),
  ).toHaveCount(3);
  await page.screenshot({ path: "tests/shots/screen-9.png" });
});

test("screen 9 live view is reachable from the training screen", async ({
  page,
}) => {
  await page.goto("/c/training");
  await page.getByRole("tab", { name: "Live view" }).click();
  await expect(page.getByTestId("browser-window")).toBeVisible();
});

test("screen 9 shows an error state with retry", async ({ page }) => {
  await page.goto("/c/research?mock=error");
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Try again" }).first(),
  ).toBeVisible();
});
