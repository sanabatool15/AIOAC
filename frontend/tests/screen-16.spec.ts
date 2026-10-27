import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => signIn(page));

// Screen 16 "Projects and share (invite + result link)" (Figma 76:3589).
test("screen 16 projects grid shows cards with status and members", async ({
  page,
}) => {
  await page.goto("/projects");
  await expect(
    page.getByRole("heading", { name: "Projects", level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByText("Everything you have trained, in one place."),
  ).toBeVisible();
  const cards = page.getByRole("listitem");
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0)).toContainText("RUNNING");
  await expect(cards.nth(0)).toContainText("Experiment 1 · 12 min ago");
  await expect(cards.nth(1)).toContainText("You + 1");
  await expect(cards.nth(2)).toContainText("Target missed · model kept");
});

test("screen 16 share dialog: members, invite, remove", async ({ page }) => {
  await page.goto("/projects");
  await page.getByRole("button", { name: "Share" }).click();
  const dlg = page.getByRole("dialog", { name: 'Share "Churn prediction"' });
  await expect(dlg).toBeVisible();
  const people = dlg.getByLabel("People with access").getByRole("listitem");
  await expect(people).toHaveCount(2);
  await expect(people.nth(0)).toContainText("David (you)");
  await expect(people.nth(0)).toContainText("Owner");
  await expect(people.nth(1)).toContainText("Editor · invite sent");
  await page.screenshot({ path: "tests/shots/screen-16.png" });
  await dlg.getByLabel("Email to invite").fill("nope");
  await dlg.getByRole("button", { name: "Invite" }).click();
  await expect(dlg.getByRole("alert")).toHaveText(
    "Enter a valid email address.",
  );
  await dlg.getByLabel("Email to invite").fill("sana@example.com");
  await dlg.getByRole("button", { name: "Invite" }).click();
  await expect(dlg.getByRole("alert")).toHaveText(
    "That person already has access.",
  );
  await dlg.getByLabel("Email to invite").fill("ali@example.com");
  await dlg.getByLabel("Role").selectOption("viewer");
  await dlg.getByRole("button", { name: "Invite" }).click();
  await expect(people).toHaveCount(3);
  await expect(people.nth(2)).toContainText("Viewer · invite sent");
  await dlg.getByRole("button", { name: "Remove ali@example.com" }).click();
  await expect(people).toHaveCount(2);
});

test("screen 16 result link toggle and copy", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/c/exp-1");
  await page.getByRole("button", { name: "Share" }).click();
  const dlg = page.getByRole("dialog", { name: /Share/ });
  await expect(dlg.getByLabel("Result link address")).toHaveText(
    "aioac.app/r/churn-8f2a91",
  );
  await dlg.getByRole("button", { name: "Copy link" }).click();
  await expect(page.getByText("Link copied.")).toBeVisible();
  await dlg.getByRole("switch", { name: "Result link" }).click();
  await expect(dlg.getByLabel("Result link address")).toHaveText("Link is off");
  await expect(dlg.getByRole("button", { name: "Copy link" })).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(dlg).toHaveCount(0);
});

test("screen 16 rename a project inline", async ({ page }) => {
  await page.goto("/projects");
  await page
    .getByRole("button", { name: "Rename project Lead scoring" })
    .click();
  const input = page.getByLabel("New name for Lead scoring");
  await input.fill("Lead scoring v2");
  await input.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Lead scoring v2" }),
  ).toBeVisible();
});

test("screen 16 share dialog shows an error state", async ({ page }) => {
  await page.goto("/projects?mock=error");
  await page.getByRole("button", { name: "Share" }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toBeVisible();
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "Try again" }),
  ).toBeVisible();
});
