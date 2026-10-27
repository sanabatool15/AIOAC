import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 7 "Agent working (Progress)" at 1440x900. Screenshot is compared by eye with Figma node 62:1310.
test("screen 7 renders sidebar, chat trace and canvas", async ({ page }) => {
  await page.goto("/c/exp-1");
  await expect(page.getByRole("heading", { name: "Churn prediction" })).toBeVisible();
  await expect(page.getByText("6 to 9 min left").first()).toBeVisible();
  await expect(page.getByText("Where your $40 hold goes")).toBeVisible();
  await expect(page.getByText("Target to verify")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-7.png" });
});

test("screen 7 shows an error state with retry", async ({ page }) => {
  await page.goto("/c/exp-1?mock=error");
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" }).first()).toBeVisible();
});

test("screen 7 shows an empty state", async ({ page }) => {
  await page.goto("/c/exp-1?mock=empty");
  await expect(page.getByText("No messages yet")).toBeVisible();
});

test("composer send is disabled while empty", async ({ page }) => {
  await page.goto("/c/exp-1");
  const send = page.getByRole("button", { name: "Send message" });
  await expect(send).toBeDisabled();
  await page.getByLabel("Message AIOAC").fill("hello");
  await expect(send).toBeEnabled();
});
