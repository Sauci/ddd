/**
 * The page half of the benchmark of `ddd gui` on large generated projects (design doc §4): a
 * Playwright script against a running server, timing what a reader sees - the shell answering,
 * the first drawn screen, each tab's own first row, typing, scrolling, an Apply's own change
 * showing and the findings catching up to it - rather than any one request (`tools/bench_gui.py`
 * is the server half, in process). Run by hand only (`playwright.bench.config.ts` says why), on
 * the projects `tools/generate_project.py` writes under `$BENCH` (Task 1) - this file never
 * imports that generator, so it learns a project's shape from the page alone, the way a reader
 * would.
 *
 * `DDD_BENCH_PROJECT` names one project's `project.ddd.json`; `ddd gui` is started over its
 * directory the way `gui/e2e/fixtures.ts` starts it, but without naming the project, so the
 * first measure starts exactly where a reader's own visit does - the start page, one button
 * press from the project it opens. `DDD_BENCH_OUT`, when set, is where every row is also
 * appended as `| project | measure | ms |`; every row is printed regardless (`npm run bench`).
 *
 * Every measure is capped at `CAP_MS`: `capped()` and `elapsedCapped()` race the page against a
 * plain timer, so a measure that has not finished by then is reported `> 120000` and abandoned -
 * never awaited further, and never failing the test - rather than one stuck page holding up the
 * rest of the run. A renderer crash settles sooner than that and is reported as its own word,
 * `crashed` (`formatMs`'s own doc), never folded into `> 120000`: the design doc's own measurement
 * already named the Findings tab as likely to run past the cap by itself (it froze the page for
 * more than two minutes at 36,000 findings-heavy declarations), and validating this script found
 * opening it can go further still - crashing the renderer outright at 35,000 declarations,
 * confirmed by the crash's own error text (`isPageCrash`'s own doc) and settling in fifteen to
 * twenty seconds there, nowhere near the cap. The graph is a second place this script needed to
 * treat as no longer answering: every run measured here found `answering`, `first screen` and
 * every other measure's own setup capped - the plain `> 120000`, not a crash - at 100,000
 * declarations, and the one project where `answering` itself stayed fast (`100000-many-heavy`,
 * 5.0 s) still capped on `first screen`'s own further wait for a module node, the same click
 * otherwise unchanged (`openProject`'s own doc has the full account); the direct culprit was not
 * separately isolated, but the graph is what stands between those two waits. `scrolling`
 * additionally caps opening the Findings tab separately from scrolling it, so the two capped waits
 * together still fit inside one test's own budget (300,000 ms, below). Every measure's own setup
 * beyond opening the project - a component's declarations, one endpoint's own answer - stayed at a
 * few seconds at every size the design doc measured, so it is simply awaited, generously but
 * plainly, and a genuine failure there still fails the test loudly rather than being read as
 * "slow" (Step 3's own purpose: a measure that caps or reads 0 ms on a small project is this
 * script's fault, not the page's).
 */
import { spawn } from "node:child_process";
import { appendFileSync, existsSync, statSync } from "node:fs";
import { basename, dirname } from "node:path";
import { createInterface } from "node:readline";
import { test as base, chromium, expect, type Locator, type Page } from "@playwright/test";

/**
 * `test`, with its `page` fixture backed by a fresh *browser* for every test - a whole new Chrome
 * process, not only a fresh page and context from the one browser Playwright would otherwise
 * launch once for the whole file and share between every test in it. Playwright's own `browser`
 * fixture is worker-scoped and cannot be overridden to a narrower one (confirmed empirically: `tsc`
 * refuses a `{ scope: "test" }` override of it, and without that override the launch this file
 * asked for was still made once, before the first test, for all of them to share) - so this
 * bypasses `browser` and `context` entirely and builds `page` itself.
 *
 * Confirmed while validating this script: the default, shared browser left a *later*, unrelated
 * test unable even to click the start page's own project button - "element is not stable...
 * detached from the DOM, retrying", for the whole of the 300,000 ms test timeout - after an
 * earlier test's graph of 3,333 module nodes left that one shared browser labouring, even though
 * the earlier test had itself already finished, gracefully capped rather than crashed. One
 * struggling page can this way cost a later, unrelated one its own reading, which the file's own
 * top doc "so a tab that froze in one test does not freeze the next" already promises against - a
 * promise `capped()` alone cannot keep, since it says nothing about what a test leaves behind in a
 * browser other tests still share.
 *
 * Torn down with `launchServer`'s own `kill()` (documented to terminate the process and wait for
 * its exit), not the plain `browser.close()` a `launch()`-ed browser offers: a `capped()` measure
 * has already decided to stop waiting on a page that may still be labouring - graceful shutdown
 * asks that same page to co-operate, which is the one thing it has already shown it may not do
 * for a long while. A fresh launch and kill together still cost at most a second or two, against
 * measures already capped at 120,000 ms.
 */
