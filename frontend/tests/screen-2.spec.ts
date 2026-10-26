import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

// Screen 2 "Chat home" at 1440x900. Compare tests/shots/screen-2.png with Figma node 76:382.
test("signed-out visitors go to login", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
});

test("home renders greeting, composer and chips", async ({ page }) => {
  await signIn(page);
  await page.goto("/");
  await expect(page.getByText("Hello, what do you want to")).toBeVisible();
  await expect(page.getByText("No funds held")).toBeVisible();
  await expect(page.getByPlaceholder("e.g. Predict which customers may stop buying next month")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-2.png" });
});

test("typing a prompt starts a chat", async ({ page }) => {
  await signIn(page);
  await page.goto("/");
  await page.getByLabel("Message AIOAC").fill("Predict churn for my shop");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page).toHaveURL(/\/c\/chat-/);
  await expect(page.getByText("Predict churn for my shop")).toBeVisible();
});

test("suggestion chip and sample data start a chat", async ({ page }) => {
  await signIn(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Try sample data" }).click();
  await expect(page).toHaveURL(/\/c\/chat-/);
  await expect(page.getByText("sample telco churn data").first()).toBeVisible();
});

test("start-chat failure shows retry", async ({ page }) => {
  await signIn(page);
  await page.goto("/?mock=error");
  await page.getByRole("button", { name: "Which customers may stop buying?" }).click();
  await expect(page.getByRole("button", { name: "Try again" }).last()).toBeVisible();
});
