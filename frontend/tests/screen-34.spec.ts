import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test.beforeEach(async ({ page }) => {
  await signIn(page);
});

test("34: project page shows runs, model versions and heading", async ({ page }) => {
  await page.goto("/projects/churn");
  const main = page.getByRole("region", { name: "Project" });
  await expect(main.getByRole("heading", { name: "Churn prediction", level: 1 })).toBeVisible();
  await expect(main.getByText("ROUND 2 RUNNING")).toBeVisible();
  const table = main.getByRole("table", { name: "Runs" });
  await expect(table.getByRole("row")).toHaveCount(4);
  await expect(table.getByText("77.9% / 61.2%")).toBeVisible();
  await expect(table.getByText("$0 so far")).toBeVisible();
  const versions = main.getByTestId("model-versions");
  await expect(versions.getByText("Best so far")).toBeVisible();
  await expect(versions.getByText("Download unlocks when a target is met.")).toBeVisible();
  await expect(page.getByText("No funds held")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-34.png" });
});

test("34: Open chat goes to the experiment", async ({ page }) => {
  await page.goto("/projects/churn");
  await page.getByRole("link", { name: "Open chat" }).click();
  await expect(page).toHaveURL(/\/c\/exp-1/);
});

test("34: tabs switch, Chats lists the project chats", async ({ page }) => {
  await page.goto("/projects/churn");
  const main = page.getByRole("region", { name: "Project" });
  await main.getByRole("tab", { name: "Chats" }).click();
  await expect(main.getByRole("link", { name: "Feature check" })).toBeVisible();
  await main.getByRole("tab", { name: "Data" }).click();
  await expect(main.getByText("Data is not designed yet")).toBeVisible();
});

test("34: deleting a model version needs the checkbox and removes it", async ({ page }) => {
  await page.goto("/projects/churn");
  await page.getByRole("button", { name: "Delete model Baseline" }).click();
  const dialog = page.getByRole("alertdialog");
  await expect(dialog.getByRole("button", { name: "Delete model" })).toBeDisabled();
  await dialog.getByText("I understand I cannot get it back").click();
  await dialog.getByRole("button", { name: "Delete model" }).click();
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Delete model Baseline" })).toHaveCount(0);
});

test("34: a project with no runs shows empty states", async ({ page }) => {
  await page.goto("/projects/lead");
  await expect(page.getByText("No runs yet")).toBeVisible();
  await expect(page.getByText("No model versions yet.")).toBeVisible();
});

test("34: unknown project and server errors show an error with retry", async ({ page }) => {
  await page.goto("/projects/nope");
  await expect(page.getByText("Project not found.")).toBeVisible();
  await page.goto("/projects/churn?mock=error");
  await expect(page.getByRole("region", { name: "Project" }).getByRole("button", { name: "Try again" })).toBeVisible();
});

test("34: project cards link to the project page", async ({ page }) => {
  await page.goto("/projects");
  await page.getByRole("link", { name: "Churn prediction" }).first().click();
  await expect(page).toHaveURL(/\/projects\/churn/);
});
