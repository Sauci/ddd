import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, statSync, utimesSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { type APIResponse, expect, type Locator, type Page } from "@playwright/test";

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

/** A variable's declaration in one file of a copy turned into one that reads text - a byte
 * datatype, the string conversion and one dimension of eight - so stating no unit and no limits,
 * which text has none of. A producer's datatype wider than a byte, settled onto it, is then a
 * change the loader refuses (`driftDatatypeIn` makes one). Saved from outside, before the server
 * starts. */
export function readAsText(directory: string, file: string, variable: string): void {
  const path = join(directory, file);
  const data = JSON.parse(readFileSync(path, "utf8"));
  const entry = data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === variable,
  );
  entry.definition = {
    ...Object.fromEntries(
      Object.entries(entry.definition).filter(([key]) => key !== "unit" && key !== "limits"),
    ),
    datatype: "uint8",
    conversion: { kind: "string" },
    dimensions: [8],
  };
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
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
 * auto-scroll, and clicked once it takes the pointer again: a click that scrolls the box itself
 * aims its press before the page has caught up with that scroll, and React Aria's own ScrollView
 * then takes the pointer from the table's content under it (`scrolledIntoView`'s own doc says
 * what was measured). Never enlarges the box: this is the wheel a reader's own hand would turn
 * over it. */
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
 * than at whatever assertion happens to be next.
 *
 * Then waits for `target` to take the pointer again, so that the click its caller sends next
 * lands on it. React Aria's own ScrollView sets `pointer-events: none` on a long table's content,
 * which `target` inherits, from a scroll until a timer runs out: 300 ms from the scroll that armed
 * it, re-armed only by a scroll in its last 50 ms (`private/virtualizer/ScrollView.mjs`).
 * Measured in Chrome on the Linux development PC, the pointer came back 310 to 313 ms after a lone
 * scroll, and anything from 65 to 316 ms after the last of a burst of scrolls a frame apart, by
 * where the burst ended against that timer. Settled on `scrollTop` alone, this returned inside
 * that window every time: the wheel's one scroll event came at about 30 ms, `scrollTop` settled
 * by 65 to 98 ms, and the window closed at about 345 ms. Every click after it found the table in
 * the way of its hit-test three or four times, and Playwright retried it with the box scrolled
 * to other alignments (end, center, start), each of those scrolls opening the window again; a
 * retry aimed before the page had caught up with its own scroll lost its press to the table, and
 * the grid never opened (CI: run 37688993981 on ubuntu chromium, run 37697917866 on windows
 * msedge). Waited for, the click's first attempt scrolls nothing, and lands. */
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
  // Read off the target itself, which inherits what the ScrollView sets on the content above it:
  // a reader's click lands on it once this reads anything but `none`, and not before.
  await expect(target, `"${label}" never gave its target row the pointer back`).not.toHaveCSS(
    "pointer-events",
    "none",
  );
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
 * on every grid screen, not only this one. A page that draws no grid is found by what it does
 * hold instead, `within` - its heading, say. */
export async function paste(
  page: Page,
  text: string,
  within: Locator = page.getByRole("grid"),
): Promise<void> {
  await page
    .locator("section")
    .filter({ has: within })
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
  writeFileSync(path, drifted(before, variable, key, value), "utf8");
  return before;
}

/** `text` with the first number one variable's key holds replaced by `value`. */
function drifted(text: Buffer, variable: string, key: string, value: number): string {
  return text
    .toString("utf8")
    .replace(new RegExp(`("name": "${variable}"[\\s\\S]*?"${key}": )[0-9.]+`), `$1${value}`);
}

/** One variable's greatest limit drifted as `driftMax` drifts it, but written unseen by the
 * session's own file watcher (`writeUnseen`), the way `keys.spec.ts`'s "a change refused as
 * stale..." needs it; `max` must be as wide as the number it replaces, so that the size does not
 * move either. Answers the file as it was. */
export function driftMaxUnseen(
  directory: string,
  file: string,
  variable: string,
  max: number,
): Buffer {
  const before = readFileSync(join(directory, file));
  writeUnseen(directory, file, drifted(before, variable, "max", max));
  return before;
}

