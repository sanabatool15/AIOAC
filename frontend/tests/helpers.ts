import { expect, type Page } from "@playwright/test";

// Ports of the two servers that playwright.config.ts starts.
export const API = "http://localhost:8765";
export const APP = "http://localhost:3100";

let counter = 0;
export function newEmail(): string {
  counter += 1;
  return `user${Date.now()}${counter}@example.com`;
}
export const PASSWORD = "correct-horse-battery";

/** Sign up through the screen. The app opens on the Welcome page after the first sign-up. */
export async function signUp(page: Page, email = newEmail()): Promise<string> {
  await page.goto("/signup");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign up", exact: true }).click();
  await expect(page).toHaveURL(/\/welcome$/);
  return email;
}

/**
 * The whole demo path on the test launcher (scripted model, mock PayPal, local training): goal, dataset card,
 * data check, free test, target, price, approve and pay, mock return, verified result and receipt.
 * Returns the project id.
 */
export async function runDemoPath(page: Page): Promise<string> {
  await page.getByRole("link", { name: "Start" }).click();
  await page.getByLabel("Message AIOAC").fill("I want to predict which customers will leave. I have no data.");
  await page.getByLabel("Send message").click();
  await expect(page).toHaveURL(/\/c\/[0-9a-f]+$/);
  const id = page.url().split("/c/")[1];

  // The approval card names the dataset before anything is chosen.
  const card = page.getByRole("button", { name: "Approve", exact: true });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("scikit-learn/churn-prediction").first()).toBeVisible();
  await expect(page.getByText("Hugging Face").first()).toBeVisible();
  await card.click();

  await page.getByRole("button", { name: "Check my data" }).click();
  await expect(page.getByText(/Data check: grade/)).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Run the free test" }).click();
  await expect(page.getByText(/out of 100 right/).first()).toBeVisible({ timeout: 60_000 });

  await page.getByLabel("Right out of 100").fill("80");
  await page.getByRole("button", { name: "Run the free pilot" }).click();
  await page.getByRole("button", { name: "Get my price" }).click({ timeout: 90_000 });
  await expect(page.getByText("The most you can ever be charged (the cap)")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Approve and pay" }).click();

  // The mock PayPal sends the browser to /pay/return; the page confirms the hold on the server, then the run starts.
  await expect(page.getByTestId("result-verified")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText("PayPal hold (the cap)")).toBeVisible();
  return id;
}
