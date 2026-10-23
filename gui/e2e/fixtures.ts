import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { delimiter, join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { test as base, expect, type TestInfo } from "@playwright/test";

const EXAMPLES = fileURLToPath(new URL("../../examples/", import.meta.url));
const GENERATE_PROJECT = fileURLToPath(new URL("../../tools/generate_project.py", import.meta.url));

/** An example the journeys serve a copy of: its directory under examples/, and its project. */
interface Example {
  directory: string;
  project: string;
  /** Directories of examples/ that its project names by a path beside its own directory, such as
   * the `../plugins/ddd_layout.py` of `LAYOUT`: copied beside the copy, so that the path resolves
   * there. Only `copiedGui` honours it: `started` and `mappedGui`, which serve an example as it
   * stands, copy the example's own directory alone. */
  beside?: readonly string[];
}

const DEMO: Example = { directory: "demo", project: "demo.ddd.json" };
/** The example with a units file, which part 2's journeys rename and describe units in. */
const VOCABULARY: Example = { directory: "vocabulary", project: "project.ddd.json" };
/** The example with all three kinds of type, which part 6's journeys change. */
const STRUCTURES: Example = { directory: "structures", project: "project.ddd.json" };
/** The one example whose project loads a plugin - examples/plugins/ddd_layout.py, by a path beside
 * its own directory - and so the one in which a plugin's own rules file findings. */
const LAYOUT: Example = { directory: "layout", project: "project.ddd.json", beside: ["plugins"] };

export interface Gui {
  /** The address ddd gui printed, token included. */
  address: string;
  /** The directory the server is started in and edits: a copy of an example, or the project
   * `generatedGui` or `chainedGui` generates, under this test's own output directory - or, for
   * `mappedGui`, a copy of the demo in a fresh directory on the drive `DDD_MAPPED_DRIVE` names. */
  directory: string;
  /** Stops the server; stopping twice is harmless. */
  stop: () => Promise<void>;
}

/** The examples a copy can be made of, by the name `copiedGui` takes. */
const EXAMPLES_BY_NAME = {
  demo: DEMO,
  vocabulary: VOCABULARY,
  structures: STRUCTURES,
  layout: LAYOUT,
} as const;

/** Serves a copy of an example changed before `ddd gui` starts, for a state no example has as it
 * stands: no project at all, no dictionary, a build record not used (spec 2026-10-08 §5).
 * `change` is awaited before the server starts. The copy is under the test's own output
 * directory, as `started` makes one, numbered as it is asked for, so that no two copies of one
 * test share a directory; the project is named unless `named` is `false`. A copy of an example
 * that names files beside its own directory (`layout`) is made in a directory of its own name
 * inside the numbered one, with those files copied beside it, so that they are no more shared
 * than the copy is. Every server it starts is stopped when the test ends, one still starting
 * then included. */
export type CopiedGui = (
  example: keyof typeof EXAMPLES_BY_NAME,
  change: (directory: string) => void | Promise<void>,
  options?: { named?: boolean },
) => Promise<Gui>;

/**
 * `generatedGui`'s project: 20,000 declarations, "every output without an id and half the
 * inputs unread" (part 17's task 12's own brief): large enough that the analysis an edit starts
 * runs long enough for a reader to see the heading read "Updating the findings…" rather than turn
 * back before a reader's eye catches it - and findings enough, 25,000 of them, that the Findings
 * tab's table is a window rather than a page's worth of rows (its tasks 7 and 9).
 */
const MANY: readonly string[] = [
  "--declarations",
  "20000",
  "--shape",
  "many",
  "--missing-ids",
  "1",
  "--unread",
  "0.5",
];

/**
 * `chainedGui`'s project: 4,000 declarations in the `chain` shape, 2,000 components each reading
 * the next one's output and the last reading the first's, a cycle the canvas's layout breaks into
 * one chain 2,000 deep. dagre overflows its stack in the layout worker on a chain that deep, and
 * the canvas is laid out in ranks only (`ranked`'s doc, gui/src/lib/layout.ts). In Chrome on the
 * Linux development PC a chain of 907 components laid out in full and one of 908 in ranks only,
 * four times each, at 110accb: 2,000 is more than twice that, the room left for the Windows legs,
 * where no one has measured it. Never `--unread`: it turns inputs into outputs, and the chain
 * would break where it did.
 */
const CHAIN: readonly string[] = ["--declarations", "4000", "--shape", "chain"];

/**
 * `tools/generate_project.py DIRECTORY` with `options` through `DDD_PYTHON`, into `directory`,
 * which must not exist yet - the way `demo.ts`'s own `dump` runs `ddd dump` (part 17's task 1):
 * `generatedGui`'s project unless told otherwise.
 */
function generated(directory: string, options: readonly string[] = MANY): void {
  const result = spawnSync(
    process.env.DDD_PYTHON ?? "python",
    [GENERATE_PROJECT, directory, ...options],
    // A minute is far more than the ~0.15 s either project takes (measured): long enough that a
    // real run never trips it, short enough that an interpreter stuck for some other reason does
    // not hang the whole suite behind one fixture.
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
      `generate_project.py ${directory} ${options.join(" ")} exited with ` +
        `${String(result.status)}: ${result.stderr.toString("utf8")}`,
    );
  }
}

