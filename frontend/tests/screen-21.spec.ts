import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

test("21: usage and plan shows plan, meters, card, hold and activity", async ({
  page,
}) => {
  await page.goto("/account/usage");
  await expect(
    page.getByRole("heading", { name: "Usage and plan", level: 1 }),
  ).toBeVisible();
  await expect(page.getByTestId("current-plan")).toContainText("Starter");
  await expect(page.getByTestId("current-plan")).toContainText("ACTIVE");
  const meters = page.getByTestId("usage-meters");
  await expect(
    meters.getByRole("progressbar", { name: "Projects" }),
  ).toHaveAttribute("aria-valuenow", "67");
  await expect(meters.getByText("184 MB of 500 MB")).toBeVisible();
  await expect(
    meters.getByRole("progressbar", { name: "Experiment jobs" }),
  ).toHaveAttribute("aria-valuenow", "60");
  await expect(page.getByTestId("payment-method")).toContainText(
    "Visa ending 4242",
  );
  await expect(page.getByTestId("payment-method")).toContainText("DEFAULT");
  await expect(page.getByTestId("held-now")).toContainText("$0.00");
  const table = page.getByRole("table", { name: "Recent activity" });
  await expect(table.getByRole("row")).toHaveCount(3);
  await expect(table.getByText("Captured")).toBeVisible();
  await expect(table.getByText("Voided")).toBeVisible();
  await expect(page.getByText("You pay $0 unless target met")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-21.png" });
});

test("21: user menu opens it, links point at billing screens", async ({
  page,
}) => {
  await page.goto("/c/baseline");
  await page.getByRole("button", { name: "Open user menu" }).click();
  await page.getByRole("menuitem", { name: /Usage and plan/ }).click();
  await expect(page).toHaveURL(/\/account\/usage/);
  await expect(page.getByRole("link", { name: "Manage" })).toHaveAttribute(
    "href",
    "/account/billing",
  );
  await expect(
    page.getByRole("link", { name: "Upgrade plan" }),
  ).toHaveAttribute("href", "/billing/plan");
});

test("21: error then retry, and empty states", async ({ page }) => {
  await page.goto("/account/usage?mock=error");
  const region = page.getByRole("region", { name: "Usage and plan" });
  await expect(
    region.getByText("We could not reach the server."),
  ).toBeVisible();
  await page.goto("/account/usage?mock=empty");
  await expect(page.getByText("No payment method")).toBeVisible();
  await expect(page.getByText("No activity yet")).toBeVisible();
});
