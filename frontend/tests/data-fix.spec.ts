import { expect, test } from "@playwright/test";
import { API, signUp } from "./helpers";

// One guided data fix, in the browser, on the test launcher: not eligible -> Try a fix -> confirm -> free steps re-run
// -> pick a target again -> before and after. Money is never touched on this path.

// A small deterministic table with repeated rows and one mostly empty column.
function messyCsv(): string {
  let seed = 7;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };
  const rows: string[] = ["age,plan,charges,notes_col,left"];
  for (let i = 0; i < 900; i++) {
    const age = 20 + Math.floor(rnd() * 50);
    const plan = rnd() < 0.5 ? "basic" : "plus";
    const charges = Math.round((20 + rnd() * 80) * 100) / 100;
    const left = rnd() < (plan === "basic" ? 0.45 : 0.25) ? "yes" : "no";
    const notes = rnd() < 0.85 ? "" : String(Math.round(rnd() * 100));
    rows.push(`${age},${plan},${charges},${notes},${left}`);
  }
  for (let i = 1; i <= 60; i++) rows.push(rows[i]); // exact repeats
  return rows.join("\n") + "\n";
}

test("not eligible -> Try a fix -> confirm -> pilot again shows before and after", async ({ page }) => {
  await signUp(page);
  const post = async (path: string, data?: object) => {
    const r = await page.request.post(`${API}${path}`, data ? { data } : undefined);
    expect(r.ok(), `${path}: ${await r.text()}`).toBeTruthy();
    return r.json();
  };
  const { id } = await post("/projects", { goal: "Which customers may leave?" });
  const { candidate_id } = await post(`/projects/${id}/data`, { name: "messy", csv_text: messyCsv() });
  await post(`/projects/${id}/data/${candidate_id}/select`, { target: "left" });
  await post(`/projects/${id}/readiness`);
  await post(`/projects/${id}/baseline`);
  const first = await post(`/chats/${id}/pilot`, { target: 0.99 });
  expect(first.eligible).toBe(false);

  await page.goto(`/c/${id}`);
  await expect(page.getByTestId("eligibility-card")).toBeVisible();
  await page.getByRole("button", { name: "Try a fix (free)" }).click();

  // The confirm card shows what would change, before anything does.
  const confirm = page.getByTestId("fix-confirm");
  await expect(confirm).toBeVisible();
  await expect(confirm.getByText("Rows", { exact: true })).toBeVisible();
  await expect(confirm.getByText("Columns removed")).toBeVisible();
  await expect(confirm.getByText("notes_col", { exact: true })).toBeVisible();
  await expect(confirm.getByText(/original data stays saved/)).toBeVisible();
  await expect(confirm.getByText(/it may not/)).toBeVisible();
  await page.getByRole("button", { name: "No thanks" }).click();
  await expect(page.getByTestId("fix-confirm")).toHaveCount(0);

  await page.getByRole("button", { name: "Try a fix (free)" }).click();
  await page.getByRole("button", { name: "Yes, change my data" }).click();

  // The free steps ran again on the new data; the page asks for a target again.
  await expect(page.getByText(/Your data was changed/)).toBeVisible({ timeout: 60_000 });
  await page.getByLabel("Right out of 100").fill("99");
  await page.getByRole("button", { name: "Run the free pilot" }).click();
  await expect(page.getByTestId("fix-before-after")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByTestId("fix-before-after").getByText(/Before: about/)).toBeVisible();
  await expect(page.getByTestId("fix-before-after").getByText(/Now: about/)).toBeVisible();
  await expect(page.getByTestId("fix-before-after").getByText(/not a promise/)).toBeVisible();
});