/** A fresh copy of `example` made in `parent`, with whatever its project names beside its own
 * directory copied beside it. Answers the copy's directory: `parent` itself, or - where something
 * is to lie beside it - the directory of `parent` named for the example, so that the two lie side
 * by side in a `parent` no other copy shares. */
function copiedExample(example: Example, parent: string): string {
  const beside = example.beside ?? [];
  const directory = beside.length === 0 ? parent : join(parent, example.directory);
  cpSync(join(EXAMPLES, example.directory), directory, { recursive: true });
  for (const name of beside) {
    cpSync(join(EXAMPLES, name), join(parent, name), { recursive: true });
  }
  return directory;
}

/** A stand-in for the browser `ddd gui` opens: a program that writes the address it is opened
 * with to a file beside it, and a function answering that address once it is there. A shell
 * script, or on Windows a batch file. `webbrowser` splits `BROWSER` at `os.pathsep` - Node's
 * `path.delimiter`, `:` or on Windows `;` - and runs an entry with no `%s` in it whole, as one
 * program handed the address as its one argument (`GenericBrowser`): so the program's path may
 * hold no such separator. It may hold a space, though no CI run has had one, so a batch file
 * reached through such a path is untested. A batch file reads the address as `%*`, since cmd
 * splits `%1` at the `=` of `?code=`. */
function recorder(directory: string): { program: string; opened: () => Promise<string> } {
  mkdirSync(directory, { recursive: true });
  const file = join(directory, "opened.txt");
  const program = join(directory, process.platform === "win32" ? "record.cmd" : "record.sh");
  if (program.includes(delimiter)) {
    throw new Error(`webbrowser cannot run ${program}: it splits BROWSER at ${delimiter}`);
  }
  if (process.platform === "win32") {
    writeFileSync(program, '@echo off\r\n>"%~dp0opened.txt" echo %*\r\n');
  } else {
    writeFileSync(program, '#!/bin/sh\nprintf \'%s\' "$1" > "$(dirname "$0")/opened.txt"\n', {
      mode: 0o755,
    });
  }
  const opened = async () => {
    // `launched` runs on a thread of its own once the address is printed (server.py's `run`).
    await expect
      .poll(
        () => {
          try {
            return existsSync(file) && readFileSync(file, "utf8").trim() !== "";
          } catch {
            // Refused while the program still holds the file - EBUSY on Windows, say, while
            // cmd.exe holds its redirect: no answer yet, so asked again, never the poll's end.
            return false;
          }
        },
        {
          message: `the address ddd gui opened its browser on, written to ${file}`,
          timeout: 10_000,
        },
      )
      .toBe(true);
    return readFileSync(file, "utf8").trim();
  };
  return { program, opened };
}

/** `ddd gui` with the browser it opens itself, for the sign-in no other journey sees: every
 * other server is started with `--no-browser`. */
export type OpenedGui = Gui & { opened: () => Promise<string> };

/** What else `start` is told: `browser`, a program `ddd gui` opens its browser with, through the
 * `BROWSER` variable Python's `webbrowser` reads, in place of `--no-browser`. */
interface StartOptions {
  browser?: string;
}

/** How long `ddd gui` may take to print its address (`served`): it prints it within a second or
 * two of starting on every leg, and a journey that waited longer would only wait out its own
 * timeout, its teardown then waiting on the start another (P19c-16). */
const ADDRESS_WAIT_MS = 20_000;

/** How long its first analysis may take to land once the address is printed (`analysed`), well
 * past the generated projects' few seconds, for the same reason. */
const ANALYSIS_WAIT_MS = 30_000;

/** `ddd gui` over `directory`, already prepared, naming `project` on the command line or opening
 * on the start page where it is empty; stopped by the `Gui`'s own `stop`. The shared head of
 * `serving` and `copiedGui`. */