/** `text` written over a file of a copy, unseen by the session's own file watcher - which decides
 * a file changed by `(st_mtime_ns, st_size)` alone (`stamped`, `session.py`), never by reading it
 * - while a different file to anyone who reads it fresh, which is what an Apply's own staleness
 * check does. Used where a test means the second and not the first: a change the watcher saw
 * would bring a revision of its own, racing whatever the test means to read before one comes.
 * `text` must be exactly as many bytes as the file, since a size of its own would show the
 * watcher the write: refused here, before anything is written, rather than left to race.
 *
 * The new bytes are written in the directory above the file's, given the file's own times through
 * python's `os.utime(path, ns=(...))` - exact to the nanosecond, where `fs.utimesSync` takes a JS
 * `number` a handful of nanoseconds off for an epoch this large - and renamed over it in one step,
 * so no moment shows the watcher a stamp of their own. The watcher stamps the directory a pattern
 * expands in too (`Revision.watched`, session.py), as the demo's `components/*.ddd.json` makes of
 * `components`, and a rename into a directory moves its time: put back at once after the rename,
 * with nothing between the two but the calls themselves, the write being staged elsewhere. Written
 * in place and its stamp put back after, by a python started for it, the write stood visible for
 * that start-up, and a poll landing then re-analysed the project and left nothing stale to refuse
 * (CI, PR #77, on ubuntu and windows). The rename is tried again while windows refuses it access,
 * as `ddd.editing` does. */
export function writeUnseen(directory: string, file: string, text: string): void {
  const path = join(directory, file);
  const bytes = Buffer.from(text, "utf8");
  const size = statSync(path).size;
  if (bytes.length !== size) {
    throw new Error(
      `writing ${path} unseen takes ${size} bytes, not ${bytes.length}: ` +
        `a size of their own would show the watcher the write`,
    );
  }
  const result = spawnSync(process.env.DDD_PYTHON ?? "python", ["-c", UNSEEN, path], {
    input: bytes,
  });
  if (result.status !== 0) {
    throw new Error(
      `writing ${path} unseen exited with ${String(result.status)}: ` +
        `${result.stderr.toString("utf8")}`,
    );
  }
}

/** `writeUnseen`'s python: stdin's bytes in the directory above `argv[1]`'s, under its times, then
 * renamed over it, and its directory's times put back. */
const UNSEEN = [
  "import os, sys, time",
  "path = sys.argv[1]",
  "directory = os.path.dirname(path)",
  "staged = os.path.join(os.path.dirname(directory), os.path.basename(path) + '.unseen')",
  "status = os.stat(path)",
  "with open(staged, 'wb') as file:",
  "    file.write(sys.stdin.buffer.read())",
  "os.utime(staged, ns=(status.st_atime_ns, status.st_mtime_ns))",
  "kept = os.stat(directory)",
  "for attempt in range(49):",
  "    try:",
  "        os.replace(staged, path)",
  "        break",
  "    except PermissionError:",
  "        time.sleep(0.02)",
  "else:",
  "    os.replace(staged, path)",
  "os.utime(directory, ns=(kept.st_atime_ns, kept.st_mtime_ns))",
].join("\n");

/** The demo's description in a copy made to include nothing, before `ddd gui` starts on it: a
 * project that loads with no finding and no component, its other files left on disk unread - the
 * empty project 16:M13 points at New file. */
