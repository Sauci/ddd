import { spawnSync } from "node:child_process";
import { readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";

export const CONTROLLER = join("components", "controller.ddd.json");
export const SENSOR_HUB = join("components", "sensor_hub.ddd.json");
export const USER_INTERFACE = join("components", "user_interface.ddd.json");
/** ValueE's other reader, in a sub project of its own - with UserInterface, the only demo
 * variable with one producer and two consumers, which is what lets a settlement reach one file
 * or both. */
export const EVENT_LOGGER = join("subsystems", "logging", "event_logger.ddd.json");
/** The files of examples/vocabulary the journeys change, in its copy: the component stating its
 * units, and the units file listing them. */
export const PUMP = "pump.ddd.json";
export const UNITS = "units.ddd.json";

/** A variable's own `"unit": ...` in a file: the first one after its name, whichever file it is. */
function unitOf(variable: string): RegExp {
  return new RegExp(`("name": "${variable}"[\\s\\S]*?"unit": )"[^"]*"`);
}

/** The bytes of a file with one variable's unit replaced, and nothing else. */
export function withUnitOf(bytes: Buffer, variable: string, unit: string): Buffer {
  const text = bytes.toString("utf8").replace(unitOf(variable), `$1${JSON.stringify(unit)}`);
  return Buffer.from(text, "utf8");
}

/** The bytes of a file with ValueA's unit replaced, and nothing else. */
export function withUnitOfValueA(bytes: Buffer, unit: string): Buffer {
  return withUnitOf(bytes, "ValueA", unit);
}

/** Controller's reading of a variable drifted to another unit, saved from outside - ValueA's to
 * `rpm` unless said otherwise; answers the file as it was before. */
export function drift(directory: string, variable = "ValueA", unit = "rpm"): Buffer {
  return driftIn(directory, CONTROLLER, variable, unit);
}

/** A variable's unit in one file of a copy drifted to another spelling, saved from outside;
 * answers the file as it was before. */
export function driftIn(directory: string, file: string, variable: string, unit: string): Buffer {
  const path = join(directory, file);
  const before = readFileSync(path);
  writeFileSync(path, withUnitOf(before, variable, unit));
  return before;
}

/** A variable's own `"datatype": ...` in a file: the first one after its name. */
function datatypeOf(variable: string): RegExp {
  return new RegExp(`("name": "${variable}"[\\s\\S]*?"datatype": )"[^"]*"`);
}

/** A variable's datatype in one file of a copy drifted to another, saved from outside - what a
 * comparison reports as `changed-interface`, unlike `driftIn`'s unit, which the live analysis
 * catches as `definition-mismatch` between a component's own reading and its producer. Written
 * on the *producing* declaration: resolution follows the producer's own statement of a field
 * (`reference = producer or refs[0]`, in the analysis that settles which declaration is the
 * reference one), so this is what actually changes the delivery a comparison reads, the way a
 * real widened storage type would. Answers the file as it was before. */
export function driftDatatypeIn(
  directory: string,
  file: string,
  variable: string,
  datatype: string,
): Buffer {
  const path = join(directory, file);
  const before = readFileSync(path);
  const text = before
    .toString("utf8")
    .replace(datatypeOf(variable), `$1${JSON.stringify(datatype)}`);
  writeFileSync(path, text, "utf8");
  return before;
}

/** ValueA renamed from outside in every file of the demo that declares or names it. */
export function renameValueA(directory: string, name: string): void {
  for (const file of [CONTROLLER, SENSOR_HUB]) {
    const path = join(directory, file);
    writeFileSync(path, readFileSync(path, "utf8").replaceAll('"ValueA"', JSON.stringify(name)));
  }
}

/** Chooses a unit for ValueA from its panel's picker: typed, then taken from the list. */
export async function chooseUnit(page: Page, unit: string): Promise<void> {
  await page.getByRole("combobox", { name: "Unit of ValueA" }).fill(unit);
  await page.getByRole("option", { name: unit, exact: true }).first().click();
}

/** Opens a variable's panel from its component's table, the way a reader reaches it: the unit
 * cell, which opens the panel on the unit's row with its field focused. */
export async function openPanel(
  page: Page,
  address: string,
  variable: string,
  component = "Controller",
): Promise<Locator> {
  await page.goto(address);
  await page.getByRole("button", { name: component, exact: true }).click();
  await page.getByRole("button", { name: `Set the unit of ${variable}` }).click();
  return page.getByRole("complementary", { name: variable });
}

/** Opens a variable's values grid from its component's table, the way a reader reaches it: the
 * Shape cell's own button - CurveA's and MapA's own among Controller's fourteen declarations,
 * past the box's edge at this viewport (part 17's task 9: the declarations table is virtualised).
 * Wheeled into view first, the mouse over the table, rather than left to the click's own
 * auto-scroll: React Aria's own ScrollView sets `pointer-events: none` on a long table's content
 * while it scrolls and for 300 ms after (`private/virtualizer/ScrollView.mjs`), and Playwright's
 * own actionability check hit-tests only a click's first event - so a click sent mid-scroll can
 * pass that check against a target already back under the pointer, and still open nothing,
 * `usePress` itself cancelling a press made while `pointer-events` read `none` partway through
 * (measured: `Show the values of CurveA` clicked at the box's own reported, visible position
 * still opened nothing, the page left on Controller's own heading - and the same click, the box
 * already wheeled to rest first, opened CurveA's grid every time). Never enlarges the box: this
 * is the wheel a reader's own hand would turn over it. */
export async function openValues(
  page: Page,
  address: string,
  variable: string,
  component = "Controller",
): Promise<void> {
  await page.goto(address);
  await page.getByRole("button", { name: component, exact: true }).click();
  const button = page.getByRole("button", { name: `Show the values of ${variable}` });
  await scrolledIntoView(page, `Declarations of ${component}`, button);
  await button.click();
}

/** Wheels a long table's own box, the mouse over its middle, until `target` sits inside the
 * box's own bounds top to bottom - stopping as soon as it does, so a row already in view is
 * never scrolled past. Not `target.isVisible()`: that reads true for a row the virtualiser has
 * already drawn past the box's own visible bottom - idle or scrolling down, its own overscan
 * extends a third of the box's own visible height below what is on screen, and the same third
 * above it only while actively scrolling up (`private/virtualizer/OverscanManager.mjs`'s own
 * `getOverscannedRect`, read by its own velocity) - and nothing about a drawn row's own CSS says
 * the box's own scroll position clips it; visible and displayed is all that check ever meant, on
 * a row a reader could not actually see (measured: true before any wheel at all, for a row the
 * overscan had already drawn past the box's own last visible one). Bounded at forty steps: a
 * target that never comes within the box's own bounds fails here, in words that say why, rather
 * than at whatever assertion happens to be next. */
export async function scrolledIntoView(page: Page, label: string, target: Locator): Promise<void> {
  const box = page.getByRole("grid", { name: label });
  const container = await box.boundingBox();
  if (container === null) throw new Error(`no table labelled "${label}" to scroll`);
  // Settles on the box's own `scrollTop` rather than a fixed pause: a wheel's own scroll is still
  // animating, or the virtualiser still catching rows up to it, for longer than any one guess
  // would cover on a slow run, and longer than it need wait on a fast one.
  const settled = async () => {
    let last: number | null = null;
    for (let tries = 0; tries < 20; tries += 1) {
      const current = await box.evaluate((element) => element.scrollTop);
      if (current === last) return;
      last = current;
      await page.waitForTimeout(16);
    }
  };
  await page.mouse.move(container.x + container.width / 2, container.y + container.height / 2);
  for (let step = 0; step < 40 && !(await withinBox(page, label, target)); step += 1) {
    await page.mouse.wheel(0, 200);
    await settled();
  }
  if (!(await withinBox(page, label, target))) {
    throw new Error(`scrolling "${label}" never brought its target row within the box`);
  }
}

/** Whether `target` sits whole inside the box of the long table labelled `label`, top to bottom:
 * what a reader can see of it, which `target.isVisible()` does not say (`scrolledIntoView`'s own
 * doc says why). The box and the target are both measured on each call, so the answer holds
 * wherever the page itself stands. */
export async function withinBox(page: Page, label: string, target: Locator): Promise<boolean> {
  const container = await page.getByRole("grid", { name: label }).boundingBox();
  const rect = await target.boundingBox();
  return (
    container !== null &&
    rect !== null &&
    rect.y >= container.y &&
    rect.y + rect.height <= container.y + container.height
  );
}

/** A table pasted into the grid the way a browser delivers one: a `DataTransfer` built in the
 * page and dispatched as a `paste` event, because Playwright cannot put a table on the system
 * clipboard. Dispatched on the grid's own `<section>` - the one `ValuesGridView` binds `onPaste`
 * to - found by filtering for the `section` that holds a `grid`, `.first()` only as a guard
 * against a second one elsewhere on the page: this project's own `Table` sits in a `<section>`
 * on every grid screen, not only this one. */
export async function paste(page: Page, text: string): Promise<void> {
  await page
    .locator("section")
    .filter({ has: page.getByRole("grid") })
    .first()
    .evaluate((node, block) => {
      const data = new DataTransfer();
      data.setData("text/plain", block);
      node.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true }));
    }, text);
}

