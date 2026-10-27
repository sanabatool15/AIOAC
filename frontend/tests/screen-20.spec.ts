import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => {
  await signIn(page);
  await page.goto("/c/baseline");
});

test("user menu opens with identity, plan and rows", async ({ page }) => {
  const trigger = page.getByRole("button", { name: "Open user menu" });
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await trigger.click();
  const menu = page.getByRole("menu", { name: "User menu" });
  await expect(menu).toBeVisible();
  await expect(menu.getByText("mwmfigma@gmail.com")).toBeVisible();
  await expect(menu.getByText("2 of 3 projects used")).toBeVisible();
  for (const n of ["Settings", "Usage and plan", "Billing and invoices", "API keys", "Help and feedback", "Log out"]) {
    await expect(menu.getByRole("menuitem", { name: n })).toBeVisible();
  }
  await page.screenshot({ path: "tests/shots/screen-20.png" });
});

test("closes on Escape and outside click", async ({ page }) => {
  const trigger = page.getByRole("button", { name: "Open user menu" });
  await trigger.click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu", { name: "User menu" })).toHaveCount(0);
  await trigger.click();
  await page.mouse.click(900, 300);
  await expect(page.getByRole("menu", { name: "User menu" })).toHaveCount(0);
});

test("API keys row navigates", async ({ page }) => {
  await page.getByRole("button", { name: "Open user menu" }).click();
  await page.getByRole("menuitem", { name: "API keys" }).click();
  await expect(page).toHaveURL(/\/settings\/keys/);
});

test("log out clears session and goes to login", async ({ page }) => {
  await page.getByRole("button", { name: "Open user menu" }).click();
  await page.getByRole("menuitem", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login/);
  expect(await page.evaluate(() => localStorage.getItem("aioac.session"))).toBeNull();
});

test("log out failure shows error toast and stays", async ({ page }) => {
  await page.getByRole("button", { name: "Open user menu" }).click();
  // respond() reads ?mock at call time; set it after the shell has loaded.
  await page.evaluate(() => window.history.replaceState(null, "", "/c/baseline?mock=error"));
  await page.getByRole("menuitem", { name: "Log out" }).click();
  await expect(page.getByText("Could not log out. Try again.")).toBeVisible();
  await expect(page).toHaveURL(/\/c\/baseline/);
});
