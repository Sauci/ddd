import { type ChildProcess, spawn } from "node:child_process";
import { cpSync } from "node:fs";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { test as base, type TestInfo } from "@playwright/test";

const EXAMPLES = fileURLToPath(new URL("../../examples/", import.meta.url));

/** An example the journeys serve a copy of: its directory under examples/, and its project. */
interface Example {
  directory: string;
  project: string;
}

const DEMO: Example = { directory: "demo", project: "demo.ddd.json" };
/** The example with a units file, which part 2's journeys rename and describe units in. */
const VOCABULARY: Example = { directory: "vocabulary", project: "project.ddd.json" };

export interface Gui {
  /** The address ddd gui printed, token included. */
  address: string;
  /** The copy of the example the server edits, under this test's own output directory. */
  directory: string;
  /** Stops the server; stopping twice is harmless. */
  stop: () => Promise<void>;
}

/** `ddd gui` over a fresh copy of an example, with its project named or not. */
async function started(
  example: Example,
  named: boolean,
  use: (gui: Gui) => Promise<void>,
  testInfo: TestInfo,
): Promise<void> {
  // Under test-results/, which Playwright empties at the start of every run: a failed journey
  // then keeps its copy beside its trace, and nothing here has to remove it.
  const directory = testInfo.outputPath(example.directory);
  cpSync(join(EXAMPLES, example.directory), directory, { recursive: true });
  const project = named ? [join(directory, example.project)] : [];
  // python -m ddd rather than the ddd launcher: on Windows the launcher starts python as a child
  // of its own, which killing the launcher leaves running, holding the port and the copy.
  const child = spawn(
    process.env.DDD_PYTHON ?? "python",
    ["-m", "ddd", "gui", ...project, "--no-browser"],
    {
      cwd: directory,
      stdio: ["ignore", "pipe", "inherit"],
    },
  );
  let stopped = false;
  const stop = async () => {
    if (!stopped) {
      stopped = true;
      await terminated(child);
    }
  };
  try {
    await use({ address: await served(child), directory, stop });
  } finally {
    await stop();
  }
}

function served(child: ChildProcess): Promise<string> {
  return new Promise((resolve, reject) => {
    if (child.stdout === null) {
      reject(new Error("ddd gui has no stdout"));
      return;
    }
    createInterface({ input: child.stdout }).on("line", (line) => {
      const found = /serving (\S+)/.exec(line);
      if (found?.[1] !== undefined) resolve(found[1]);
    });
    child.once("exit", (code) => reject(new Error(`ddd gui exited with ${code} before serving`)));
  });
}

function terminated(child: ChildProcess): Promise<void> {
  return new Promise((resolve) => {
    if (child.exitCode !== null || child.signalCode !== null) {
      resolve();
      return;
    }
    child.once("exit", () => resolve());
    child.kill();
  });
}

export const test = base.extend<{ gui: Gui; bareGui: Gui; vocabularyGui: Gui }>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  gui: async ({}, use, testInfo) => started(DEMO, true, use, testInfo),
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  bareGui: async ({}, use, testInfo) => started(DEMO, false, use, testInfo),
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  vocabularyGui: async ({}, use, testInfo) => started(VOCABULARY, true, use, testInfo),
});

export { expect } from "@playwright/test";
