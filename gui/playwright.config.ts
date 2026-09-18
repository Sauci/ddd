import { defineConfig } from "@playwright/test";

// One worker: every test starts its own `ddd gui` over its own copy of the demo, and the journeys
// are few. Locally, PLAYWRIGHT_CHANNEL=msedge drives the installed Edge, which needs no download.
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    browserName: "chromium",
    ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}),
    trace: "retain-on-failure",
  },
});
