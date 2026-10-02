import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { cpSync } from "node:fs";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { test as base, type TestInfo } from "@playwright/test";

const EXAMPLES = fileURLToPath(new URL("../../examples/", import.meta.url));
const GENERATE_PROJECT = fileURLToPath(new URL("../../tools/generate_project.py", import.meta.url));

/** An example the journeys serve a copy of: its directory under examples/, and its project. */
interface Example {
  directory: string;
  project: string;
}

const DEMO: Example = { directory: "demo", project: "demo.ddd.json" };
/** The example with a units file, which part 2's journeys rename and describe units in. */
const VOCABULARY: Example = { directory: "vocabulary", project: "project.ddd.json" };
/** The example with all three kinds of type, which part 6's journeys change. */
const STRUCTURES: Example = { directory: "structures", project: "project.ddd.json" };

export interface Gui {
  /** The address ddd gui printed, token included. */
  address: string;
  /** The copy of the example the server edits, under this test's own output directory. */
  directory: string;
  /** Stops the server; stopping twice is harmless. */
  stop: () => Promise<void>;
}

/**
 * `tools/generate_project.py DIRECTORY --declarations 20000 --shape many --missing-ids 1
 * --unread 0.5` through `DDD_PYTHON`, into `directory`, which must not exist yet - the way
 * `demo.ts`'s own `dump` runs `ddd dump` (part 17's task 1). 20,000 declarations, "every output
 * without an id and half the inputs unread" (task 12's own brief): large enough that an analysis
 * of it lasts long enough for a reader to see "Updating the findings…" rather than a flash
 * between two frames - measured on the Linux development PC, in process over a running session,
 * one declaration's unit changed: the edit answered in 3 ms and the analysis that followed it
 * landed about 760 ms later - and findings enough, 25,000 of them, that the Findings tab's table
 * is a window rather than a page's worth of rows (tasks 7 and 9).
 */
function generated(directory: string): void {
  const result = spawnSync(
    process.env.DDD_PYTHON ?? "python",
    [
      GENERATE_PROJECT,
      directory,
      "--declarations",
      "20000",
      "--shape",
      "many",
      "--missing-ids",
      "1",
      "--unread",
      "0.5",
    ],
    // A minute is far more than the ~0.15 s this takes (measured): long enough that a real run
    // never trips it, short enough that an interpreter stuck for some other reason does not
    // hang the whole suite behind one fixture.
    { timeout: 60_000 },
  );
  // Spawning itself can fail - the interpreter named is not there at all - before there is any
  // status, signal or stderr to read; `result.error` is the only field set then, and reading
  // `result.stderr` as though it were one throws "Cannot read properties of undefined", losing
  // the ENOENT under a different error entirely.
  if (result.error) {
    throw new Error(
      `generate_project.py ${directory} could not be started: ${result.error.message}`,
    );
  }
  // A timeout, or a signal from elsewhere, ends the process without a status - `status` is then
  // `null`, and naming it would print "exited with null", true of every signal alike.
  if (result.signal !== null) {
    throw new Error(`generate_project.py ${directory} was killed by ${result.signal}`);
  }
  if (result.status !== 0) {
    throw new Error(
      `generate_project.py ${directory} --declarations 20000 --shape many --missing-ids 1 ` +
        `--unread 0.5 exited with ${String(result.status)}: ${result.stderr.toString("utf8")}`,
    );
  }
}

/** `ddd gui` over `directory`, already prepared, naming `project` on the command line or opening
 * on the start page where it is empty - the shared tail of `started` and `generatedGui`, which
 * prepare `directory` two different ways (a copied example; a generated project) and otherwise
 * start the very same server the very same way. */
async function serving(
  directory: string,
  project: readonly string[],
  use: (gui: Gui) => Promise<void>,
): Promise<void> {
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
    const address = await served(child);
    if (project.length > 0) await analysed(address);
    await use({ address, directory, stop });
  } finally {
    await stop();
  }
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
  await serving(directory, named ? [join(directory, example.project)] : [], use);
}

/**
 * Resolves once `ddd gui` has analysed the project it was named, which is what a journey changing
 * a file "from outside" means: a file the server has read. It prints its address before its first
 * analysis lands, and a file written in that moment is read by the first analysis or by the one
 * after, as it happens - the two drifts of one journey were once split between them, its arrow
 * then naming one disagreement where the journey made two. Asked of the state the page itself
 * follows, signed in with the address's own token, and never of anything a journey reads.
 */
async function analysed(address: string): Promise<void> {
  const signedIn = await fetch(address, { redirect: "manual" });
  const [cookie] = signedIn.headers.getSetCookie();
  if (cookie === undefined) throw new Error("ddd gui set no cookie for the address it printed");
  const headers = { cookie: cookie.split(";", 1)[0] ?? cookie };
  let after: number | null = null;
  for (;;) {
    const asked = new URL(after === null ? "/api/state" : `/api/state?after=${after}`, address);
    const response = await fetch(asked, { headers });
    // Refused - signed out, or no project open - it would be refused again at every ask, and the
    // journey would wait out its own timeout saying nothing of why.
    if (response.status !== 200) {
      throw new Error(
        `ddd gui answered ${response.status} to ${asked.pathname}: ${await response.text()}`,
      );
    }
    const state = (await response.json()) as {
      version: number;
      revision: number;
      analysing: boolean;
    };
    if (state.revision > 0 && !state.analysing) return;
    after = state.version;
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

export const test = base.extend<{
  gui: Gui;
  bareGui: Gui;
  vocabularyGui: Gui;
  structuresGui: Gui;
  generatedGui: Gui;
}>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  gui: async ({}, use, testInfo) => started(DEMO, true, use, testInfo),
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  bareGui: async ({}, use, testInfo) => started(DEMO, false, use, testInfo),
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  vocabularyGui: async ({}, use, testInfo) => started(VOCABULARY, true, use, testInfo),
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  structuresGui: async ({}, use, testInfo) => started(STRUCTURES, true, use, testInfo),
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  generatedGui: async ({}, use, testInfo) => {
    const directory = testInfo.outputPath("generated");
    generated(directory);
    await serving(directory, [join(directory, "project.ddd.json")], use);
  },
});

export { expect } from "@playwright/test";
