// Ladle, the workbench for the widgets: every *.stories.tsx under src, built into ladle-build/,
// which the screenshot tests photograph. Its own Vite configuration, not the pages' - Ladle runs
// a Vite a major version behind theirs, and that configuration builds into the Python package.
/** @type {import('@ladle/react').UserConfig} */
export default {
  stories: "src/**/*.stories.tsx",
  outDir: "ladle-build",
  viteConfig: ".ladle/vite.config.ts",
};
