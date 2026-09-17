import { type ChildProcess, spawn } from "node:child_process";
import { cpSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { test as base } from "@playwright/test";

const DEMO = fileURLToPath(new URL("../../examples/demo/", import.meta.url));

export interface Gui {
  /** The address ddd gui printed, token included. */
  address: string;
  /** The temporary copy of examples/demo the server edits. */
  directory: string;
  /** Stops the server; stopping twice is harmless. */
  stop: () => Promise<void>;
}

/** `ddd gui` over a fresh copy of the demo, with the project named or not. */
async function started(named: boolean, use: (gui: Gui) => Promise<void>): Promise<void> {
  const directory = mkdtempSync(join(tmpdir(), "ddd-gui-e2e-"));
  cpSync(DEMO, directory, { recursive: true });
  const project = named ? [join(directory, "demo.ddd.json")] : [];
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
    removeCopy(directory);
  }
}

/**
 * Windows can hold a file of the just-killed server's working directory locked for anywhere
 * from nothing up to several minutes past the point where Node considers it exited (observed
 * with antivirus scanning enabled); retrying cannot be relied on to bridge that within a test's
 * timeout. A copy still locked once the retries above are exhausted is left for the OS's own
 * temporary-directory cleanup rather than failing a journey whose assertions already ran.
 */
function removeCopy(directory: string): void {
  try {
    rmSync(directory, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
  } catch {
    // best-effort: see the comment above.
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

export const test = base.extend<{ gui: Gui; bareGui: Gui }>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  gui: async ({}, use) => started(true, use),
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  bareGui: async ({}, use) => started(false, use),
});

export { expect } from "@playwright/test";