/** One variable's linear factor in one file of a copy drifted, saved from outside; answers the
 * file as it was before. */
export function driftFactor(
  directory: string,
  file: string,
  variable: string,
  factor: number,
): Buffer {
  return driftNumber(directory, file, variable, "factor", factor);
}

/** One variable's greatest limit in one file of a copy drifted, saved from outside, which is
 * what makes its two declarations disagree about `limits`; answers the file as it was before. */
export function driftMax(directory: string, file: string, variable: string, max: number): Buffer {
  return driftNumber(directory, file, variable, "max", max);
}

/** The first number one variable's key holds in a file of a copy, replaced in place. */
function driftNumber(
  directory: string,
  file: string,
  variable: string,
  key: string,
  value: number,
): Buffer {
  const path = join(directory, file);
  const before = readFileSync(path);
  const text = before
    .toString("utf8")
    .replace(new RegExp(`("name": "${variable}"[\\s\\S]*?"${key}": )[0-9.]+`), `$1${value}`);
  writeFileSync(path, text, "utf8");
  return before;
}

/** `path`'s modification time, read now so a write about to be made to it can be hidden from
 * the session's own file watcher afterwards - call the function this returns once that write is
 * made. The session decides a file changed by `(st_mtime_ns, st_size)` alone (`stamped`,
 * `session.py`), never by reading it, so a write whose bytes change but whose stamp does not
 * is invisible to the watcher while still being a different file to anyone who reads it fresh -
 * which is what an Apply's own staleness check does. Used where a test means the second and not
 * the first, the way `keys.spec.ts`'s "a change refused as stale..." does.
 *
 * The restore is made through python's own `os.utime(path, ns=(...))`, not `fs.utimesSync`:
 * `utimesSync` takes the time through a JS `number`, which is a handful of nanoseconds off for
 * an epoch this large - close enough to fool a human but not the exact-tuple comparison
 * `stamped` makes, so the write would still have been visible to it. Reached through
 * `DDD_PYTHON` rather than a shell tool, the way `dump` above is, so this needs nothing this
 * repository does not already depend on and is exact on every platform the suite runs on. */