async function start(
  directory: string,
  project: readonly string[],
  options: StartOptions = {},
): Promise<Gui> {
  // python -m ddd rather than the ddd launcher: on Windows the launcher starts python as a child
  // of its own, which killing the launcher leaves running, holding the port and the copy.
  const child = spawn(
    process.env.DDD_PYTHON ?? "python",
    ["-m", "ddd", "gui", ...project, ...(options.browser === undefined ? ["--no-browser"] : [])],
    {
      cwd: directory,
      // Its stderr piped rather than inherited, and passed on line by line (`served`).
      stdio: ["ignore", "pipe", "pipe"],
      ...(options.browser === undefined
        ? {}
        : { env: { ...process.env, BROWSER: options.browser } }),
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
  // Bounded, as `served` is, so that an analysis that never lands fails the journey saying so.
  const deadline = Date.now() + ANALYSIS_WAIT_MS;
  let after: number | null = null;
  for (;;) {
    const asked = new URL(after === null ? "/api/state" : `/api/state?after=${after}`, address);
    const signal = AbortSignal.timeout(Math.max(deadline - Date.now(), 0));
    let state: { version: number; revision: number; analysing: boolean };
    try {
      const response = await fetch(asked, { headers, signal });
      // Refused - signed out, or no project open - it would be refused again at every ask, and
      // the journey would wait out its own timeout saying nothing of why.
      if (response.status !== 200) {
        throw new Error(
          `ddd gui answered ${response.status} to ${asked.pathname}: ${await response.text()}`,
        );
      }
      state = (await response.json()) as typeof state;
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "TimeoutError")) throw error;
      throw new Error(
        `ddd gui at ${new URL(address).origin} had not finished its first analysis ` +
          `${ANALYSIS_WAIT_MS / 1000} s after printing its address`,
      );
    }
    if (state.revision > 0 && !state.analysing) return;
    after = state.version;
  }
}

/**
 * The address `ddd gui` prints on its stdout once it serves (pytest pins the stream). Its stderr is
 * read too, each line passed on as it was when stderr was inherited, so that an address that
 * never comes is an error naming what each stream gave, rather than a journey waiting out its
 * timeout and its teardown another. That is how a project naming a plugin met it on Windows: a
 * plugin's hook ran with stdout bound to stderr for the whole process as the address was printed,
 * which `run` (server.py) now guards against (P19c-18).
 */
function served(child: ChildProcess): Promise<string> {
  return new Promise((resolve, reject) => {
    if (child.stdout === null || child.stderr === null) {
      reject(new Error("ddd gui has no stdout or no stderr to read"));
      return;
    }
    const streams = { stdout: child.stdout, stderr: child.stderr };
    const seen: Record<"stdout" | "stderr", string[]> = { stdout: [], stderr: [] };
    let waiting = true;
    const settle = (settled: () => void) => {
      if (!waiting) return;
      waiting = false;
      clearTimeout(timer);
      settled();
    };
    const timer = setTimeout(() => {
      settle(() =>
        reject(
          new Error(
            `ddd gui (pid ${child.pid}) printed no address within ${ADDRESS_WAIT_MS / 1000} s: ` +
              `its stdout gave ${JSON.stringify(seen.stdout)}, ` +
              `its stderr ${JSON.stringify(seen.stderr)}`,
          ),
        ),
      );
    }, ADDRESS_WAIT_MS);
    for (const name of ["stdout", "stderr"] as const) {
      createInterface({ input: streams[name] }).on("line", (line) => {
        if (waiting) seen[name].push(line);
        if (name === "stderr") {
          process.stderr.write(`${line}\n`);
          return;
        }
        const address = /serving (\S+)/.exec(line)?.[1];
        if (address !== undefined) settle(() => resolve(address));
      });
    }
    child.once("exit", (code) =>
      settle(() => reject(new Error(`ddd gui exited with ${code} before serving`))),
    );
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
  chainedGui: Gui;
  mappedGui: Gui;
  copiedGui: CopiedGui;
  openedGui: OpenedGui;
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
  chainedGui: async ({}, use, testInfo) => {
    const directory = testInfo.outputPath("chained");
    generated(directory, CHAIN);
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
  openedGui: async ({}, use, testInfo) => {
    const directory = testInfo.outputPath(DEMO.directory);
    cpSync(join(EXAMPLES, DEMO.directory), directory, { recursive: true });
    const browser = recorder(testInfo.outputPath("browser"));
    const gui = await start(directory, [join(directory, DEMO.project)], {
      browser: browser.program,
    });
    try {
      await use({ ...gui, opened: browser.opened });
    } finally {
      await gui.stop();
    }
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
        const numbered = testInfo.outputPath(`${example.directory}-${copies}`);
        copies += 1;
        const directory = copiedExample(example, numbered);
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