export function includesNothing(directory: string): void {
  const path = join(directory, "demo.ddd.json");
  const data = JSON.parse(readFileSync(path, "utf8"));
  data.project.includes = [];
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

/** The letters a DDD id is spelled in (`OBJECT_ID_ALPHABET`, src/ddd/models/common.py). */
const ID_LETTERS = "abcdefghjkmnpqrstvwxyz0123456789";

/** `count` locals added to Controller's interface in a copy, before `ddd gui` starts on it, named
 * `Crowd00000` on and each with an id of its own, so that they add no finding: a component of
 * thousands of declarations, whose table puts a widened filter's rows back a thousand at a time. */
export function crowd(directory: string, count: number): void {
  const path = join(directory, CONTROLLER);
  const data = JSON.parse(readFileSync(path, "utf8"));
  for (let at = 0; at < count; at += 1) {
    let id = "";
    for (let left = at, letter = 0; letter < 10; letter += 1, left = Math.floor(left / 32)) {
      id = `${ID_LETTERS[left % 32]}${id}`;
    }
    data.component.interface.push({
      scope: "local",
      definition: {
        name: `Crowd${String(at).padStart(5, "0")}`,
        id: `zz${id}`,
        kind: "measurement",
        datatype: "uint8",
        unit: "%",
        conversion: { kind: "identity" },
        volatile: false,
      },
    });
  }
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

/** Controller made to declare a scalar type, `Gain_t`, and two declarations naming it: `GainA`, a
 * parameter of no dimensions stating 10, and `GainRow`, a value block of three. Neither states a
 * datatype of its own: the type does. */
export function namingAScalarType(directory: string): void {
  const path = join(directory, CONTROLLER);
  const data = JSON.parse(readFileSync(path, "utf8"));
  data.component.types = [
    {
      type: "scalar",
      name: "Gain_t",
      description: "A gain in hertz",
      datatype: "uint16",
      unit: "Hz",
      conversion: { factor: 0.25 },
    },
  ];
  data.component.interface.push(
    {
      scope: "local",
      definition: {
        kind: "parameter",
        name: "GainA",
        id: "g41na0000001",
        typename: "Gain_t",
        init: 10,
        volatile: false,
      },
    },
    {
      scope: "local",
      definition: {
        kind: "value_block",
        name: "GainRow",
        id: "g41na0000002",
        typename: "Gain_t",
        dimensions: [3],
        init: [1, 2, 3],
        volatile: false,
      },
    },
  );
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
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

/** A baseline under `directory/baseline`, for `hostile.spec.ts`'s own page on another port to
 * name through `?baseline=` - another way the Compare tab's baseline reaches the server, not
 * through `dump` above but written by hand: a project naming one component file and loading
 * `marker.py`. `marker.py` is invalid past its first line of real code - it exposes no `PLUGIN`,
 * so `ddd.plugins.load_plugin` refuses it - and that is beside the point: a plugin's module
 * body runs on import, before it is ever validated as a plugin at all, so `marker.py` has
 * already written `ran` beside itself the moment anything asks to read this baseline, whatever
 * it decides about the baseline afterwards.
 *
 * Returns the path `?baseline=` would name, relative to `directory`, in this platform's own
 * separator - the one `pathlib` resolves natively on whichever machine also runs the server. */
export function writeHostileBaseline(directory: string): string {
  const dir = join(directory, "baseline");
  mkdirSync(dir);
  const component = { component: { name: "Hostile", interface: [] } };
  writeFileSync(join(dir, "component.ddd.json"), `${JSON.stringify(component, null, 2)}\n`, "utf8");
  const project = {
    project: { name: "Hostile", includes: ["component.ddd.json"], plugins: ["marker.py"] },
  };
  writeFileSync(join(dir, "baseline.ddd.json"), `${JSON.stringify(project, null, 2)}\n`, "utf8");
  writeFileSync(
    join(dir, "marker.py"),
    [
      "from pathlib import Path",
      'Path(__file__).with_name("ran").write_text("the plugin ran", encoding="utf-8")',
      "",
    ].join("\n"),
    "utf8",
  );
  return join("baseline", "baseline.ddd.json");
}

/** One frame as a reader saw it: what a field read, whether the page said "Updating the
 * findings…" anywhere, and whether it offered the undo of one edit. */
export type Frame = readonly [value: string | null, updating: boolean, undoOffered: boolean];

/** Records, from now on and at every frame the page paints, what the field named `label` reads,
 * whether the page says its findings are updating, and whether it offers to undo the edit named
 * `edit` - its button, "Undo " and the edit's name - what a reader sees at each paint, which a
 * wait on any one moment can step over: on examples/demo an analysis lands within a few frames.
 * Read back with `framesWatched`. */
export async function watchFrames(page: Page, label: string, edit: string): Promise<void> {
  await page.evaluate(
    ([name, undo]) => {
      const frames: [string | null, boolean, boolean][] = [];
      (window as unknown as { watched: typeof frames }).watched = frames;
      const each = () => {
        const field = document.querySelector<HTMLInputElement>(`input[aria-label="${name}"]`);
        const said = [...document.querySelectorAll('[role="status"]')].some(
          // The heading's says it after what the page wrote, where it says that too (16:I13).
          (status) => status.textContent?.endsWith("Updating the findings…") === true,
        );
        const offered = [...document.querySelectorAll("button")].some(
          (button) => button.textContent === undo,
        );
        frames.push([field?.value ?? null, said, offered]);
        requestAnimationFrame(each);
      };
      requestAnimationFrame(each);
    },
    [label, `Undo ${edit}`],
  );
}

/** Every frame `watchFrames` has recorded so far, in order. */
export function framesWatched(page: Page): Promise<Frame[]> {
  return page.evaluate(() => (window as unknown as { watched: Frame[] }).watched);
}

/** What `ddd gui` answers a request it failed on (`_INTERNAL`, src/ddd/gui/server.py), and so
 * what `failing`'s `"http"` answers with: a page shows the server's own words for it. */
export const SERVER_FAILED = "ddd gui failed on this request; the terminal it runs in shows why";

/**
 * Makes the page's requests whose path is `path` - or matches it - fail, the first `times` of
 * them, or every one where `times` is left out, and lets the rest through to the server
 * (spec 2026-10-08 §5). `"http"` answers each as the server answers a request it failed on, a
 * `500` with its own error body; `"network"` answers nothing at all, as a dropped connection.
 * Playwright's own route, on this page alone: the server's code is never touched. Answers how
 * many it has failed so far.
 *
 * `path` is matched as `held`'s is (`Matcher`): a string as a request's pathname, and a pattern
 * afresh for every request, whatever its flags. A route on the same path registered after this
 * one, and calling `route.continue()`, sends its request straight to the server, past `failing`;
 * one calling `route.fallback()` hands it on to `failing`.
 */
export async function failing(
  page: Page,
  path: Matcher,
  how: "http" | "network",
  times = Number.POSITIVE_INFINITY,
): Promise<() => number> {
  let failed = 0;
  await page.route(matching(path), async (route) => {
    if (failed >= times) {
      await route.fallback();
      return;
    }
    failed += 1;
    if (how === "network") {
      await route.abort("failed");
      return;
    }
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ error: "internal", message: SERVER_FAILED }),
    });
  });
  return () => failed;
}

