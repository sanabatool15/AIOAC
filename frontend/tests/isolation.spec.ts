import { expect, test } from "@playwright/test";
import { runDemoPath, signUp } from "./helpers";

test("another user cannot open my project in the UI (not found, nothing leaked)", async ({ page, browser }) => {
  await signUp(page);
  const id = await runDemoPath(page);

  const ctxB = await browser.newContext();
  const b = await ctxB.newPage();
  await signUp(b);

  await b.goto(`/c/${id}`);
  await expect(b.getByText(/project not found/i)).toBeVisible();
  await expect(b.locator("body")).not.toContainText("Telco customer churn");

  await b.goto(`/projects/${id}`);
  await expect(b.getByText(/project not found/i)).toBeVisible();
  await expect(b.locator("body")).not.toContainText("predict which customers will leave");

  // B's own list is empty; A still sees the project.
  await b.goto("/projects");
  await expect(b.getByText(/predict which customers will leave/i)).toHaveCount(0);
  await page.goto("/projects");
  await expect(page.getByText(/predict which customers will leave/i).first()).toBeVisible();
  await ctxB.close();
});