export function preserveStampOf(path: string): () => void {
  const mtimeNs = statSync(path, { bigint: true }).mtimeNs;
  return () => {
    const result = spawnSync(process.env.DDD_PYTHON ?? "python", [
      "-c",
      "import os, sys\nos.utime(sys.argv[1], ns=(int(sys.argv[2]), int(sys.argv[2])))",
      path,
      mtimeNs.toString(),
    ]);
    if (result.status !== 0) {
      throw new Error(
        `restoring ${path}'s modification time exited with ${String(result.status)}: ` +
          `${result.stderr.toString("utf8")}`,
      );
    }
  };
}

/** A producing declaration's id taken away from outside, the way a description written before
 * `ddd id` adopted ids states it - which is what `missing-id` reports; answers the file as it
 * was before. */
export function unstamp(directory: string, file: string, variable: string): Buffer {
  const path = join(directory, file);
  const before = readFileSync(path);
  const text = before
    .toString("utf8")
    .replace(new RegExp(`("name": "${variable}"[\\s\\S]*?)\\n\\s*"id": "[^"]*",`), "$1");
  writeFileSync(path, text, "utf8");
  return before;
}

/** BlockA's own array `init` in the copy's user_interface.ddd.json, replaced from outside with
 * the values given - part 7's own fixture for a finding that leads to the values grid: an
 * out-of-range element the analysis reports as `init-invalid`, whose route opens BlockA's own
 * grid rather than its variable panel. */
export function writeBlockAInit(directory: string, values: readonly number[]): void {
  const path = join(directory, USER_INTERFACE);
  const text = readFileSync(path, "utf8").replace(
    /("name": "BlockA"[\s\S]*?"init": )\[[\s\S]*?\]/,
    `$1${JSON.stringify(values)}`,
  );
  writeFileSync(path, text, "utf8");
}

