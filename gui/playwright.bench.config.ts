import { defineConfig } from "@playwright/test";

// Run by hand only, never in CI (Global Constraints; spec's own §9, "the benchmark in CI... is
// slow and the machine's own"): a run drives up to eighteen generated projects of up to 100,000
// declarations each, deliberately alone on the machine so its own load is what is measured, and
// minutes of capped measures at the largest, findings-heavy sizes - the opposite of what a
// shared, variably-loaded CI runner could answer honestly.
export default defineConfig({
  testDir: "bench",
  testMatch: "*.bench.ts",
  timeout: 300_000,
  workers: 1,
  reporter: "list",
  use: {
    browserName: "chromium",
    // Exactly playwright.config.ts's own line: neither dev machine has a Playwright-downloaded
    // browser, so PLAYWRIGHT_CHANNEL=chrome (or msedge on Windows) is not optional.
    ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}),
    // Fixed, so every run draws the same number of rows at the same size - a virtualised table
    // (Task 9) still depends on the viewport for how many rows are ever in the DOM at once.
    viewport: { width: 1280, height: 800 },
  },
});
