import { test, expect } from "@playwright/test";
import { signIn } from "./helpers";

// Screens 3a / 3b / 3c "Add data" modal at 1440x900.
// Compare tests/shots/screen-3a|3b|3c.png with Figma nodes 76:557, 76:757, 76:984.
const csv = { name: "churn_sample.csv", mimeType: "text/csv", buffer: Buffer.from("a,b\n1,2\n") };

test.beforeEach(async ({ page }) => {
  await signIn(page);
  await page.goto("/");
});

test("3a: attach opens upload tab; upload shows progress then enables Add", async ({ page }) => {
  await page.getByRole("button", { name: "Attach data" }).click();
  const dialog = page.getByRole("dialog", { name: "Add data" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("tab", { name: "Upload" })).toHaveAttribute("aria-selected", "true");
  await expect(dialog.getByText("Drag and drop files here")).toBeVisible();
  await expect(dialog.getByText("CSV, Parquet or Excel · up to 200 MB")).toBeVisible();
  await expect(dialog.getByText("Your data stays private to your project and is never used to train anything else.")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Add to project" })).toBeDisabled();

  await dialog.getByLabel("Choose data files").setInputFiles(csv);
  const row = dialog.getByTestId("upload-row");
  await expect(row).toContainText("churn_sample.csv");
  await expect(dialog.getByRole("button", { name: "Add to project" })).toBeDisabled(); // still uploading
  await expect(row.getByText(/^(4\d|5\d|6\d|7\d|8\d)%$/)).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-3a.png" });

  await expect(row.getByLabel("Uploaded")).toBeVisible({ timeout: 8000 });
  await dialog.getByRole("button", { name: "Add to project" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText("1 dataset added to your project")).toBeVisible();
  await expect(page.getByText("4 files")).toBeVisible(); // sidebar refetched
});

test("3a: wrong file type is rejected; upload can be cancelled", async ({ page }) => {
  await page.getByRole("button", { name: "Attach data" }).click();
  const dialog = page.getByRole("dialog", { name: "Add data" });
  await dialog.getByLabel("Choose data files").setInputFiles({ name: "notes.pdf", mimeType: "application/pdf", buffer: Buffer.from("x") });
  await expect(dialog.getByRole("alert")).toContainText("Use a CSV, Parquet or Excel file.");
  await expect(dialog.getByTestId("upload-row")).toHaveCount(0);

  await dialog.getByLabel("Choose data files").setInputFiles(csv);
  await dialog.getByRole("button", { name: "Cancel churn_sample.csv" }).click();
  await expect(dialog.getByTestId("upload-row")).toHaveCount(0);
});

test("3b: Hugging Face link is detected", async ({ page }) => {
  await page.getByRole("button", { name: "Attach data" }).click();
  const dialog = page.getByRole("dialog", { name: "Add data" });
  await dialog.getByRole("tab", { name: "Paste a link" }).click();
  await expect(dialog.getByText("WORKS WITH")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Add to project" })).toBeDisabled();
  await dialog.getByLabel("Dataset link").fill("https://huggingface.co/datasets/scikit-learn/telco-churn");
  const card = dialog.getByTestId("detected-card");
  await expect(card).toContainText("Hugging Face dataset detected");
  await expect(card).toContainText("scikit-learn/telco-churn · public");
  await expect(card).toContainText("FOUND");
  await expect(card).toContainText("7,043");
  await expect(card).toContainText("suggested target");
  for (const t of ["Hugging Face", "Kaggle", "Google Drive", "Dropbox", "GitHub (raw)", "Amazon S3 link", "Any CSV or Parquet URL"]) {
    await expect(dialog.getByText(t, { exact: true }).first()).toBeVisible();
  }
  await page.screenshot({ path: "tests/shots/screen-3b.png" });
  await dialog.getByRole("button", { name: "Add to project" }).click();
  await expect(page.getByText("1 dataset added to your project")).toBeVisible();
});

test("3b: bad link shows an error with retry", async ({ page }) => {
  await page.getByRole("button", { name: "Attach data" }).click();
  const dialog = page.getByRole("dialog", { name: "Add data" });
  await dialog.getByRole("tab", { name: "Paste a link" }).click();
  await dialog.getByLabel("Dataset link").fill("not a link");
  await expect(dialog.getByRole("alert")).toContainText("does not look like a link");
  await expect(dialog.getByRole("button", { name: "Try again" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Add to project" })).toBeDisabled();
});

test("3c: sidebar data source opens Connect tab with every source state", async ({ page }) => {
  await page.getByRole("button", { name: /Hugging Face/ }).click();
  const dialog = page.getByRole("dialog", { name: "Add data" });
  await expect(dialog.getByRole("tab", { name: "Connect an account" })).toHaveAttribute("aria-selected", "true");
  await expect(dialog.getByTestId("source-huggingface")).toContainText("Connected");
  await expect(dialog.getByTestId("source-kaggle")).toContainText("Syncing...");
  await expect(dialog.getByTestId("source-gdrive")).toContainText("Token expired");
  await expect(dialog.getByTestId("source-dropbox").getByRole("button", { name: "Connect" })).toBeVisible();
  await expect(dialog.getByTestId("source-s3")).toContainText("COMING SOON");
  await expect(dialog.getByTestId("source-database")).toContainText("COMING SOON");
  await page.screenshot({ path: "tests/shots/screen-3c.png" });

  await dialog.getByRole("button", { name: "Reconnect" }).click();
  await expect(dialog.getByTestId("source-gdrive")).toContainText("Connected");
  await dialog.getByTestId("source-dropbox").getByRole("button", { name: "Connect" }).click();
  await expect(dialog.getByTestId("source-dropbox")).toContainText("Connected");
  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(dialog).toBeHidden();
});

test("modal closes with Escape and Close, and tabs keep their state", async ({ page }) => {
  await page.getByRole("button", { name: "Attach data" }).click();
  const dialog = page.getByRole("dialog", { name: "Add data" });
  await dialog.getByRole("tab", { name: "Paste a link" }).click();
  await dialog.getByLabel("Dataset link").fill("https://www.kaggle.com/datasets/a/b");
  await expect(dialog.getByTestId("detected-card")).toContainText("Kaggle dataset detected");
  await dialog.getByRole("tab", { name: "Upload" }).click();
  await dialog.getByRole("tab", { name: "Paste a link" }).click();
  await expect(dialog.getByTestId("detected-card")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await page.getByRole("button", { name: "Attach data" }).click();
  await page.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toBeHidden();
});
