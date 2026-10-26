import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("32: payment states sheet has six states, each with two actions", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/dev/payment-states");
  await expect(
    page.getByRole("heading", { name: "Payment states" }),
  ).toBeVisible();
  for (const tag of [
    "hold expired",
    "card declined",
    "3d secure",
    "card expiring",
    "paypal unavailable",
    "plan limit",
  ]) {
    const card = page.getByRole("group", { name: tag, exact: true });
    await expect(card).toBeVisible();
    await expect(
      card.getByRole("button").or(card.getByRole("link")),
    ).toHaveCount(2);
  }
  await expect(page.getByRole("group", { name: "hold expired" })).toContainText(
    "Nothing was charged.",
  );
  await expect(page.getByText("Hugging Face")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-32.png" });
  await page.getByRole("button", { name: "Place new hold" }).click();
  await expect(page.getByText("Place new hold (demo)")).toBeVisible();
  await page.getByRole("link", { name: "Upgrade plan" }).click();
  await expect(page).toHaveURL(/\/billing\/plan/);
});