/** What `held` and `failing` match: a pathname, a pattern over the pathname, or a test of the
 * whole address (a query parameter included). A pathname is the request's own, from its leading
 * `/`, and never a glob: a string that does not start with `/` is refused, rather than left to
 * match no request and say nothing. A pattern is matched afresh for every request, whatever its
 * flags: a copy of it is tried from its start each time, so a `g` or `y` flag, which makes `test`
 * go on from where it last stopped, never makes one match depend on the last. */
export type Matcher = string | RegExp | ((url: URL) => boolean);

function matching(matcher: Matcher): (url: URL) => boolean {
  if (typeof matcher === "string") {
    // A glob such as `**/api/units`, as a route of Playwright's own takes one, is a pathname no
    // request has: refused here, where a hold of it would hold nothing.
    if (!matcher.startsWith("/")) {
      throw new Error(
        `${JSON.stringify(matcher)} matches no request: a string is a pathname, ` +
          "starting with /, never a glob",
      );
    }
    return (url) => url.pathname === matcher;
  }
  if (matcher instanceof RegExp) {
    // A copy, flags and all, so that setting where it starts leaves the caller's own untouched.
    const pattern = new RegExp(matcher);
    return (url) => {
      pattern.lastIndex = 0;
      return pattern.test(url.pathname);
    };
  }
  return matcher;
}

/**
 * Holds the page's next request that `matcher` matches until the function it answers is called,
 * then lets it through to the server; any later one goes straight through (`{ times: 1 }`: a
 * route left registered met the teardown on Windows as `ECONNRESET`, P19b-7). With `every`,
 * each one is held until the release, for a journey whose claim is about every answer, not the
 * next one. With `onAnswer`, the server's answer is fetched and handed to it before the page
 * gets it: what a journey reads of an answer the page has not drawn yet. Under `every` the route
 * stays registered until the page closes, so with `onAnswer` as well it fetches every later
 * request it matches with `route.fetch`, the teardown's own included: the route P19b-7 met on
 * Windows. Combine the two only for a path the page never asks on its own. For a state the page
 * shows while it waits (spec 2026-10-08 §5, "Loading states"): release in a `finally`, so that a
 * failed assertion never leaves the page waiting.
 */
