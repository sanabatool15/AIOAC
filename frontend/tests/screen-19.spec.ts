import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("19: the motion spec sheet shows tool states, stages, ETA rules and timings", async ({ page }) => {
  await signIn(page);
  await page.goto("/dev/motion");
  await expect(page.getByRole("heading", { name: "Tool strip states" })).toBeVisible();
  const states = page.getByRole("region", { name: "Tool strip states" });
  for (const s of ["Idle", "Running", "Done", "Error"]) await expect(states.getByText(s, { exact: true })).toBeVisible();
  const stages = page.getByRole("region", { name: "Training stages and ETA" });
  await expect(stages.getByRole("listitem")).toHaveCount(10);
  await expect(stages.getByText("Always show a range, never one exact number.")).toBeVisible();
  const timing = page.getByRole("table", { name: "Timing reference" });
  await expect(timing.getByRole("row")).toHaveCount(11);
  await expect(timing.getByText("280 ms ease-out")).toBeVisible();
  await expect(page.getByText(/Respect "reduce motion"/)).toBeVisible();
  await expect(page.getByText("Hugging Face")).toBeVisible();
  await page.screenshot({ path: "tests/shots/screen-19.png" });
});
