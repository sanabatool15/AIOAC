import { test, expect } from "@playwright/test";

// Screen 1 "Login / sign up" at 1440x900. Compare tests/shots/screen-1.png with Figma node 76:339.
test("app starts on the login screen", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(page.getByText("Train with proof.")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-1.png" });
});

test("login validates, then signs in", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.locator("form [role=alert]")).toContainText("valid email");
  await page.getByLabel("Email").fill("you@example.com");
  await page.getByLabel("Password").fill("secret123");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/localhost:3000\/$/);
});

test("google button signs in the demo user, signup page works", async ({ page }) => {
  await page.goto("/signup");
  await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await expect(page).toHaveURL(/localhost:3000\/$/);
});

test("forgot password needs an email, then confirms", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Forgot password?" }).click();
  await expect(page.locator("form [role=alert]")).toBeVisible();
  await page.getByLabel("Email").fill("you@example.com");
  await page.getByRole("button", { name: "Forgot password?" }).click();
  await expect(page.getByRole("status")).toContainText("reset link");
});
