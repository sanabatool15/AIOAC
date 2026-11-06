import { expect, test } from "@playwright/test";
import { runDemoPath, signUp } from "./helpers";

test("share link opens for a visitor with no cookies, shows no money, and stops working when revoked", async ({ page, browser }) => {
  const email = await signUp(page);
  const id = await runDemoPath(page);

  await page.goto(`/projects/${id}`);
  await page.getByRole("button", { name: "Share" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Create a link" }).click();
  const link = await dialog.getByLabel("Share link").inputValue();
  expect(link).toMatch(/\/s\/[A-Za-z0-9_-]+$/);

  // A brand new context: no cookies at all.
  const visitor = await browser.newContext();
  const v = await visitor.newPage();
  await v.goto(link);
  await expect(v.getByText("Built with AIOAC")).toBeVisible();
  await expect(v.getByLabel("Verified result")).toBeVisible();
  const text = await v.locator("body").innerText();
  expect(text).not.toContain(email);
  expect(text).not.toMatch(/\$\d|PayPal|Total charged|Held/);
  expect(await visitor.cookies()).toEqual([]);

  // Stop sharing: the same address is no longer available.
  await dialog.getByRole("button", { name: "Stop sharing" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Stop sharing" }).click();
  await expect(dialog.getByText("SHARING IS OFF")).toBeVisible();
  await v.reload();
  await expect(v.getByText("This link is not available")).toBeVisible();
  await visitor.close();
});
