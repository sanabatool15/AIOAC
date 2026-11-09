import { expect, test } from "@playwright/test";
import { API, runDemoPath, signUp } from "./helpers";

// Real backend: the demo run saves Version 1 and it is in use.
test("Model tab lists Version 1 as in use after the demo run", async ({ page }) => {
  await signUp(page);
  const id = await runDemoPath(page);
  await page.goto(`/projects/${id}?tab=model`);
  const versions = page.getByLabel("Versions");
  await expect(versions).toBeVisible();
  const one = versions.getByLabel("Version 1");
  await expect(one).toContainText("In use");
  await expect(one).toContainText(/out of 100 right on rows it never saw/);
  await expect(one.getByRole("button", { name: "Use this version" })).toHaveCount(0);
  await expect(one.getByRole("button", { name: "Download" })).toBeVisible();
  await expect(page.getByTestId("compare-line")).toHaveCount(0); // one version: nothing to compare
  await page.getByRole("tab", { name: "History" }).click();
  await expect(page.getByText(/Round 1: Finished · saved as version 1/)).toBeVisible();
});

// Switching the version: the two versions come from intercepted responses (a second paid run is not part of the
// browser launcher), the switch itself is a real POST that the test observes.
test("Use this version switches the version in use and refreshes the list", async ({ page }) => {
  await signUp(page);
  const id = await runDemoPath(page);
  const real = await (await page.request.get(`${API}/projects/${id}/model/versions`)).json();
  const base = real[0];
  let current = 2;
  const list = () => [
    { ...base, model_id: "m2", version_no: 2, is_current: current === 2, verified_value: 0.9, passed: true, dataset_version_id: "d1" },
    { ...base, model_id: "m1", version_no: 1, is_current: current === 1, verified_value: 0.87, passed: true, dataset_version_id: "d1" },
  ];
  const posted: string[] = [];
  await page.route(`**/projects/${id}/model/versions`, (r) => r.fulfill({ json: list() }));
  await page.route(`**/projects/${id}/model/m1/use`, (r) => {
    posted.push(r.request().url());
    current = 1;
    return r.fulfill({ json: { model_id: "m1", version_no: 1, is_current: true } });
  });

  await page.goto(`/projects/${id}?tab=model`);
  const versions = page.getByLabel("Versions");
  await expect(versions.getByLabel("Version 2")).toContainText("In use");
  await expect(page.getByTestId("compare-line")).toHaveText(
    "Version 2 is 3 points better than version 1 (an estimate from rows neither model saw).",
  );
  await expect(versions.getByLabel("Version 1")).not.toContainText("In use");

  await versions.getByLabel("Version 1").getByRole("button", { name: "Use this version" }).click();
  await expect(versions.getByLabel("Version 1")).toContainText("In use");
  await expect(versions.getByLabel("Version 2")).not.toContainText("In use");
  expect(posted).toHaveLength(1);
});