/** CurveA made to name a scalar type instead of stating its own storage, in the copy: the type
 * declared on Controller itself, and the `datatype`, `unit` and `conversion` taken off the
 * declaration, which the loader refuses beside a `typename`. Measured on the copy this writes:
 * the project loads with no finding at all and CurveA resolves exactly as it did - uint16, ms,
 * x0.01, the same six values, the same producing file - so the Shape column must keep offering
 * it. Nothing in examples/ has this shape, which is how it was taken away unnoticed.
 *
 * Written whole rather than patched: this changes what the declaration is made of, not one
 * value inside it, and no journey using it applies an edit whose hunks would move. */
export function typeCurveA(directory: string): void {
  const path = join(directory, CONTROLLER);
  const data = JSON.parse(readFileSync(path, "utf8"));
  data.component.types = [
    {
      type: "scalar",
      name: "Millis_t",
      description: "A duration as every component of this project agrees to see it",
      datatype: "uint16",
      unit: "ms",
      conversion: { factor: 0.01 },
      limits: { min: 0, max: 655.35 },
    },
  ];
  const curve = data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === "CurveA",
  ).definition;
  for (const key of ["datatype", "unit", "conversion"]) delete curve[key];
  curve.typename = "Millis_t";
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

/** BlockA given three dimensions, and an init nested to match with one value over uint8: a
 * shape no grid draws, saved from outside the page the way every other drift here is. Legal
 * DDD - the loader takes it and only `init-invalid` is reported - and the one shaped object of
 * examples/demo whose declaration is easy to widen without touching anything that reads it. */
export function widenBlockA(directory: string): void {
  const path = join(directory, USER_INTERFACE);
  const text = readFileSync(path, "utf8")
    .replace(/("name": "BlockA"[\s\S]*?"dimensions": )\[[^\]]*\]/, "$1[2, 2, 2]")
    .replace(
      /("name": "BlockA"[\s\S]*?"init": )\[[\s\S]*?\]\s*(?=,\s*\n)/,
      "$1[[[0, 12], [28, 52]], [[84, 124], [180, 9999]]]",
    );
  writeFileSync(path, text, "utf8");
}

/** `ddd dump` of `project` into `output`, both read and written relative to `directory` - the
 * Compare tab's own baseline, produced the way `fixtures.ts` itself starts `ddd gui`: through
 * `DDD_PYTHON` rather than the `ddd` launcher, which on Windows starts python as a child of its
 * own that killing the launcher leaves running. Run from `directory`, exactly as the server
 * under test is, so `output` lands under the one root a baseline is ever read from
 * (`ddd/gui/compare.py`'s own `_resolved_baseline` confines it there). Synchronous: a journey
 * calls this once, before it ever opens the page, and there is nothing here to await. */
export function dump(directory: string, project: string, output: string): void {
  const result = spawnSync(
    process.env.DDD_PYTHON ?? "python",
    ["-m", "ddd", "dump", project, "-o", output],
    { cwd: directory },
  );
  if (result.status !== 0) {
    throw new Error(
      `ddd dump ${project} -o ${output} exited with ${String(result.status)}: ` +
        `${result.stderr.toString("utf8")}`,
    );
  }
}

/** One frame as a reader saw it: what a field read, and whether the page said "Updating the
 * findings…" anywhere. */
export type Frame = readonly [value: string | null, updating: boolean];

/** Records, from now on and at every frame the page paints, what the field named `label` reads
 * and whether the page says its findings are updating - what a reader sees at each paint, which
 * a wait on any one moment can step over: on examples/demo an analysis lands within a few frames.
 * Read back with `framesWatched`. */
export async function watchFrames(page: Page, label: string): Promise<void> {
  await page.evaluate((name) => {
    const frames: [string | null, boolean][] = [];
    (window as unknown as { watched: typeof frames }).watched = frames;
    const each = () => {
      const field = document.querySelector<HTMLInputElement>(`input[aria-label="${name}"]`);
      const said = [...document.querySelectorAll('[role="status"]')].some(
        (status) => status.textContent === "Updating the findings…",
      );
      frames.push([field?.value ?? null, said]);
      requestAnimationFrame(each);
    };
    requestAnimationFrame(each);
  }, label);
}

/** Every frame `watchFrames` has recorded so far, in order. */
export function framesWatched(page: Page): Promise<Frame[]> {
  return page.evaluate(() => (window as unknown as { watched: Frame[] }).watched);
}