const test = base.extend<{ page: Page }>({
  // biome-ignore lint/correctness/noEmptyPattern: Playwright reads a fixture's dependencies from this pattern
  page: async ({}, use) => {
    const server = await chromium.launchServer(
      process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {},
    );
    try {
      const browser = await chromium.connect(server.wsEndpoint());
      // The same viewport playwright.bench.config.ts's own `use` sets - read straight here,
      // since this page is never built from that config's own `use` block the way the default
      // fixture's is (config's own comment: fixed, so every run draws the same number of rows at
      // the same size).
      const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
      await use(page);
    } finally {
      await server.kill();
    }
  },
});

/** Never waited past, for any one measure. */
const CAP_MS = 120_000;

/** Every `expect(...).toBeVisible()`-style wait in this file passes this, `capped()`'s own timer
 * included: longer than `CAP_MS`, so that timer always wins the race and reports `CAPPED` first,
 * this is a safety net an ordinary run never actually needs (nowhere near this slow at any size
 * the design doc measured, the Findings tab and the graph included - both still settle, merely
 * slowly, within `CAP_MS` far more often than not) - yet still short enough beside `CAP_MS` that
 * stacking one of each still fits inside a test's own 300,000 ms budget (below). */
const LONG_TIMEOUT = 180_000;

/** What `capped()` returns for an action that had not settled by `CAP_MS`. */
const CAPPED = Symbol("capped");
/** What `capped()` returns for an action that settled early because the renderer crashed
 * (`isPageCrash`) - a genuinely different outcome from `CAPPED`, reported as a different word
 * (`formatMs`'s own doc): the measure finished, just not the way a reader waiting for it would
 * call finishing. */
const CRASHED = Symbol("crashed");
type Capped<T> = T | typeof CAPPED | typeof CRASHED;

/** True for a `capped()` result that is not a real value - `CAPPED` and `CRASHED` are two quite
 * different ends of a wait (`formatMs`'s own doc), but mean the same thing to a caller only
 * deciding whether it has anything left to act on. */
function didNotFinish(value: unknown): value is typeof CAPPED | typeof CRASHED {
  return value === CAPPED || value === CRASHED;
}

/** True for an error that means the page's own renderer is gone, rather than a mistake in this
 * file's own selectors (which should still fail the test loudly - Step 3's own purpose). Confirmed
 * while validating this script, not merely theorised from the design doc's own "froze the page for
 * more than two minutes" (§2): opening the Findings tab of a findings-heavy 35,000-declaration
 * project crashed the renderer outright (`Protocol error (Runtime.callFunctionOn): Page crashed.`,
 * inside sixteen seconds), rendering tens of thousands of rows in one unvirtualised table (Task 9
 * gives it a virtualised one). The graph draws just as unvirtualised a DOM at 100,000 declarations
 * - one node per component, spec §6's own future budget for it is to draw only the nodes in view -
 * but every run measured here found that a genuine freeze rather than a second crash: capped at
 * `CAP_MS` every time, never this function's own `/crash/i` text (`openProject`'s own doc has that
 * finding, since it is what made opening the project itself - not only the Findings tab - need
 * capping too). */
function isPageCrash(error: unknown): boolean {
  return error instanceof Error && /crash/i.test(error.message);
}

/**
 * Runs `action`, capped at `CAP_MS`: if it has not settled by then, `CAPPED` is returned and
 * `action`'s own eventual settlement - success or failure, whenever it comes - is never awaited
 * or thrown, since the next test's fresh page is what matters from here (so a tab that froze in
 * one test does not freeze the next). A renderer crash (`isPageCrash`) instead returns `CRASHED`,
 * at once rather than waiting out the rest of `CAP_MS`: there is nothing left to wait for once the
 * page itself is gone, and a crash is a different outcome from a timeout, not the same one reached
 * a different way (`formatMs`'s own doc reports the two as different words for exactly this
 * reason). A genuine failure of any other kind *before* the cap still rejects normally, surfacing a
 * script bug the way Step 3's trial run is for, rather than reading as a slow page.
 */
