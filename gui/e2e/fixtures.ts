import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { cpSync, mkdtempSync } from "node:fs";
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
  /** The directory the server is started in and edits: a copy of an example, or the project
   * `generatedGui` generates, under this test's own output directory - or, for `mappedGui`, a
   * copy of the demo in a fresh directory on the drive `DDD_MAPPED_DRIVE` names. */
  directory: string;
  /** Stops the server; stopping twice is harmless. */
  stop: () => Promise<void>;
}

/** The examples a copy can be made of, by the name `copiedGui` takes. */
const EXAMPLES_BY_NAME = { demo: DEMO, vocabulary: VOCABULARY, structures: STRUCTURES } as const;

/** Serves a copy of an example changed before `ddd gui` starts, for a state no example has as it
 * stands: no project at all, no dictionary, a build record not used (spec 2026-10-08 §5).
 * `change` is awaited before the server starts. The copy is under the test's own output
 * directory, as `started` makes one, numbered as it is asked for, so that no two copies of one
 * test share a directory; the project is named unless `named` is `false`. Every server it
 * starts is stopped when the test ends, one still starting then included. */
export type CopiedGui = (
  example: keyof typeof EXAMPLES_BY_NAME,
  change: (directory: string) => void | Promise<void>,
  options?: { named?: boolean },
) => Promise<Gui>;

/**
 * `tools/generate_project.py DIRECTORY --declarations 20000 --shape many --missing-ids 1
 * --unread 0.5` through `DDD_PYTHON`, into `directory`, which must not exist yet - the way
 * `demo.ts`'s own `dump` runs `ddd dump` (part 17's task 1). 20,000 declarations, "every output
 * without an id and half the inputs unread" (task 12's own brief): large enough that the
 * analysis an edit starts runs long enough for a reader to see the heading read "Updating the
 * findings…" rather than turn back before a reader's eye catches it - and findings enough,
 * 25,000 of them, that the Findings tab's table is a window rather than a page's worth of rows
 * (tasks 7 and 9).
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
  // The timeout above kills the process on expiry and sets *both* `result.error` (`code:
  // "ETIMEDOUT"`) and `result.signal` - checked first, ahead of the plainer spawn failure below,
  // or a run merely slow would be misread as the interpreter never starting at all.
  if (result.error && (result.error as NodeJS.ErrnoException).code === "ETIMEDOUT") {
    throw new Error(`generate_project.py ${directory} did not finish within 60 s`);
  }
  // Spawning itself can otherwise fail - the interpreter named is not there at all - before
  // there is any status, signal or stderr to read; `result.error` is the only field set then
  // (with no signal, unlike the timeout above), and reading `result.stderr` as though it were
  // one throws "Cannot read properties of undefined", losing the ENOENT under a different error
  // entirely.
  if (result.error) {
    throw new Error(
      `generate_project.py ${directory} could not be started: ${result.error.message}`,
    );
  }
  // A signal from elsewhere - not the timeout above, already reported - ends the process without
  // a status - `status` is then `null`, and naming it would print "exited with null", true of
  // every signal alike.
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
 * on the start page where it is empty; stopped by the `Gui`'s own `stop`. The shared head of
 * `serving` and `copiedGui`. */
async function start(directory: string, project: readonly string[]): Promise<Gui> {
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
    return { address, directory, stop };
  } catch (error) {
    await stop();
    throw error;
  }
}

/** `ddd gui` over `directory`, handed to `use` and stopped after it whatever it did. */
async function serving(
  directory: string,
  project: readonly string[],
  use: (gui: Gui) => Promise<void>,
): Promise<void> {
  const gui = await start(directory, project);
  try {
    await use(gui);
  } finally {
    await gui.stop();
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
 *
 * Past every analysis opening makes: on examples/demo, two - its sub-project's own
 * event_logger.ddd.json has no stamp before the first reads it, and the revision the first
 * publishes asks for the second (`_finished`, session.py). The server's first poll used to ask
 * for it instead, and the state saying so came 952 to 1036 ms after this resolved, asked as this
 * asks, in 20 starts on the Linux development PC - about a second into the journey. A press made
 * then, on Apply or Show changes, went down on the button and came up off it - above it, once
 * "Updating the findings…" had moved it down a line, or where it had been, withdrawn while its
 * plan was asked for again for the new revision - and was lost, the journey waiting out its
 * timeout for what the press never asked for.
 */
async function analysed(address: string): Promise<void> {
  // The token the printed address carries, sent as the page sends it. Nothing sets a cookie
  // any more (part 18b).
  const token = new URL(address).searchParams.get("token");
  if (token === null) throw new Error(`ddd gui printed an address with no token: ${address}`);
  const headers = { authorization: `Bearer ${token}` };
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
  mappedGui: Gui;
  copiedGui: CopiedGui;
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
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  mappedGui: async ({}, use, testInfo) => {
    const drive = process.env.DDD_MAPPED_DRIVE;
    if (drive === undefined) {
      throw new Error("mappedGui serves a mapped drive, which DDD_MAPPED_DRIVE must name");
    }
    // A directory of the test's own on the drive, as `started` makes one under test-results -
    // but a fresh one each run: nothing empties the drive as Playwright empties test-results, and
    // the test's id is the same from one run to the next, so a run by hand on a drive kept
    // would otherwise find the file an earlier run created there.
    const directory = join(
      mkdtempSync(join(`${drive}\\`, `ddd-${testInfo.testId}-`)),
      DEMO.directory,
    );
    cpSync(join(EXAMPLES, DEMO.directory), directory, { recursive: true });
    await serving(directory, [join(directory, DEMO.project)], use);
  },
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  copiedGui: async ({}, use, testInfo) => {
    // Every start, kept as it begins: one still starting when the test ends is stopped too.
    const starts: Promise<Gui>[] = [];
    let copies = 0;
    let ended = false;
    try {
      await use(async (name, change, options) => {
        const example = EXAMPLES_BY_NAME[name];
        // Numbered before anything is awaited, so two calls in flight never share a directory.
        const directory = testInfo.outputPath(`${example.directory}-${copies}`);
        copies += 1;
        cpSync(join(EXAMPLES, example.directory), directory, { recursive: true });
        await change(directory);
        // A change still running when the test ended starts nothing: nothing would stop it.
        if (ended) throw new Error(`the test ended before ${directory} was served`);
        const named = options?.named ?? true;
        const begun = start(directory, named ? [join(directory, example.project)] : []);
        starts.push(begun);
        return begun;
      });
    } finally {
      ended = true;
      // `start` stops a server whose start fails; every one that started is stopped here.
      for (const outcome of await Promise.allSettled(starts)) {
        if (outcome.status === "fulfilled") await outcome.value.stop();
      }
    }
  },
});

export { expect } from "@playwright/test";
