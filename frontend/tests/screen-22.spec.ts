import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

test("22: choose a plan shows three plans, current plan and tracker", async ({
  page,
}) => {
  await page.goto("/billing/plan");
  await expect(
    page.getByRole("heading", { name: "Choose a plan" }),
  ).toBeVisible();
  const steps = page.getByRole("list", { name: "Steps" });
  await expect(steps.getByRole("listitem")).toHaveCount(4);
  await expect(steps.locator("[aria-current=step]")).toContainText("Plan");
  const starter = page.getByRole("article", { name: "Starter plan" });
  await expect(starter).toContainText("CURRENT");
  await expect(
    starter.getByRole("button", { name: "Current plan" }),
  ).toBeDisabled();
  const pro = page.getByRole("article", { name: "Pro plan" });
  await expect(pro).toContainText("MOST POPULAR");
  await expect(pro).toContainText("$29");
  await expect(pro.getByRole("listitem")).toHaveCount(6);
  await expect(page.getByRole("article", { name: "Team plan" })).toContainText(
    "$99",
  );
  await expect(
    page.getByText("you are charged for a job only if its target is verified."),
  ).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-22.png" });
});

test("22: yearly toggle discounts prices and Choose Pro carries the choice", async ({
  page,
}) => {
  await page.goto("/billing/plan");
  await page.getByRole("button", { name: /Yearly/ }).click();
  await expect(page.getByRole("article", { name: "Pro plan" })).toContainText(
    "$23.20",
  );
  await page.getByRole("button", { name: "Choose Pro" }).click();
  await expect(page).toHaveURL(/\/billing\/payment\?plan=pro&cycle=yearly/);
});

test("22: close returns to usage; error state retries", async ({ page }) => {
  await page.goto("/billing/plan");
  await page.getByRole("link", { name: /Close/ }).click();
  await expect(page).toHaveURL(/\/account\/usage/);
  await page.goto("/billing/plan?mock=error");
  await expect(page.getByText("We could not reach the server.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});
