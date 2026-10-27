import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => {
  await signIn(page);
});

test("35: first-run layout shows examples, sample card and three steps", async ({ page }) => {
  await page.goto("/welcome");
  await expect(page.getByRole("heading", { name: "What do you want to predict?" })).toBeVisible();
  for (const e of ["Which customers will churn?", "Score my sales leads", "Will this loan be repaid?", "Forecast next month demand"])
    await expect(page.getByRole("button", { name: e })).toBeVisible();
  await expect(page.getByTestId("sample-card").getByText("7,043 customers · 21 columns · safe public dataset")).toBeVisible();
  const steps = page.getByRole("list", { name: "How it works" });
  await expect(steps.getByRole("listitem")).toHaveCount(3);
  await expect(steps.getByText("Independent test decides")).toBeVisible();
  await expect(page.getByText("Hugging Face")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-35.png" });
});

test("35: sample button starts the sample chat and ends first run", async ({ page }) => {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem("seeded")) {
      sessionStorage.setItem("seeded", "1");
      localStorage.setItem("aioac.firstrun", "1");
    }
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "What do you want to predict?" })).toBeVisible();
  await page.getByRole("button", { name: "Use telco churn sample" }).click();
  await expect(page).toHaveURL(/\/c\/chat-/);
  await page.goto("/");
  await expect(page.getByText("Hello, what do you want to")).toBeVisible();
});

test("35: an example chip and the composer start a chat", async ({ page }) => {
  await page.goto("/welcome");
  await page.getByRole("button", { name: "Score my sales leads" }).click();
  await expect(page).toHaveURL(/\/c\/chat-/);
  await expect(page.getByText("Score my sales leads").first()).toBeVisible();
});

test("35: start failure shows a retry", async ({ page }) => {
  await page.goto("/welcome?mock=error");
  await page.getByRole("button", { name: "Score my sales leads" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Could not start the chat." })).toBeVisible();
});

test("35: sign-up lands on the first-run screen", async ({ page }) => {
  await page.addInitScript(() => localStorage.removeItem("aioac.session"));
  await page.goto("/signup");
  await page.getByLabel("Email").fill("new@example.com");
  await page.getByLabel("Password").fill("longenough1");
  await page.getByRole("button", { name: "Sign up", exact: true }).click();
  await expect(page.getByRole("heading", { name: "What do you want to predict?" })).toBeVisible();
});
