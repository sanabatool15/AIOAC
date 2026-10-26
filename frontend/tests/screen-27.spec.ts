import { test, expect } from "@playwright/test";

// Screen 27 "Public result page" (Figma 76:5819). No sign-in needed.
test("screen 27 opens without signing in and shows results only", async ({ page }) => {
  await page.goto("/s/demo");
  await expect(page).toHaveURL(/\/s\/demo/);
  await expect(page.getByText("SHARED RESULT · VIEW ONLY")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Churn prediction" })).toBeVisible();
  await expect(page.getByText("Trained by David · Oct 24, 2026 · 7,043 customers")).toBeVisible();
  await expect(page.getByText("TARGET MET")).toBeVisible();
  await expect(page.getByText("Target reached on unseen data")).toBeVisible();
  await expect(page.getByTestId("metric-precision")).toContainText("82.4%");
  await expect(page.getByTestId("metric-recall")).toContainText("63.1%");
  const money = page.getByTestId("money-recap");
  await expect(money).toContainText("THE MONEY, IN PLAIN NUMBERS");
  await expect(money).toContainText("$18.60");
  await expect(money).toContainText("The owner was only charged because the independent test passed.");
  await expect(page.getByLabel("How it was checked").getByText("Charge captured only after the test passed")).toBeVisible();
  await expect(page.getByText("Data files, API keys and chat history stay private to the owner.")).toBeVisible();
  await expect(page.getByRole("complementary")).toHaveCount(0); // no app sidebar
  await page.screenshot({ path: "tests/shots/screen-27.png" });
});

test("screen 27 header links and unknown link", async ({ page }) => {
  await page.goto("/s/demo");
  await expect(page.getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
  await expect(page.getByRole("link", { name: "Train your own" })).toHaveAttribute("href", "/signup");
  await page.goto("/s/nope");
  await expect(page.getByRole("alert").first()).toContainText("not found");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});
