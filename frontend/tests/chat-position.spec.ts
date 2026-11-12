import { expect, test } from "@playwright/test";
import { runDemoPath, signUp } from "./helpers";

// After a finished run the step cards (result, money, receipt) are tall. A new chat reply must appear next to the
// composer, not above those cards.
for (const [name, size] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 780 }]] as const) {
  test(`the newest chat message is in view after a reply (${name})`, async ({ page }) => {
    await page.setViewportSize(size);
    await signUp(page);
    await runDemoPath(page);

    const thread = page.getByLabel("Chat with the assistant");
    const before = await thread.locator("> *").count();
    await page.getByLabel("Message AIOAC").fill("Thank you, what does this result mean?");
    await page.getByLabel("Send message").click();

    // My own message and then the assistant's reply both appear, and the last one is visible on screen.
    await expect(thread.locator("> *")).toHaveCount(before + 2, { timeout: 60_000 });
    // On a phone a long reply can push my own line above the screen; the newest message (the reply) is what must be in view.
    if (name === "desktop") await expect(thread.getByText("Thank you, what does this result mean?")).toBeInViewport();
    await expect(thread.locator("> *").last()).toBeInViewport();
    // The composer is on screen with it.
    await expect(page.getByLabel("Message AIOAC")).toBeInViewport();
  });
}
