import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The compiled pages go where the Python package serves them from; git ignores that directory
// and the wheel carries it. The coverage gate covers the modules that hold logic: the screens
// are covered end to end by Playwright (e2e/).
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/ddd/gui/static",
    emptyOutDir: true,
  },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
    coverage: {
      provider: "v8",
      include: ["src/api/**/*.ts", "src/lib/**/*.ts", "src/state/**/*.ts"],
      exclude: ["src/**/*.test.ts"],
      reporter: ["text"],
      thresholds: { 100: true },
    },
  },
});