async function capped<T>(action: () => Promise<T>): Promise<Capped<T>> {
  const settlement: Promise<Capped<T>> = action().catch((error: unknown) => {
    if (isPageCrash(error)) return CRASHED;
    throw error;
  });
  settlement.catch(() => {});
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      settlement,
      new Promise<typeof CAPPED>((resolve) => {
        timer = setTimeout(() => resolve(CAPPED), CAP_MS);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

/** `capped()` of `action`'s own elapsed time, rather than of what it returns. */
async function elapsedCapped(action: () => Promise<void>): Promise<Capped<number>> {
  const start = Date.now();
  return capped(() => action().then(() => Date.now() - start));
}

/** The report row's own `<ms>` column: `> 120000` for a measure that had not finished by the cap,
 * `crashed` for one that finished sooner because the renderer crashed (`capped()`'s own doc says
 * why these are written as two different words rather than folded into one) - a plan reading
 * either as "took at least 120000 ms" would be reading a crashed cell's own duration wrong, since
 * a crash can settle in a small fraction of that. Otherwise the plain millisecond figure, rounded
 * - `typing` and `scrolling` read a `DOMHighResTimeStamp`, which is fractional; every other
 * measure is already a whole millisecond. */
function formatMs(value: Capped<number>): string {
  if (value === CAPPED) return `> ${CAP_MS}`;
  if (value === CRASHED) return "crashed";
  return String(Math.round(value));
}

declare global {
  interface Window {
    /** Every `longtask` entry's own duration, from the observer `installLongTaskObserver`
     * installs; reset to `[]` right before whichever action is timed against it. */
    __longTasks?: number[];
  }
}

/** Installs the `longtask` observer before the first navigation, so it is running for the page's
 * whole life - one page, one document, since this app never reloads between tabs. A long task is
 * reported only from 50 ms (what a `PerformanceObserver` for `longtask` itself enforces), so an
 * empty list - read back as `0` - means no stall reached that. */
async function installLongTaskObserver(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.__longTasks = [];
    try {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) window.__longTasks?.push(entry.duration);
      }).observe({ type: "longtask", buffered: true });
    } catch {
      // No `longtask` support: `__longTasks` stays `[]`, read back as 0 - not observed with
      // PLAYWRIGHT_CHANNEL=chrome, which every benchmark run uses (Global Constraints).
    }
  });
}

/** Clears what the observer has collected so far, so only what happens next counts. */
async function resetLongTasks(page: Page): Promise<void> {
  await page.evaluate(() => {
    window.__longTasks = [];
  });
}

/** The longest `longtask` entry seen since the last reset, or `0`. */
async function longestLongTask(page: Page): Promise<number> {
  const durations = await page.evaluate(() => window.__longTasks ?? []);
  return durations.length === 0 ? 0 : Math.max(...durations);
}

let address: string;
let stopGui: () => Promise<void>;
let projectLabel: string;

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
  const project = process.env.DDD_BENCH_PROJECT;
  if (project === undefined || !existsSync(project) || !statSync(project).isFile()) {
    throw new Error("DDD_BENCH_PROJECT names no project description");
  }
  const directory = dirname(project);
  projectLabel = basename(directory);
  const gui = startGui(directory);
  address = await gui.address;
  stopGui = gui.stop;
});

test.afterAll(async () => {
  await stopGui();
});

/**
 * Starts `ddd gui` the way `gui/e2e/fixtures.ts`'s own `started()` does - `DDD_PYTHON -m ddd gui
 * --no-browser`, `cwd` the project's own directory, the address read off the "serving ..." line
 * it prints, killed to stop it - written out again here rather than imported: that helper is a
 * Playwright *fixture*, torn down after each test, where this benchmark starts one server for
 * the whole file, in `beforeAll`/`afterAll`. Never named, unlike that helper's own `named`
 * option: this benchmark always starts on the start page, exactly where a reader who has not yet
 * chosen a project does.
 */
