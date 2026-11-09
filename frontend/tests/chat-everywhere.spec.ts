import { expect, test } from "@playwright/test";
import { runDemoPath, signUp } from "./helpers";

// The project chat is on the project page too, collapsed until opened, and it never blocks the tabs.
for (const [name, size] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 780 }]] as const) {
  test(`the project page has a collapsible chat that shares the project's messages (${name})`, async ({ page }) => {
    await page.setViewportSize(size);
    await signUp(page);
    const id = await runDemoPath(page);

    await page.goto(`/projects/${id}`);
    const toggle = page.getByRole("button", { name: /Ask about this project/ });
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByLabel("Chat with the assistant")).toHaveCount(0); // nothing loaded while collapsed

    await toggle.click();
    const thread = page.getByLabel("Chat with the assistant");
    await expect(thread).toBeVisible();
    const before = await thread.locator("> *").count();
    await page.getByLabel("Message AIOAC").fill("What does this result mean?");
    await page.getByLabel("Send message").click();
    await expect(thread.locator("> *")).toHaveCount(before + 2, { timeout: 60_000 });

    // the tabs still work while the chat is open, and the page does not scroll sideways
    await page.getByRole("tab", { name: "History" }).click();
    await expect(page.getByRole("tab", { name: "History" })).toHaveAttribute("aria-selected", "true");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);

    // the same messages are on the chat page
    await page.goto(`/c/${id}`);
    await expect(page.getByLabel("Chat with the assistant").getByText("What does this result mean?")).toBeVisible();
  });
}
