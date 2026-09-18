import { defineConfig } from "@playwright/test";

// The stories of src/, photographed from Ladle's build and compared with the images committed
// under screenshots/references. Only ever run in Playwright's Linux image (docker compose run
// --rm gui-screenshots, or the gui-screenshots job of ci): Windows and Linux draw text
// differently, so references made anywhere else would fail everywhere else.
export default defineConfig({
  testDir: "screenshots",
  snapshotPathTemplate: "{testDir}/references/{arg}{ext}",
  workers: 1,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { browserName: "chromium", baseURL: "http://127.0.0.1:61000" },
  webServer: {
    command: "npx ladle preview --host 127.0.0.1 --port 61000",
    url: "http://127.0.0.1:61000",
    reuseExistingServer: false,
  },
});