function startGui(directory: string): { address: Promise<string>; stop: () => Promise<void> } {
  const child = spawn(process.env.DDD_PYTHON ?? "python", ["-m", "ddd", "gui", "--no-browser"], {
    cwd: directory,
    stdio: ["ignore", "pipe", "inherit"],
  });
  const address = new Promise<string>((resolve, reject) => {
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
  let stopped = false;
  const stop = (): Promise<void> => {
    if (stopped) return Promise.resolve();
    stopped = true;
    return new Promise((resolve) => {
      if (child.exitCode !== null || child.signalCode !== null) {
        resolve();
        return;
      }
      child.once("exit", () => resolve());
      child.kill();
    });
  };
  return { address, stop };
}

/** Appends `| project | measure | ms |` to `DDD_BENCH_OUT` when it is set, and always prints
 * it. */
function record(measure: string, ms: string): void {
  const row = `| ${projectLabel} | ${measure} | ${ms} |`;
  console.log(row);
  const out = process.env.DDD_BENCH_OUT;
  if (out !== undefined) appendFileSync(out, `${row}\n`);
}

/** From the start page to the project's own heading visible - `answering`'s own span, reused as
 * every other measure's own setup. `tools/bench_gui.py`'s own `open` figures put the *server's*
 * side of this under 4.1 s even at 100,000 declarations, but the *page's* side is not only that
 * answer: clicking the project's button also starts the graph rendering in the background (the
 * default screen a project opens on), which at 100,000 declarations was observed to block the
 * main thread - and so this very click, and every UI interaction after it - well past `CAP_MS`.
 * Observed, not merely theorised: every measure capped on `100000-many-clean` (all twelve rows,
 * `Table`'s and `Units`' own click on a fresh page included), and on `100000-many-heavy`,
 * `answering` itself finished in 5.0 s while `first screen` - the same click, waiting further only
 * for a module node to appear - capped at the full two minutes; the graph is what stands between
 * those two waits, though this script never isolated it further (a page profile, not a benchmark
 * script's own job). So this is `capped()` too, not a plain wait: every caller below checks
 * whether opening finished (`didNotFinish`) and records its own measure the same way opening's own
 * did, rather than trying to act on a page that has not even answered this much yet. */
async function openProject(page: Page): Promise<Capped<void>> {
  return capped(async () => {
    await page.goto(address);
    await page.getByRole("button", { name: /Generated/ }).click();
    await expect(
      page.getByRole("heading", { name: "Generated", level: 1, exact: true }),
    ).toBeVisible({ timeout: LONG_TIMEOUT });
  });
}

/** `openProject`, recording `measure` capped or crashed - whichever opening itself did - and
 * telling the caller not to proceed if it did not finish: every measure below opens the project
 * this same way first, and none of them has anything left to measure once that alone did not
 * finish. */
async function openedProject(page: Page, measure: string): Promise<boolean> {
  const opened = await openProject(page);
  if (didNotFinish(opened)) {
    record(measure, formatMs(opened));
    return false;
  }
  return true;
}

/** The first row of whichever table is on screen: index 0 is always the header row, for
 * react-aria's own `Table` (a `grid`) and the Table tab's plain `<table>` alike - both spell a
 * header row `role="row"` too. */
function firstRow(page: Page): Locator {
  return page.getByRole("row").nth(1);
}

/**
 * The first component the Table tab lists, and that component's first declaration's unit picker
 * - the way a reader would reach it (resolution #1), read off the page rather than assumed. The
 * server half picks the *middle* of the project's sorted declarations instead (`tools/
 * bench_gui.py`'s own `measure()`); that is not a discrepancy to fix - the two measure different
 * things, a panel drawn against a request answered, and need not land on the same variable.
 */
async function openFirstVariablePicker(page: Page): Promise<string> {
  await page.getByRole("link", { name: "Table", exact: true }).click();
  const component = firstRow(page).getByRole("button").first();
  await expect(component).toBeVisible({ timeout: LONG_TIMEOUT });
  await component.click();
  const cell = firstRow(page).getByRole("button", { name: /^Set the unit of / });
  await expect(cell).toBeVisible({ timeout: LONG_TIMEOUT });
  const label = await cell.getAttribute("aria-label");
  if (label === null) throw new Error("the first declaration's unit cell has no aria-label");
  const variable = label.replace(/^Set the unit of /, "");
  await cell.click();
  await expect(
    page.getByRole("combobox", { name: `Unit of ${variable}`, exact: true }),
  ).toBeFocused({ timeout: LONG_TIMEOUT });
  return variable;
}

/** Clicks the Findings tab and waits for whichever it shows: a first row on a findings-heavy
 * project, or `findingCounts`'s own "Nothing to report" on a clean one (`gui/src/lib/
 * findings.ts`) - a generated project never shows anything else there, unlike Types and Shared
 * files, whose own generator never gives either tab a row to declare (resolution #1: those two
 * always show their sentence for none, read directly in their own tests below). */
async function openFindingsTab(page: Page): Promise<void> {
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await expect(firstRow(page).or(page.getByText("Nothing to report", { exact: true }))).toBeVisible(
    { timeout: LONG_TIMEOUT },
  );
}

/** How long `undoLastEditIfAny` waits for the Undo button before deciding there is truly nothing
 * to put back - a wait, not an instant, one-shot `isVisible()` read: `state.undoable`, which the
 * button depends on, reaches the page through the continuous `GET /api/state` long poll, a
 * separate path from the file re-fetch `apply shows`'s and `findings current`'s own measured wait
 * already confirms, and one that a one-shot read could lose the race against. Thirty seconds is
 * far past that gap in every run measured here (the poll is already continuously in flight, so
 * this is one more round trip, not a fresh one) while still far short of `CAP_MS`, for the one
 * genuine case this wait can span the whole of: a `capped()` measure moved on before its own
 * `POST /api/edit` ever answered, and there is truly nothing to undo. */
const UNDO_TIMEOUT = 30_000;

/** Puts back whatever this test's own edit changed, if anything landed at all - `UNDO_TIMEOUT`'s
 * own doc says why this waits rather than checking once. Leaves the project as generated for
 * whichever test opens it next (brief: "so the project is as generated for the next run" - needed
 * after both `apply shows` and `findings current`, since each presses Apply on its own fresh page
 * and the second would otherwise find nothing left to change).
 *
 * Called unconditionally after `apply shows`'s and `findings current`'s own measured
 * `elapsedCapped` span, whether that span read a real number, `CAPPED` or `CRASHED` - in every
 * case observed across all eight figures-before projects, that span was a real number by the time
 * this ran (nothing in it capped or crashed on any of them), so the two paths below are read off
 * the design rather than exercised yet:
 *   - **crashed**: the renderer is gone: every `page.XXX()` call below rejects, caught by the
 *     `try`/`catch` the same way `capped()` itself catches a crash, and there is nothing this step
 *     could do with a dead page regardless - `apply shows`/`findings current` already recorded
 *     `crashed` for their own row by this point, and whatever the edit did server-side stays as it
 *     is, same as a crash during any other measure leaves the state it was in.
 *   - **capped** (page alive, merely still busy): the measured action above is abandoned, not
 *     cancelled (`capped()`'s own doc), so it may still be mid-flight here - reading `undo`'s own
 *     visibility, which is all the *first* wait below does, does not itself write anything, and an
 *     abandoned `apply.click()` that only fires later targets a locator Playwright re-resolves at
 *     click time, not a stale element handle, so it either lands on the same control this step
 *     also uses or finds nothing there to click. Not proven race-free, only reasoned through: the
 *     safer alternative - skipping this step whenever the measured span did not settle cleanly -
 *     risks the exact "left dirty" failure fix round 1 already found once (a missing `undo.click()`
 *     there, not this one), which seemed the worse default to design around. */
async function undoLastEditIfAny(page: Page): Promise<void> {
  const undo = page.getByRole("button", { name: /^Undo / });
  const appeared = await expect(undo)
    .toBeVisible({ timeout: UNDO_TIMEOUT })
    .then(
      () => true,
      () => false,
    );
  if (!appeared) return;
  try {
    await undo.click();
    const confirm = page.getByRole("button", { name: /^Put back \d+ files?$/ });
    await expect(confirm).toBeVisible({ timeout: LONG_TIMEOUT });
    await confirm.click();
    await expect(undo).toBeHidden({ timeout: LONG_TIMEOUT });
  } catch (error) {
    if (!isPageCrash(error)) throw error;
  }
}

test("answering", async ({ page }) => {
  await page.goto(address);
  const ms = await elapsedCapped(async () => {
    await page.getByRole("button", { name: /Generated/ }).click();
    await expect(
      page.getByRole("heading", { name: "Generated", level: 1, exact: true }),
    ).toBeVisible({ timeout: LONG_TIMEOUT });
  });
  record("answering", formatMs(ms));
});

test("first screen", async ({ page }) => {
  await page.goto(address);
  // The module node's own wrapper, not its inner button: React Flow's Controls panel (Tidy/Fit
  // sit beside it, but the zoom buttons it draws on its own are not disabled) adds buttons of its
  // own to the same canvas, and `.react-flow__node` is what the existing journeys already use to
  // mean a module specifically (e.g. `e2e/skeleton.spec.ts`'s dragged-module test).
  const firstModule = page.locator(".react-flow__node").first();
  const ms = await elapsedCapped(async () => {
    await page.getByRole("button", { name: /Generated/ }).click();
    await expect(firstModule).toBeVisible({ timeout: LONG_TIMEOUT });
  });
  record("first screen", formatMs(ms));
});

test("Table", async ({ page }) => {
  if (!(await openedProject(page, "Table"))) return;
  const ms = await elapsedCapped(async () => {
    await page.getByRole("link", { name: "Table", exact: true }).click();
    await expect(firstRow(page)).toBeVisible({ timeout: LONG_TIMEOUT });
  });
  record("Table", formatMs(ms));
});

test("Units", async ({ page }) => {
  if (!(await openedProject(page, "Units"))) return;
  const ms = await elapsedCapped(async () => {
    await page.getByRole("link", { name: "Units", exact: true }).click();
    await expect(firstRow(page)).toBeVisible({ timeout: LONG_TIMEOUT });
  });
  record("Units", formatMs(ms));
});

test("Types", async ({ page }) => {
  if (!(await openedProject(page, "Types"))) return;
  const ms = await elapsedCapped(async () => {
    await page.getByRole("link", { name: "Types", exact: true }).click();
    // A generated project never declares a type (resolution #1): this tab always shows its own
    // sentence for none, never a first row - `typesTitle`, gui/src/lib/projectTypes.ts.
    await expect(page.getByText("This project declares no types", { exact: true })).toBeVisible({
      timeout: LONG_TIMEOUT,
    });
  });
  record("Types", formatMs(ms));
});

test("Shared files", async ({ page }) => {
  if (!(await openedProject(page, "Shared files"))) return;
  const ms = await elapsedCapped(async () => {
    await page.getByRole("link", { name: "Shared files", exact: true }).click();
    // A generated project never declares a shared entry either (resolution #1): always the
    // sentence for none - `tabTitle`, gui/src/lib/shared.ts.
    await expect(
      page.getByText("This project declares nothing in its shared files.", { exact: true }),
    ).toBeVisible({ timeout: LONG_TIMEOUT });
  });
  record("Shared files", formatMs(ms));
});

test("Files", async ({ page }) => {
  if (!(await openedProject(page, "Files"))) return;
  const ms = await elapsedCapped(async () => {
    await page.getByRole("link", { name: "Files", exact: true }).click();
    await expect(firstRow(page)).toBeVisible({ timeout: LONG_TIMEOUT });
  });
  record("Files", formatMs(ms));
});

test("Findings", async ({ page }) => {
  if (!(await openedProject(page, "Findings"))) return;
  const ms = await elapsedCapped(() => openFindingsTab(page));
  record("Findings", formatMs(ms));
});

test("typing", async ({ page }) => {
  await installLongTaskObserver(page);
  if (!(await openedProject(page, "typing"))) return;
  const opened = await capped(() => openFirstVariablePicker(page));
  if (didNotFinish(opened)) {
    record("typing", formatMs(opened));
    return;
  }
  const combobox = page.getByRole("combobox", { name: `Unit of ${opened}`, exact: true });
  await resetLongTasks(page);
  const result = await capped(async () => {
    // Twelve characters, 50 ms apart - matching no real unit on purpose: the picker's own
    // filtering and rendering is what this measure is about, not which options it happens to
    // find.
    await combobox.pressSequentially("abcdefghijkl", { delay: 50 });
    return longestLongTask(page);
  });
  record("typing", formatMs(result));
});

test("scrolling", async ({ page }) => {
  await installLongTaskObserver(page);
  if (!(await openedProject(page, "scrolling"))) return;
  const opened = await capped(() => openFindingsTab(page));
  if (didNotFinish(opened)) {
    // Today's own freeze or crash (`isPageCrash`'s own doc): the tab did not finish drawing
    // either way, so there is no table yet to scroll over - recorded the same way opening's own
    // wait was, rather than scrolling something that was never fully there.
    record("scrolling", formatMs(opened));
    return;
  }
  const table = page.getByRole("grid", { name: "Findings", exact: true });
  const box = await table.boundingBox();
  if (box === null) throw new Error("the Findings table has no bounding box to scroll over");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await resetLongTasks(page);
  const result = await capped(async () => {
    // Forty wheel steps of 600 px, 50 ms apart, the mouse over the table itself (resolution #2):
    // the same code scrolls the page today and the table's own box once Task 7 gives it one.
    for (let step = 0; step < 40; step += 1) {
      await page.mouse.wheel(0, 600);
      await page.waitForTimeout(50);
    }
    return longestLongTask(page);
  });
  record("scrolling", formatMs(result));
});

test("apply shows", async ({ page }) => {
  if (!(await openedProject(page, "apply shows"))) return;
  const opened = await capped(() => openFirstVariablePicker(page));
  if (didNotFinish(opened)) {
    record("apply shows", formatMs(opened));
    return;
  }
  const variable = opened;
  const combobox = page.getByRole("combobox", { name: `Unit of ${variable}`, exact: true });
  const cell = page.getByRole("button", { name: `Set the unit of ${variable}`, exact: true });
  // A unit no generated project ever states (tools/generate_project.py's own vocabulary: "rpm",
  // "Nm", "kPa", "degC", "V", "A", "ms", "Hz"), typed and confirmed with Enter - accepted whether
  // it is listed or not (gui/e2e/units.spec.ts's own "in no list at all" journey) - so the row's
  // own unit, whatever it was, is guaranteed to actually change.
  await combobox.fill("BenchUnit");
  await combobox.press("Enter");
  const apply = page.getByRole("button", { name: /^Apply to \d+ files?$/ });
  await expect(apply).toBeVisible({ timeout: LONG_TIMEOUT });
  const ms = await elapsedCapped(async () => {
    await apply.click();
    await expect(cell).toHaveText("BenchUnit", { timeout: LONG_TIMEOUT });
  });
  record("apply shows", formatMs(ms));
  await undoLastEditIfAny(page);
});

test("findings current", async ({ page }) => {
  if (!(await openedProject(page, "findings current"))) return;
  const opened = await capped(() => openFirstVariablePicker(page));
  if (didNotFinish(opened)) {
    record("findings current", formatMs(opened));
    return;
  }
  const variable = opened;
  const combobox = page.getByRole("combobox", { name: `Unit of ${variable}`, exact: true });
  await combobox.fill("BenchUnit");
  await combobox.press("Enter");
  const apply = page.getByRole("button", { name: /^Apply to \d+ files?$/ });
  await expect(apply).toBeVisible({ timeout: LONG_TIMEOUT });
  // One targeted read of the revision right before the press, not a listener kept running from
  // the start of the test: that would re-parse every long-poll answer for as long as the test
  // runs, and at 100,000 declarations findings-heavy that answer is upward of 50 MB (design doc
  // §2) - a needless cost this avoids regardless of whether it was ever actually what slowed an
  // earlier, listener-based version of this test; never confirmed as a cause the way
  // `isPageCrash`'s own finding was.
  const before = await page.evaluate<number>(async () => {
    const response = await fetch("/api/state");
    const body = (await response.json()) as { revision: number };
    return body.revision;
  });
  const ms = await elapsedCapped(async () => {
    // A benchmark may wait on a response directly; a journey may not (brief). The long poll in
    // flight when Apply is pressed answers the edit's write, its revision unchanged; the page's
    // next one answers when the edit's analysis lands, with the newer revision this waits for.
    const newer = page.waitForResponse(async (response) => {
      if (new URL(response.url()).pathname !== "/api/state") return false;
      try {
        const body = (await response.json()) as { revision?: unknown };
        return typeof body.revision === "number" && body.revision > before;
      } catch {
        return false;
      }
    });
    await apply.click();
    await newer;
  });
  record("findings current", formatMs(ms));
  // "After findings current, press Undo, so the project is as generated for the next run" (brief).
  await undoLastEditIfAny(page);
});
