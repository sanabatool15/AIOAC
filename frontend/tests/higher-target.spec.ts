import { expect, test } from "@playwright/test";
import { runDemoPath, signUp } from "./helpers";

// After a verified run the result screen offers "Try a higher target". It starts a free small test; the old receipt stays.
test("Try a higher target after a verified run opens a new round at the free test", async ({ page }) => {
  await signUp(page);
  await runDemoPath(page);

  const card = page.getByTestId("higher-target");
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: "Try a higher target" }).click();

  // The form starts a few points above the reached target (80 -> 83) and explains the rule in plain words.
  const field = page.getByLabel("Right out of 100");
  await expect(field).toHaveValue("83");
  await field.fill("80");
  await expect(page.getByText(/must be higher than the 80 out of 100 already reached/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Run the free small test" })).toBeDisabled();

  await field.fill("83");
  await page.getByRole("button", { name: "Run the free small test" }).click();

  // The project left the result step: the forecast (or the honest "not enough" card) shows, and nothing was charged yet.
  await expect(page.getByTestId("result-verified")).toHaveCount(0, { timeout: 60_000 });
  await expect(page.getByText(/out of 100/).first()).toBeVisible();
});