export async function held(
  page: Page,
  matcher: Matcher,
  options: {
    every?: boolean;
    onAnswer?: (response: APIResponse) => void | Promise<void>;
  } = {},
): Promise<() => void> {
  let release = (): void => undefined;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  const { every = false, onAnswer } = options;
  await page.route(
    matching(matcher),
    async (route) => {
      await released;
      if (onAnswer === undefined) {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      await onAnswer(response);
      await route.fulfill({ response });
    },
    every ? {} : { times: 1 },
  );
  return release;
}

/** Longer than what a change of page leaves waiting waits at most, 3 s (`WAITS_AT_MOST_MS`,
 * lib/focus.ts). */
export const PAST_THE_WAITS = 4000;

/** GainA's panel on the Graph, and its link to Gain_t, the scalar type giving GainA its unit
 * (`namingAScalarType`): the Graph loaded at GainA's address, after the address ddd gui printed. */
export async function gainLink(page: Page, address: string): Promise<Locator> {
  await page.goto(address);
  const graph = new URL(page.url());
  graph.pathname = "/project";
  graph.search = "?variable=GainA";
  await page.goto(graph.href);
  const link = page
    .getByRole("complementary", { name: "GainA" })
    .getByRole("link", { name: "Gain_t" })
    .first();
  await expect(link).toBeVisible();
  return link;
}

/** Controller made to declare `count` scalar types more than it does, `Scale00_t` and on, each
 * naming nothing: enough of them stand the Types tab's table past a window's foot. */
export function moreScalarTypes(directory: string, count: number): void {
  const path = join(directory, CONTROLLER);
  const data = JSON.parse(readFileSync(path, "utf8"));
  data.component.types ??= [];
  for (let index = 0; index < count; index += 1) {
    data.component.types.push({
      type: "scalar",
      name: `Scale${String(index).padStart(2, "0")}_t`,
      description: "A scale, for a long table of types",
      datatype: "uint16",
      conversion: { factor: 1 },
    });
  }
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

/** A component of `name` declaring nothing, as its file holds it. */
export function emptyComponent(name: string): string {
  const data = { component: { name, description: `${name}, declaring nothing`, interface: [] } };
  return `${JSON.stringify(data, null, 2)}\n`;
}

/** `count` components more in the demo's own `components/*.ddd.json` pattern, `Extra00` and on,
 * each declaring nothing: rows enough to fill the Files tab's table box. */
export function moreComponents(directory: string, count: number): void {
  for (let index = 0; index < count; index += 1) {
    const name = `Extra${String(index).padStart(2, "0")}`;
    writeFileSync(
      join(directory, "components", `${name.toLowerCase()}.ddd.json`),
      emptyComponent(name),
    );
  }
}

/** Waits two of the page's frames: by then what it does once a change is drawn has run - its
 * effects, and what it watches of its own layout. */
export async function twoFrames(page: Page): Promise<void> {
  await page.evaluate(
    () =>
      new Promise<void>((done) => {
        requestAnimationFrame(() => requestAnimationFrame(() => done()));
      }),
  );
}

/**
 * Turns the mouse's wheel by `deltaX` and `deltaY` px where the pointer stands, and goes on only once
 * the page has had the wheel's event: the browser hands a wheel to the page on its own timing - on
 * Windows, after the turn has returned, and after what a journey does next - so a journey whose
 * claim is about what the page does once the reader has turned the wheel waits for the page to have
 * heard it.
 */
export async function wheeled(page: Page, deltaX: number, deltaY: number): Promise<void> {
  const listening = await page.evaluateHandle(() => ({
    heard: new Promise<void>((done) => {
      document.addEventListener("wheel", () => done(), {
        capture: true,
        once: true,
        passive: true,
      });
    }),
  }));
  await page.mouse.wheel(deltaX, deltaY);
  await listening.evaluate(({ heard }) => heard);
  await listening.dispose();
}

/**
 * A wheel the page turns itself from the moment the heading of the panel titled `title` takes the
 * focus: a wheel event at each of its next `frames` frames, dispatched in the frame's animation
 * callbacks - before the frame's layout and what watches the page's sizes, where the browser hands
 * the page a wheel turned by hand too. So the turn falls in the frames right after the focus,
 * whatever the platform's own timing of the wheel. A wheel event the page dispatches scrolls
 * nothing itself, as a wheel turned upward at the page's top. Set before what moves the focus;
 * answers what waits until the last of those events has been dispatched.
 */
export async function wheelFromFocus(
  page: Page,
  title: string,
  frames: number,
): Promise<() => Promise<void>> {
  const turning = await page.evaluateHandle(
    ({ title, frames }) => ({
      over: new Promise<void>((done) => {
        const start = (event: FocusEvent) => {
          const heading = event.target;
          if (!(heading instanceof HTMLElement) || heading.dataset.heading !== "panel") return;
          if (heading.textContent !== title) return;
          document.removeEventListener("focusin", start, true);
          let left = frames;
          const turn = () => {
            const under = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
            (under ?? document.body).dispatchEvent(
              new WheelEvent("wheel", { deltaY: -100, bubbles: true, cancelable: true }),
            );
            left -= 1;
            if (left > 0) requestAnimationFrame(turn);
            else done();
          };
          requestAnimationFrame(turn);
        };
        document.addEventListener("focusin", start, true);
      }),
    }),
    { title, frames },
  );
  return async () => {
    await turning.evaluate(({ over }) => over);
    await turning.dispose();
  };
}

/**
 * Moves `file`'s modification time to now and changes none of its bytes. The watcher compares a
 * file's `(st_mtime_ns, st_size)` alone (`stamped` and `poll`, session.py), so its next poll
 * reads a new revision, and the server's long poll, which would otherwise wait out its
 * `WAIT_SECONDS`, answers at once (P19b-9). For a journey that needs the next revision now: one
 * whose reads it fails, or the state read after it failed.
 */
export function restamp(directory: string, file: string): void {
  const now = new Date();
  utimesSync(join(directory, file), now, now);
}
