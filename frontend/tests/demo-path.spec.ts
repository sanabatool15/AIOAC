import { expect, test } from "@playwright/test";
import { runDemoPath, signUp } from "./helpers";

test("demo path: goal, dataset card, data check, free test, target, price, pay, result and receipt", async ({ page }) => {
  await signUp(page);
  const id = await runDemoPath(page);

  // Honest wording on the result: an estimate note, a measured result, the money recap (local training costs 0).
  await expect(page.getByText("Target reached")).toBeVisible();
  await expect(page.getByText(/not a promise/i).first()).toBeVisible();
  await expect(page.getByText("WHAT HAPPENED TO THE MONEY")).toBeVisible();
  await expect(page.getByText("Total charged").first()).toBeVisible();

  // Reloading keeps the finished state (the screen comes from the stored status, not from page memory).
  await page.reload();
  await expect(page).toHaveURL(new RegExp(`/c/${id}$`));
  await expect(page.getByTestId("result-verified")).toBeVisible();

  // The sidebar lists the project with a plain status.
  await expect(page.getByRole("link", { name: /predict which customers will leave/i }).first()).toBeVisible();
});
