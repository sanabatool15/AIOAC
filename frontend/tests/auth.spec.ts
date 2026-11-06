import { expect, test } from "@playwright/test";
import { newEmail, PASSWORD, signUp } from "./helpers";

test("sign up shows Welcome once, log in does not, log out and the guard send you to /login", async ({ page, browser }) => {
  const email = await signUp(page);
  await expect(page.getByRole("heading", { name: "Welcome to AIOAC" })).toBeVisible();

  // Log out through the user menu.
  await page.getByRole("button", { name: "Open user menu" }).click();
  await page.getByRole("menuitem", { name: /log out/i }).click();
  await expect(page).toHaveURL(/\/login/);

  // Signed out: a protected page sends you to the login screen.
  await page.goto("/projects");
  await expect(page).toHaveURL(/\/login/);

  // Log in again (a fresh browser, so no first-run flag exists): no Welcome page.
  const fresh = await (await browser.newContext()).newPage();
  await fresh.goto("/login");
  await fresh.getByLabel("Email").fill(email);
  await fresh.getByLabel("Password").fill(PASSWORD);
  await fresh.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(fresh).toHaveURL(/localhost:3100\/$/);
  await expect(fresh.getByText("Welcome to AIOAC")).toHaveCount(0);
  await expect(fresh.getByLabel("Message AIOAC")).toBeVisible();

  // A wrong password gives a plain message and keeps you on the login screen.
  const other = await (await browser.newContext()).newPage();
  await other.goto("/login");
  await other.getByLabel("Email").fill(newEmail());
  await other.getByLabel("Password").fill("not-the-password");
  await other.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(other.getByText("Wrong email or password.")).toBeVisible();
});

test("an unauthenticated visit to a project page redirects to /login", async ({ page }) => {
  await page.goto("/c/0123456789abcdef0123456789abcdef");
  await expect(page).toHaveURL(/\/login/);
});
