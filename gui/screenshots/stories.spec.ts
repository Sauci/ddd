import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const meta = JSON.parse(
  readFileSync(new URL("../ladle-build/meta.json", import.meta.url), "utf8"),
) as { stories: Record<string, unknown> };

for (const story of Object.keys(meta.stories)) {
  test(story, async ({ page }) => {
    await page.goto(`/?story=${story}&mode=preview`, { waitUntil: "networkidle" });
    // Ladle marks <html data-storyloaded> before the story's own code has arrived: waiting on
    // that alone photographs its spinner.
    await expect(page.locator(".ladle-ring-wrapper")).toHaveCount(0);
    await expect(page).toHaveScreenshot(`${story}.png`, { fullPage: true });
  });
}
