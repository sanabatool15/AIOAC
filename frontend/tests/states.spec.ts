import { expect, test, type Page } from "@playwright/test";
import { API, signUp } from "./helpers";

// Project states that the launcher cannot reach quickly are drawn from api.md-shaped JSON, with the browser's own
// requests intercepted. The JSON below follows specs/api.md sections A2 and A5.
const GOAL = "Which customers may stop buying?";
const quote = { id: "q1", estimate_cents: 56, low_cents: 55, high_cents: 56, cap_cents: 56, success_fee_max_cents: 3, approved: true };
const project = (id: string, status: string, run: unknown) => ({
  id, goal: GOAL, status, readiness_grade: "A", trust_level: "Low",
  baseline: { accuracy: 0.73, simple_guess_accuracy: 0.7 }, quote,
  dataset: { rows: 1500, columns: 4, target: "churn", source: "upload", license: null },
  readiness: { grade: "A", findings: [{ kind: "OK", text: "Enough rows to train a useful model" }] },
  forecast: null, payment: { payment_id: "p1", state: "released", approve_url: null, hold_cents: 56 }, run,
});
const training = (status: string, result: unknown, extra: object = {}) => ({
  run_id: "r1", status, stage: status === "running" ? "training the model" : "done", fraction: status === "running" ? 0.5 : 1,
  elapsed_seconds: 90, spend_so_far_cents: 40, spend_is_estimate: true, cap_cents: 53,
  eta: status === "running" ? { low_seconds: 30, high_seconds: 150, is_estimate: true } : null,
  stop_requested: false, result, ...extra,
});
const receipt = (compute: number, fee: number, released: number, state = "released") => ({
  payment_id: "p1", project_id: "x", state, hold_cents: 56, compute_captured_cents: compute, fee_captured_cents: fee,
  released_cents: released, total_charged_cents: compute + fee, approve_url: null,
});

async function setup(page: Page, status: string, run: unknown, train: unknown, pay: unknown) {
  await signUp(page);
  const created = await (await page.request.post(`${API}/projects`, { data: { goal: GOAL } })).json();
  const id: string = created.id;
  const json = (body: unknown, code = 200) => ({ status: code, contentType: "application/json", body: JSON.stringify(body) });
  await page.route(new RegExp(`/projects/${id}$`), (r) => (r.request().method() === "GET" ? r.fulfill(json(project(id, status, run))) : r.continue()));
  await page.route(new RegExp(`/projects/${id}/messages$`), (r) =>
    r.fulfill(json([{ id: "m1", role: "user", text: GOAL, kind: "chat", blocks: [], created_at: new Date().toISOString() }])));
  await page.route(new RegExp(`/projects/${id}/training$`), (r) => r.fulfill(json(train)));
  await page.route(new RegExp(`/projects/${id}/payment$`), (r) => r.fulfill(json(pay)));
  await page.route(new RegExp(`/payments/p1$`), (r) => r.fulfill(json(pay)));
  return id;
}

test("training in progress shows progress and Stop asks for confirmation; stop calls the server", async ({ page }) => {
  let stopCalled = false;
  const id = await setup(page, "training", { run_id: "r1", status: "running" }, training("running", null), receipt(0, 0, 0, "held"));
  await page.route(new RegExp(`/projects/${id}/training/stop$`), (r) => {
    stopCalled = true;
    return r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ run_id: "r1", stop_requested: true }) });
  });
  await page.goto(`/c/${id}`);
  await expect(page.getByText("Spent so far (estimate)")).toBeVisible();
  await expect(page.getByText("Compute limit (the cap)")).toBeVisible();
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByRole("alertdialog", { name: "Stop the run" })).toBeVisible();
  await page.getByRole("button", { name: "Yes, stop now" }).click();
  await expect.poll(() => stopCalled).toBe(true);
});

test("a stopped run: you pay the compute used, no fee", async ({ page }) => {
  const id = await setup(page, "stopped", { run_id: "r1", status: "stopped" }, training("stopped", { stopped_by_user: true }), receipt(40, 0, 16));
  await page.goto(`/c/${id}`);
  await expect(page.getByRole("heading", { name: "You stopped the run" })).toBeVisible();
  await expect(page.getByText(/no success fee/i).first()).toBeVisible();
  await expect(page.getByText("$0.40").first()).toBeVisible();
});

test("a missed target: compute only, no success fee, and a free Improve round", async ({ page }) => {
  const missed = { accuracy: 0.72, simple_guess_accuracy: 0.7, runtime_seconds: 88, verification: { value: 0.72, target: 0.8, passed: false } };
  const id = await setup(page, "done", { run_id: "r1", status: "done" }, training("done", missed), receipt(40, 0, 16));
  await page.goto(`/c/${id}`);
  await expect(page.getByTestId("result-missed")).toBeVisible();
  await expect(page.getByText("NOT MET")).toBeVisible();
  await expect(page.getByText("$0.40").first()).toBeVisible();
  await expect(page.getByText("$0.00").first()).toBeVisible(); // success fee
});

test("a failed run on our side: nothing is charged", async ({ page }) => {
  const id = await setup(page, "voided", { run_id: "r1", status: "failed" }, training("failed", { error: "training failed" }), receipt(0, 0, 56, "voided"));
  await page.goto(`/c/${id}`);
  await expect(page.getByRole("heading", { name: "Something went wrong on our side" })).toBeVisible();
  await expect(page.getByText(/You pay \$0/).first()).toBeVisible();
});

test("a cancelled hold: voided with no run says the whole hold was released", async ({ page }) => {
  const id = await setup(page, "voided", null, { status: "not_started" }, receipt(0, 0, 56, "voided"));
  await page.goto(`/c/${id}`);
  await expect(page.getByRole("heading", { name: "Nothing was charged" })).toBeVisible();
  await expect(page.getByText("The whole hold was released.")).toBeVisible();
});
