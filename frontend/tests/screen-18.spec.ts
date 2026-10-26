import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("18: the system states sheet shows all nine states", async ({ page }) => {
  await signIn(page);
  await page.goto("/dev/states");
  await expect(page.getByRole("heading", { name: "System states" })).toBeVisible();
  for (const t of [
    "upload failed", "connection error", "paypal declined",
    "budget almost used", "slow job", "job failed",
    "empty project", "loading", "success toast",
  ])
    await expect(page.getByRole("group", { name: t })).toBeVisible();
  await expect(page.getByText("PayPal could not hold $40")).toBeVisible();
  await page.getByRole("button", { name: "Retry for free" }).click();
  await expect(page.getByText("Retry for free (demo)")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-18.png" });
});
