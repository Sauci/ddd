import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator } from "@playwright/test";
import {
  CONTROLLER,
  driftMaxUnseen,
  type Frame,
  failing,
  framesWatched,
  held,
  openValues,
  paste,
  restamp,
  SENSOR_HUB,
  SERVER_FAILED,
  scrolledIntoView,
  typeCurveA,
  USER_INTERFACE,
  watchFrames,
  widenBlockA,
  withinBox,
  writeBlockAInit,
} from "./demo";
import { expect, test } from "./fixtures";

/** A declaration's own definition, read back from a file of the copy - the same untyped shape
 * findings.spec.ts's own `valueH` reads a declaration's definition as. */
function definitionOf(directory: string, file: string, name: string) {
  const data = JSON.parse(readFileSync(join(directory, file), "utf8"));
  return data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === name,
  ).definition;
}

/** Each of a single row's own cells, left to right - `elementLabel`'s own one-based aria-labels,
 * checked one at a time rather than as one collection: `toHaveValues` is for a `<select>`'s own
 * chosen options, not a set of plain `<input>`s, and strict-mode-violates on six of them. */
async function expectRow(grid: Locator, values: readonly string[]): Promise<void> {
  for (const [index, value] of values.entries()) {
    await expect(grid.getByRole("textbox", { name: `element ${index + 1}` })).toHaveValue(value);
  }
}

/** ValueB's own `"init": 0,` taken out of SensorHub, the one declaration producing it: a shaped
 * object stating nothing, which the startup code zeroes. */
function stateNothingOfValueB(directory: string): void {
  const path = join(directory, SENSOR_HUB);
  const text = readFileSync(path, "utf8");
  const changed = text.replace(/("name": "ValueB"[\s\S]*?)\n\s*"init": 0,/, "$1");
  if (changed === text) throw new Error(`${SENSOR_HUB} states no init of ValueB`);
  writeFileSync(path, changed, "utf8");
}

/** SensorHub's declaration of ValueB taken out, the file rewritten whole: Controller and
 * UserInterface still read ValueB, and nothing produces it. */
function producedByNobody(directory: string): void {
  const path = join(directory, SENSOR_HUB);
  const data = JSON.parse(readFileSync(path, "utf8"));
  const kept = data.component.interface.filter(
    (declaration: { definition: { name: string } }) => declaration.definition.name !== "ValueB",
  );
  if (kept.length !== data.component.interface.length - 1) {
    throw new Error(`${SENSOR_HUB} declares ValueB other than once`);
  }
  data.component.interface = kept;
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

/** UserInterface's reading of ValueB made a second producing declaration of it, beside
 * SensorHub's. */
function producedTwice(directory: string): void {
  const path = join(directory, USER_INTERFACE);
  const text = readFileSync(path, "utf8");
  const changed = text.replace(
    /"scope": "input",(\s*"definition": \{\s*"name": "ValueB")/,
    '"scope": "output",$1',
  );
  if (changed === text) throw new Error(`${USER_INTERFACE} reads no ValueB`);
  writeFileSync(path, changed, "utf8");
}

test("a curve is read against its axis, raw and physical", async ({ page, gui }) => {
  await openValues(page, gui.address, "CurveA");

  const grid = page.getByRole("grid", { name: "Values of CurveA" });
  // Spec 5.2's own sketch, labels and all: `AxisA (Hz)` over the breakpoints, `CurveA (ms)`
  // beside the values - the header converting by the axis's rule and the values by the
  // object's, which is the one thing that says which unit belongs to which edge.
  await expect(grid.getByRole("columnheader")).toHaveText([
    "AxisA (Hz)",
    "0",
    "800",
    "1600",
    "3200",
    "4800",
    "8000",
  ]);
  await expect(grid.getByRole("rowheader")).toHaveText(["CurveA (ms)"]);
  await expectRow(grid, ["12", "9", "8", "7.5", "7", "6.5"]);

  await page.getByRole("button", { name: "Raw" }).click();
  // The same two labels, without their units: these readings are counts, and `(Hz)` over
  // `0, 3200, 6400` or `(ms)` beside `1200, 900, 800` would be a label the numbers contradict.
  await expect(grid.getByRole("columnheader")).toHaveText([
    "AxisA",
    "0",
    "3200",
    "6400",
    "12800",
    "19200",
    "32000",
  ]);
  await expect(grid.getByRole("rowheader")).toHaveText(["CurveA"]);
  await expectRow(grid, ["1200", "900", "800", "750", "700", "650"]);
});

// Part 10's own journey: `valuePlot.test.ts` calls `plotted()` straight, and a Ladle story
// renders it, but neither drives a served reply through a browser - so neither can tell a
// `<polyline>` built from `reply.rows` apart from one that only looks like it was.
test("a curve is drawn from the numbers it holds", async ({ page, gui }) => {
  await openValues(page, gui.address, "CurveA");

  // `role="img"`'s own name drops "(Hz)" and "(ms)" in Raw the way the grid's own headers do
  // (spec 5.2, `ValuesPlotView.tsx`), so matching the fragment both keep - "plotted against
  // AxisA" - is what this locator survives the toggle below on, without re-querying the page.
  const plot = page.getByRole("img", { name: "plotted against AxisA" });
  const polyline = plot.locator("polyline");
  // Read once off this served copy of examples/demo and pinned literally, not recomputed from
  // BOX and AxisA's own breakpoints: a test that repeats valuePlot.ts's own arithmetic passes
  // even where both share the same mistake. The first pair sits at x = 56 - BOX.left itself -
  // because AxisA's first breakpoint (0 Hz) is the lowest of its six; the last at x = 624 -
  // BOX.width (640) less BOX.right (16), not BOX.width itself - because AxisA's last (8000 Hz)
  // is the highest. Between them, the six y's place CurveA's own 12, 9, 8, 7.5, 7, 6.5 ms.
  const physicalPoints =
    "56,15.454545454545467 112.80000000000001,96.77685950413223 " +
    "169.60000000000002,123.88429752066115 283.20000000000005,137.43801652892563 " +
    "396.8,150.99173553719007 624,164.54545454545453";
  await expect(polyline).toHaveAttribute("points", physicalPoints);
  await expect(plot.locator(".values-plot-tick")).toHaveText([
    "0",
    "800",
    "1600",
    "3200",
    "4800",
    "8000",
  ]);
  await expect(plot.locator(".values-plot-side")).toHaveText(["12.275", "6.225"]);

  await page.getByRole("button", { name: "Raw" }).click();
  // What the toggle actually redraws, in text a reader can see: AxisA's own ticks (its raw
  // breakpoints rather than what its conversion makes of them) and the two side readings (the
  // padded range of CurveA's own raw counts rather than of what its conversion makes of them).
  //
  // The polyline's own `points` are deliberately not re-asserted here. The plot scales to its own
  // range (`rangeOf`, `placed` in valuePlot.ts), so the same six numbers in a different unit are
  // the same shape: low, high and every value between them move by the same factor, and a
  // coordinate is placed by the ratio between them, which that factor cancels out of. Reading
  // `points` again after this toggle, on this served page, does turn up a change - but only in
  // the thirteenth decimal of two of the six y's, from CurveA's own 0.01 conversion factor not
  // being an exact binary fraction the way AxisA's 0.25 is (which is why every x above is
  // bit-for-bit identical either way). That is real, but it is not what this toggle is for, and a
  // test asserting it would be asserting rounding noise rather than the picture.
  await expect(plot.locator(".values-plot-tick")).toHaveText([
    "0",
    "3200",
    "6400",
    "12800",
    "19200",
    "32000",
  ]);
  await expect(plot.locator(".values-plot-side")).toHaveText(["1227.5", "622.5"]);
});

test("a cell changed is written to the producer's file", async ({ page, gui }) => {
  await openValues(page, gui.address, "CurveA");

  await page.getByRole("textbox", { name: "element 3" }).fill("7.5");
  await expect(page.getByText("Sets element 3 of CurveA to 7.5 ms")).toBeVisible();
  // Named before Show changes is opened, as spec 5.3 asks and as every sibling write path
  // already does: an object's numbers live in its producer's file, which the reader is not
  // always looking at.
  await expect(page.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
  await page.getByRole("button", { name: "Show changes" }).click();
  await expect(page.getByText('"init": [1200, 900, 750, 750, 700, 650],')).toBeVisible();

  await page.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect
    .poll(() => readFileSync(join(gui.directory, CONTROLLER), "utf8"))
    .toContain('"init": [1200, 900, 750, 750, 700, 650]');
});

/** Whether the page has taken in the analysis of its own edit and stood on it for the last thirty
 * frames watched - half a second at sixty frames a second: in each, it offers to undo the edit,
 * which only a state from after the edit does, and says nothing is updating, which with such a
 * state it says once the analysis including the edit has come. Not whether it was seen to say
 * "Updating the findings…" first: that can come and go between two frames (below). */
function settledAfterTheEdit(frames: readonly Frame[]): boolean {
  const last = frames.slice(-30);
  return last.length === 30 && last.every(([, updating, offered]) => offered && !updating);
}

// Spec 6: an edit is answered once written and analysed after, and `GET /api/values` answers what
// the last analysis read - for one analysis after an Apply it still answers the value from before,
// as though the Apply had failed. The grid holds what it wrote meanwhile. Waited on as a reader
// sees it, frame by frame: element 3 reads 7.5 from Apply on - while the grid says its findings are
// updating, and after - and never the 8 it was. With the hold taken out, on the Linux development
// PC in headless Chrome, ten runs: the note stood four frames (five in one), and element 3 read 8
// in three of them in every run. The wait is for the analysis to have come, not for the note to
// have been seen: on the same PC, in 80 runs of these steps, the edit's analysis took 2.5 to 6.1
// ms, and in 8 runs the note stood 3.6 to 12.2 ms in the page, between two frames, and no frame
// painted it.
test("a value applied in the grid shows at once, and stays while its findings update", async ({
  page,
  gui,
}) => {
  await openValues(page, gui.address, "CurveA");
  const cell = page.getByRole("textbox", { name: "element 3" });
  await expect(cell).toHaveValue("8");
  await cell.fill("7.5");
  await expect(page.getByText("Sets element 3 of CurveA to 7.5 ms")).toBeVisible();

  await watchFrames(page, "element 3", "element 3 of CurveA");
  await page.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect.poll(async () => settledAfterTheEdit(await framesWatched(page))).toBe(true);
  const read = new Set((await framesWatched(page)).map(([value]) => value));
  expect(read).toEqual(new Set(["7.5"]));
});

test("a reader's page names the producer's file, not its own", async ({ page, gui }) => {
  // Spec 5.3's own example: ValueB on Controller is an `input`, its numbers live in SensorHub,
  // and the preview names sensor_hub.ddd.json. Nothing is applied here - the sentence before
  // Apply is the whole subject.
  const before = readFileSync(join(gui.directory, SENSOR_HUB));
  await openValues(page, gui.address, "ValueB");

  await page.getByRole("textbox", { name: "element 1" }).fill("1");
  await expect(page.getByText("Sets element 1 of ValueB to 1 V")).toBeVisible();
  await expect(page.getByText("Changes 1 file: sensor_hub.ddd.json")).toBeVisible();
  expect(readFileSync(join(gui.directory, SENSOR_HUB)).equals(before)).toBe(true);
});

test("a map's cell names its row and its column", async ({ page, gui }) => {
  await openValues(page, gui.address, "MapA");

  const grid = page.getByRole("grid", { name: "Values of MapA" });
  await expect(grid.getByRole("rowheader")).toHaveText(["0", "30", "70", "100"]);
  // Spec 5.2's map sketch: AxisB (%) down the side, in the corner above its own readings, and
  // AxisA (Hz) across the top, above the columns it lays them against.
  await expect(grid.getByRole("columnheader").first()).toHaveText("AxisB (%)");
  await expect(page.getByText("AxisA (Hz) →")).toBeVisible();

  await page.getByRole("button", { name: "Raw" }).click();
  await expect(page.getByText("AxisA →")).toBeVisible();
  await page.getByRole("textbox", { name: "element 2, 4" }).fill("50");
  await expect(page.getByText("Sets element 2, 4 of MapA to 50")).toBeVisible();
  await page.getByRole("button", { name: "Apply to 1 file" }).click();

  await expect.poll(() => definitionOf(gui.directory, CONTROLLER, "MapA").init[1][3]).toBe(50);
});

test("a physical value no raw count represents shows what was stored", async ({ page, gui }) => {
  await openValues(page, gui.address, "CurveA");

  await page.getByRole("textbox", { name: "element 1" }).fill("12.004");
  await expect(page.getByText("Sets element 1 of CurveA to 12 ms")).toBeVisible();
  await page.getByRole("button", { name: "Apply to 1 file" }).click();

  await expect(page.getByRole("textbox", { name: "element 1" })).toHaveValue("12");
  await expect.poll(() => definitionOf(gui.directory, CONTROLLER, "CurveA").init[0]).toBe(1200);
});

test("a value the datatype cannot hold is refused, and nothing is written", async ({
  page,
  gui,
}) => {
  const before = readFileSync(join(gui.directory, CONTROLLER));
  await openValues(page, gui.address, "CurveA");
  await page.getByRole("button", { name: "Raw" }).click();

  // Not a number at all first: a decimal comma is what half the world types, and reading the
  // numeric prefix of it would plan a write of 1 with no refusal at all.
  await page.getByRole("textbox", { name: "element 1" }).fill("1,5");
  await expect(page.getByText("'1,5' is not a number")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  await page.getByRole("textbox", { name: "element 1" }).fill("70000");
  await expect(page.getByText("70000 does not fit into uint16 (0 .. 65535)")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
});

test("Enter settles what was typed and writes nothing", async ({ page, gui }) => {
  // Spec 5.3: "Type, press Enter, and the grid shows … the sentence … then `Show changes` and
  // `Apply to 1 file` … No cell writes on its own." Enter used to apply, so a reader finishing
  // a number the way every other field in this interface trains them to wrote the file without
  // ever pressing Apply. The preview still standing afterwards is itself the evidence: an
  // apply clears the cell being edited, and the offer with it.
  const before = readFileSync(join(gui.directory, CONTROLLER));
  await openValues(page, gui.address, "CurveA");

  const cell = page.getByRole("textbox", { name: "element 3" });
  await cell.fill("7.5");
  await cell.press("Enter");
  await expect(page.getByText("Sets element 3 of CurveA to 7.5 ms")).toBeVisible();
  const apply = page.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeVisible();
  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);

  // And the button that does write still writes, from the very same settled cell.
  await apply.click();
  await expect
    .poll(() => readFileSync(join(gui.directory, CONTROLLER), "utf8"))
    .toContain('"init": [1200, 900, 750, 750, 700, 650]');
});

test("a cell changed is put back", async ({ page, gui }) => {
  const before = readFileSync(join(gui.directory, CONTROLLER));
  await openValues(page, gui.address, "CurveA");

  await page.getByRole("textbox", { name: "element 3" }).fill("7.5");
  await page.getByRole("button", { name: "Apply to 1 file" }).click();

  const undo = page.getByRole("button", { name: "Undo element 3 of CurveA" });
  await expect(undo).toBeVisible();
  await undo.click();
  const strip = page.getByRole("region", { name: "Undo" });
  await expect(strip.getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
  await strip.getByRole("button", { name: "Put back 1 file" }).click();

  await expect.poll(() => readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
});

test("a value applied from a file that changed on disk is refused, and applied once the page has caught up", async ({
  page,
  gui,
}) => {
  await openValues(page, gui.address, "CurveA");
  await page.getByRole("textbox", { name: "element 3" }).fill("7.5");
  const apply = page.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeEnabled();

  // Controller changes under the plan the grid holds, unseen by the session's watcher, as
  // keys.spec.ts's own stale journey changes it: only the Apply's own fingerprint check sees it.
  const path = join(gui.directory, CONTROLLER);
  driftMaxUnseen(gui.directory, CONTROLLER, "ValueA", 999);
  const drifted = readFileSync(path);
  await apply.click();
  const setting = page.getByRole("region", { name: "Set the cell" });
  await expect(setting.getByRole("status")).toHaveText(
    "A file changed on disk, so nothing was written. The page now shows the files as they are.",
  );
  expect(readFileSync(path).equals(drifted)).toBe(true);

  // A stamp moved with no byte touched lets the next poll read the drifted file; the refusal is
  // held until the analysis moves on, and goes with it, the cell still being typed into.
  restamp(gui.directory, CONTROLLER);
  await expect(setting.getByRole("status")).toHaveCount(0, { timeout: 15000 });
  await apply.click();
  await expect
    .poll(() => readFileSync(path, "utf8"))
    .toContain('"init": [1200, 900, 750, 750, 700, 650]');
});

// Part 9's own five: a table pasted from a spreadsheet replaces every value of an object in one
// edit, the way `paste` (demo.ts) delivers one - a `DataTransfer` dispatched as a real `paste`
// event, since Playwright cannot put a table on the system clipboard.

/** The five-row block a reader would copy from MapA's own Raw grid: AxisA's breakpoints across
 * the top, AxisB's down the side, and 1..24 filled in underneath in row-major order - so the
 * file's first row and its last come to exactly `[1, 2, 3, 4, 5, 6]` and
 * `[19, 20, 21, 22, 23, 24]`. `pasted()` only counts the header's shape and drops its text
 * (`objectValues.ts`'s own `header ? cells.slice(1).map((row) => row.slice(1))`), so what the
 * corner and the breakpoints actually read makes no difference to the parse - they are spelled
 * out here only so the block reads like one a spreadsheet would hand back. */
const MAP_A_PASTE = [
  "AxisB\t0\t3200\t6400\t12800\t19200\t32000",
  "0\t1\t2\t3\t4\t5\t6",
  "60\t7\t8\t9\t10\t11\t12",
  "140\t13\t14\t15\t16\t17\t18",
  "200\t19\t20\t21\t22\t23\t24",
].join("\n");

/** MapA's own shape (4 rows of 6), three cells of the first row three ways over what sint8
 * holds - columns 1, 3 and 6 - and every other cell in range, so the server's refusal names
 * exactly those three and nothing else drags a fourth offender into the sentence. */
const MAP_A_OVER_RANGE = [
  "200\t1\t300\t1\t1\t400",
  "1\t1\t1\t1\t1\t1",
  "1\t1\t1\t1\t1\t1",
  "1\t1\t1\t1\t1\t1",
].join("\n");

// A stale-failure regression - a cell apply failed for a reason other than staleness, then a
// table pasted over it, asserting no trace of the old failure remains - is not folded into this
// journey. The out-of-range cell above ("a value the datatype cannot hold is refused, and nothing
// is written") cannot reach one: `_value_plan` (`api.py`) runs `set_cell`'s own range check before
// ever answering a plan, so a value out of range never renders an `Apply to` button at all - that
// test's own `toHaveCount(0)` is exactly this - and `apply.mutate()`, the only place
// `ValuesPage.tsx` sets its non-stale `failed`, is never reached. Nothing reachable through a
// cell's own Apply button fails non-stale without the file also changing underneath it, which is
// staleness itself, unless the server is made to fail on the Apply's own request: the mechanism
// of "a cell's apply the server fails on says so in its words, keeps its Apply, and is sent once",
// further down this file. It stops at that refusal: no journey pastes a table over it.
test("a pasted curve replaces every value in one edit", async ({ page, gui }) => {
  await openValues(page, gui.address, "CurveA");

  await paste(page, "12.004\t9.5\t8.5\t8\t7.5\t7");
  await expect(page.getByText("Replaces every value of CurveA")).toBeVisible();
  await expect(page.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();

  await page.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect
    .poll(() => readFileSync(join(gui.directory, CONTROLLER), "utf8"))
    .toContain('"init": [1200, 950, 850, 800, 750, 700]');
  // Spec 4.1: 12.004 has no raw count of its own - stored as the nearest one, 1200, then shown
  // as what was stored. `values.spec.ts:118`'s own single-cell journey already makes this claim
  // for a typed cell; nothing before this re-read the grid after a paste to make it true of one.
  await expect(page.getByRole("textbox", { name: "element 1" })).toHaveValue("12");
  await expect(page.getByRole("button", { name: "Undo the values of CurveA" })).toBeVisible();
});

test("a pasted map takes its header row and column", async ({ page, gui }) => {
  await openValues(page, gui.address, "MapA");
  await page.getByRole("button", { name: "Raw" }).click();

  await paste(page, MAP_A_PASTE);
  await page.getByRole("button", { name: "Apply to 1 file" }).click();

  await expect
    .poll(() => definitionOf(gui.directory, CONTROLLER, "MapA").init[0])
    .toEqual([1, 2, 3, 4, 5, 6]);
  expect(definitionOf(gui.directory, CONTROLLER, "MapA").init[3]).toEqual([19, 20, 21, 22, 23, 24]);
});

test("a block of the wrong shape is refused and nothing is written", async ({ page, gui }) => {
  const before = readFileSync(join(gui.directory, CONTROLLER));
  await openValues(page, gui.address, "CurveA");

  await paste(page, ["1\t2\t3\t4\t5\t6", "7\t8\t9\t10\t11\t12"].join("\n"));
  await expect(
    page.getByText("expected 1 row of 6, or 2 rows of 7 with a header; got 2 rows of 6"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
});

test("a value the datatype cannot hold names every offender", async ({ page, gui }) => {
  const before = readFileSync(join(gui.directory, CONTROLLER));
  await openValues(page, gui.address, "MapA");
  await page.getByRole("button", { name: "Raw" }).click();

  await paste(page, MAP_A_OVER_RANGE);
  await expect(
    page.getByText(
      "3 elements of 'MapA' are refused: " +
        "element 1, 1 because 200 does not fit into sint8 (-128 .. 127); " +
        "element 1, 3 because 300 does not fit into sint8 (-128 .. 127); " +
        "element 1, 6 because 400 does not fit into sint8 (-128 .. 127)",
    ),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
});

test("a pasted table is put back", async ({ page, gui }) => {
  const before = readFileSync(join(gui.directory, CONTROLLER));
  await openValues(page, gui.address, "CurveA");

  await paste(page, "13\t9.5\t8.5\t8\t7.5\t7");
  await page.getByRole("button", { name: "Apply to 1 file" }).click();

  const undo = page.getByRole("button", { name: "Undo the values of CurveA" });
  await expect(undo).toBeVisible();
  await undo.click();
  const strip = page.getByRole("region", { name: "Undo" });
  await expect(strip.getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
  await strip.getByRole("button", { name: "Put back 1 file" }).click();

  await expect.poll(() => readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
});

// Beyond the brief's six: examples/demo carries no finding on its own, so this one is built from
// outside - BlockA's own init pushed past what a uint8 holds, saved from outside the page as
// every fixture above is, the way the six journeys' own drift would be. This is the one route a
// screenshot cannot draw and no Vitest may touch: `ComponentPage.tsx`'s own findings list must
// send a same-file `values`-kind finding to the grid rather than let its in-place shortcut open
// the variable's panel instead.
test("a finding on an object's init leads to its grid, not its panel", async ({ page, gui }) => {
  writeBlockAInit(gui.directory, [0, 12, 28, 52, 84, 124, 180, 9999]);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "UserInterface", exact: true }).click();

  const finding = page.getByRole("link", {
    name: "init value 9999 does not fit into uint8 (0 .. 255)",
  });
  await expect(finding).toBeVisible();
  await finding.click();

  await expect(page).toHaveURL(/\/component\?file=[^&]+&variable=BlockA&view=values$/);
  await expect(page.getByRole("heading", { name: "BlockA", level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: "Back to UserInterface" })).toBeVisible();
  const grid = page.getByRole("grid", { name: "Values of BlockA" });
  await expectRow(grid, ["0", "12", "28", "52", "84", "124", "180", "9999"]);
  // The finding the reader followed is drawn on the grid too, which is what carrying it
  // through `ValuesReply.findings` is for - and what this journey rendered without asserting.
  await expect(page.getByText("init value 9999 does not fit into uint8 (0 .. 255)")).toBeVisible();
});

// A shape no grid draws, reached the only two ways there are to reach it - the address, and a
// finding on its own init - since the Shape column offers no button for one. Both the refusal
// and the way out of it are the subject: a refusal that left the reader on an empty page with
// a sentence would be its own dead end.
test("a shape deeper than a grid is shown, not offered, and says so with a way back", async ({
  page,
  gui,
}) => {
  widenBlockA(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "UserInterface", exact: true }).click();

  // Plain text in the Shape column, not a button onto a grid that refuses the moment it opens.
  await expect(page.getByRole("button", { name: "Show the values of BlockA" })).toHaveCount(0);
  await expect(page.getByRole("gridcell", { name: "2 × 2 × 2" })).toBeVisible();

  await page
    .getByRole("link", { name: "init value 9999 does not fit into uint8 (0 .. 255)" })
    .click();
  await expect(page.getByRole("heading", { name: "BlockA", level: 1 })).toBeVisible();
  await expect(
    page.getByText("'BlockA' has 3 dimensions, and a grid draws at most two"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Back to UserInterface" }).click();
  await expect(page.getByRole("grid", { name: "Declarations of UserInterface" })).toBeVisible();
});

// The other side of that rule, and the one nothing in examples/ has: a curve naming a type
// rather than stating its own storage. It is still a numeric table - its shape follows from its
// axis and the type it names is a scalar one - so it is still offered, and the grid it opens
// draws exactly the readings it drew before the type was named.
test("a curve naming a scalar type keeps its button, and its grid", async ({ page, gui }) => {
  typeCurveA(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();

  // CurveA is the thirteenth of Controller's fourteen declarations: its own row is inside the
  // box's own visible rect at this viewport (measured, its own top 3px above the box's own
  // bottom), but the Shape button inside it is not - clipped by the box's own overflow a few
  // pixels further down the row than its own top is (fix round 1, Important 5; fix round 2
  // corrected this - the row is not drawn "only through overscan", whole or at all). Scrolled to
  // before either cell of its row is asked for, not after.
  const button = page.getByRole("button", { name: "Show the values of CurveA" });
  await scrolledIntoView(page, "Declarations of Controller", button);
  // The Type cell reads the type, since there is no datatype of its own to read.
  await expect(page.getByRole("gridcell", { name: "Millis_t" })).toBeVisible();
  await button.click();

  const grid = page.getByRole("grid", { name: "Values of CurveA" });
  await expect(grid.getByRole("rowheader")).toHaveText(["CurveA (ms)"]);
  await expectRow(grid, ["12", "9", "8", "7.5", "7", "6.5"]);
});

// `scroll-padding-top` pinned a second way (fix round 2, New Minor 4): the stylesheet test beside
// `.findings-window`'s own (findingsWindow.test.ts) checks the rule is written; this walks it with
// the keyboard. At this viewport the box is 432px tall, and Controller's header and fourteen rows
// 495px, so Control+End leaves the box scrolled to its end, 63px: the second row, ValueB, whose
// top is at 66px, is then drawn 3px below the box's own top - inside the scrolled view, under the
// 33px sticky header. Twelve ArrowUps walk the focus from the fourteenth row (MapA) to it. Every
// row on the way is clear of the header, so React Aria's scroll to the focused row moves the box
// for ValueB alone, and only with the rule: `scroll-padding-top` moves the top of the box's scroll
// port down below the header, so ValueB counts as out of view and is scrolled to just below the
// header (to 33px); without it, ValueB counts as in view and stays under the header. Not
// Control+Home: that scrolls the box to 0, where the first row sits below the header, rule or no
// rule.
test("a row walked back up near the top stops below the sticky header, not under it", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const grid = page.getByRole("grid", { name: "Declarations of Controller" });
  const header = grid.getByRole("columnheader").first();
  const lastRow = grid.getByRole("row").last();
  const walkedRow = page.getByRole("row", { name: /ValueB/ });
  // Focused, not clicked: a click would also select the row, opening its own panel, which
  // narrows the table and races the walk below over the same frame.
  await lastRow.evaluate((node) => (node as HTMLElement).focus());
  await page.keyboard.press("Control+End");
  // Control+End moves the box by Chrome's own smooth scroll, about 150ms long: React Aria leaves
  // End's default alone in a table that selects by toggling, and a key held with Control never
  // sets its keyboard modality, so it scrolls nothing itself. MapA is drawn - the Virtualizer's
  // overscan - before that scroll even starts, so the walk waits instead for MapA to sit whole
  // inside the box, which it does only once the box stands at its end. Started sooner, the
  // ArrowUps race the smooth scroll, which can carry ValueB under the header after the walk has
  // reached it.
  await expect.poll(() => withinBox(page, "Declarations of Controller", lastRow)).toBe(true);
  for (let step = 0; step < 12; step += 1) await page.keyboard.press("ArrowUp");
  // Polled, not read once: React Aria scrolls a newly focused row into view in an animation frame
  // after the key that focused it, not while it handles the key.
  await expect
    .poll(async () => {
      const headerBottom = await header.evaluate((node) => node.getBoundingClientRect().bottom);
      const rowTop = await walkedRow.evaluate((node) => node.getBoundingClientRect().top);
      return rowTop - headerBottom;
    })
    .toBeGreaterThanOrEqual(-1);
});

test("the values grid says it is reading the values until they are read", async ({ page, gui }) => {
  // Only the values page asks for an object's grid (`getValues`): `/api/value-plan` and
  // `/api/values-plan` are other pathnames. Held from before the page opens, it is the read this
  // journey is about.
  const release = await held(page, "/api/values");
  const reading = page.getByText("Reading the values…", { exact: true });
  try {
    await openValues(page, gui.address, "CurveA");
    // The line stands alone: no heading and no way back until the grid is read.
    await expect(reading).toBeVisible();
    await expect(page.getByRole("heading", { name: "CurveA" })).toHaveCount(0);
  } finally {
    release();
  }
  const grid = page.getByRole("grid", { name: "Values of CurveA" });
  await expect(grid.getByRole("rowheader")).toHaveText(["CurveA (ms)"]);
  await expect(reading).toHaveCount(0);
});

test("the values failing to load leave the server's own error, under the heading and beside the way back", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, "/api/values", "http");
  await openValues(page, gui.address, "CurveA");

  // A first read that fails shows the error alone, but for what every refusal of this page keeps:
  // the heading the reader opened and the way back (spec 5.4).
  await expect(page.getByRole("heading", { name: "CurveA", level: 1, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Back to Controller", exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(page.getByRole("grid", { name: "Values of CurveA" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Physical", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Raw", exact: true })).toHaveCount(0);
  expect(failed()).toBeGreaterThanOrEqual(1);
});

// An object renamed from outside while its grid is open: the grid's next read, keyed by the new
// revision, asks the server for a name the project no longer has. The page keeps what the reader
// opened - its heading - and says why there is nothing under it, with the way back that the
// heading row always carries (spec 5.4: every refusal keeps the heading and the way back).
test("an object renamed under its open grid is said to be declared no longer, with the way back to its component", async ({
  page,
  gui,
}) => {
  await openValues(page, gui.address, "CurveA");
  const grid = page.getByRole("grid", { name: "Values of CurveA" });
  await expect(grid.getByRole("rowheader")).toHaveText(["CurveA (ms)"]);

  // Written plainly, so that the watcher sees it, under a name of another length: the size moves
  // as well as the stamp (`stamped`, session.py). Nothing else in examples/demo names CurveA, so
  // the project still loads clean and the rename is the only change the next revision brings.
  const path = join(gui.directory, CONTROLLER);
  const text = readFileSync(path, "utf8");
  const renamed = text.replace('"name": "CurveA"', '"name": "CurveGone"');
  if (renamed === text) throw new Error(`${CONTROLLER} names no CurveA`);
  writeFileSync(path, renamed, "utf8");

  // The server's own refusal, in its words (`grid_of`, object_values.py, answered 404 by
  // `Api._values`): the one alert on the page, under the heading the reader opened, with the grid
  // gone - a refusal is never kept (`refusedRead`), so the grid of the revision before does not
  // stay beside it: it would offer cells of an object the project no longer has.
  await expect(page.getByRole("alert")).toHaveText("the project declares no 'CurveA'");
  await expect(page.getByRole("heading", { name: "CurveA", level: 1, exact: true })).toBeVisible();
  await expect(grid).toHaveCount(0);

  // The way back names the component the grid was opened from - read from the state's own list of
  // files, not from the object, which is gone - and leads to it, where the renamed declaration is.
  const back = page.getByRole("button", { name: "Back to Controller", exact: true });
  await expect(back).toBeVisible();
  await back.click();
  await expect(page).toHaveURL(/\/component\?file=[^&]+$/);
  await expect(
    page.getByRole("heading", { name: "Controller", level: 1, exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("grid", { name: "Declarations of Controller" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a shapeless declaration opened by its values address says it has no cell, with the way back", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page).toHaveURL(/\/component\?file=[^&]+$/);
  // The component's address as the page spells it, the file in it as it spells every file, so that
  // the way back finds the component by it.
  const component = page.url();

  // The address a values route is written as (`hrefOf`, lib/route.ts), for a declaration no
  // button of the Shape column offers a grid of: ValueA is a scalar. This tab's token is in local
  // storage, so the page is signed in.
  await page.goto(`${component}&variable=ValueA&view=values`);
  await expect(page.getByRole("heading", { name: "ValueA", level: 1, exact: true })).toBeVisible();
  await expect(
    page.getByText("'ValueA' has no cell for a value to sit in", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("grid")).toHaveCount(0);

  const back = page.getByRole("button", { name: "Back to Controller", exact: true });
  await expect(back).toBeVisible();
  await back.click();
  await expect(
    page.getByRole("heading", { name: "Controller", level: 1, exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("grid", { name: "Declarations of Controller" })).toBeVisible();
});

test("an object initialised with text says so on its values page, which only a reader offers", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  // Controller produces StateName and states its text itself (`"init": "OFF"`), so its own row
  // offers no grid: the Shape cell reads 16 as plain text.
  await expect(page.getByRole("rowheader", { name: "StateName", exact: true })).toBeVisible();
  await expect(
    page.getByRole("row", { name: "StateName", exact: true }).getByRole("gridcell", {
      name: "16",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Show the values of StateName" })).toHaveCount(0);

  // UserInterface reads it and states no init - a reader cannot see its producer's - so its row
  // offers the grid, and the grid it opens says what the producer wrote.
  await openValues(page, gui.address, "StateName", "UserInterface");
  await expect(
    page.getByRole("heading", { name: "StateName", level: 1, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("'StateName' is initialised with text, not with a grid", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("grid", { name: "Values of StateName" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Physical", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Raw", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Back to UserInterface" })).toBeVisible();
});

test("a grid that states nothing reads zero, greyed, says so, and takes its first values", async ({
  page,
  copiedGui,
}) => {
  // ValueB's init taken out of SensorHub, its one producer, before the server starts: the grid is
  // of a shaped object that states nothing, which the startup code zeroes (`_filled`).
  const gui = await copiedGui("demo", stateNothingOfValueB);
  await openValues(page, gui.address, "ValueB");
  const grid = page.getByRole("grid", { name: "Values of ValueB" });
  await expectRow(grid, ["0", "0", "0", "0"]);
  for (const element of [1, 2, 3, 4]) {
    await expect(grid.getByRole("textbox", { name: `element ${element}` })).toHaveClass("unstated");
  }
  const nothing = page.getByText("Nothing is stated.", { exact: true });
  await expect(nothing).toBeVisible();
  // One producer, so the grid is writable and a paste is offered.
  await expect(
    page.getByText("Paste 1 row of 4 values from a spreadsheet to replace them all.", {
      exact: true,
    }),
  ).toBeVisible();

  await grid.getByRole("textbox", { name: "element 2" }).fill("1");
  await expect(page.getByText("Sets element 2 of ValueB to 1 V")).toBeVisible();
  await expect(page.getByText("Changes 1 file: sensor_hub.ddd.json")).toBeVisible();
  await page.getByRole("button", { name: "Apply to 1 file" }).click();
  // `set_cell` writes the whole `init` where none was written: the other cells keep their zeros.
  await expect
    .poll(() => definitionOf(gui.directory, SENSOR_HUB, "ValueB").init)
    .toEqual([0, 1000, 0, 0]);
  await expect(nothing).toHaveCount(0);
});

test("a grid stated once for every cell says so, and one cell set writes every value", async ({
  page,
  gui,
}) => {
  // UserInterface's CurveB states `"init": 200`, one number for its six cells.
  await openValues(page, gui.address, "CurveB", "UserInterface");
  const grid = page.getByRole("grid", { name: "Values of CurveB" });
  await expect(grid.getByRole("rowheader")).toHaveText(["CurveB (%)"]);
  // 200 raw counts, times the conversion's 0.5.
  await expectRow(grid, ["100", "100", "100", "100", "100", "100"]);
  const once = page.getByText("Stated once, for every cell.", { exact: true });
  await expect(once).toBeVisible();

  await grid.getByRole("textbox", { name: "element 3" }).fill("50");
  await expect(page.getByText("Sets element 3 of CurveB to 50 %")).toBeVisible();
  await expect(page.getByText("Changes 1 file: user_interface.ddd.json")).toBeVisible();
  await page.getByRole("button", { name: "Apply to 1 file" }).click();
  // `set_cell` writes the one number out as the list it stands for, with the cell set in it.
  await expect
    .poll(() => definitionOf(gui.directory, USER_INTERFACE, "CurveB").init)
    .toEqual([200, 200, 100, 200, 200, 200]);
  await expect(once).toHaveCount(0);
});

test("a grid nothing produces is read only, and says why", async ({ page, copiedGui }) => {
  // SensorHub's declaration of ValueB taken out before the server starts: Controller and
  // UserInterface still read it, and it resolves, with no owner and no file to set it in.
  const gui = await copiedGui("demo", producedByNobody);
  await openValues(page, gui.address, "ValueB");
  const grid = page.getByRole("grid", { name: "Values of ValueB" });
  await expect(grid.getByRole("textbox", { name: "element 1" })).toBeDisabled();
  await expect(
    page.getByText("nothing produces 'ValueB', so it has no values to set", { exact: true }),
  ).toBeVisible();
  // A grid with nothing to write into has nothing to paste into either.
  await expect(page.getByText(/^Paste /)).toHaveCount(0);
});

test("a grid more than one place produces is read only, and says why", async ({
  page,
  copiedGui,
}) => {
  // UserInterface's reading of ValueB made a producing declaration of it, beside SensorHub's: the
  // analysis reads one of them (an owner is named), the index holds both, so no one file is the
  // grid's.
  const gui = await copiedGui("demo", producedTwice);
  await openValues(page, gui.address, "ValueB");
  const grid = page.getByRole("grid", { name: "Values of ValueB" });
  await expect(grid.getByRole("textbox", { name: "element 1" })).toBeDisabled();
  await expect(
    page.getByText(
      "'ValueB' is produced in more than one place, so there is no one file to set it in",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page.getByText(/^Paste /)).toHaveCount(0);
});

test("a cell's apply the server fails on says so in its words, keeps its Apply, and is sent once", async ({
  page,
  gui,
}) => {
  const before = readFileSync(join(gui.directory, CONTROLLER));
  await openValues(page, gui.address, "CurveA");
  const cell = page.getByRole("textbox", { name: "element 3" });
  await cell.fill("7.5");
  await expect(page.getByText("Sets element 3 of CurveA to 7.5 ms")).toBeVisible();
  await expect(page.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
  const apply = page.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeEnabled();
  // Registered once the plan is drawn: `/api/value-plan`, which draws it, goes through either way.
  const failed = await failing(page, "/api/edit", "http");
  await apply.click();

  // `refusalOf`, through the grid's `onError`. The plan's own checks (the range, the shape) refuse
  // before an Apply is offered, so what reaches this one is the server failing on its request.
  await expect(page.getByRole("region", { name: "Set the cell" }).getByRole("status")).toHaveText(
    `The change was refused: ${SERVER_FAILED}`,
  );
  // The grid keeps its Apply and what was typed (P19b-24: the panels that write withdraw theirs).
  await expect(apply).toBeEnabled();
  await expect(cell).toHaveValue("7.5");
  // A guard against a write by another path: the POST is answered by `failing`, not the server.
  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
  // A POST is never sent again.
  expect(failed()).toBe(1);
});

test("a values address naming a file the project does not include still draws the grid, and goes back to the component", async ({
  page,
  gui,
}) => {
  // A component dropped from the project, its file still on disk: beside the project's own, where
  // the include `components/*.ddd.json` does not reach it.
  writeFileSync(
    join(gui.directory, "retired.ddd.json"),
    readFileSync(join(gui.directory, CONTROLLER)),
  );
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page).toHaveURL(/\/component\?file=[^&]+$/);

  // Controller's address as the page spells it, with the file changed to the retired one - spelled
  // as the page spells every file, absolute and posix-separated, whatever the system - the
  // variable and the view a values route is written with.
  const retired = `${gui.directory.replaceAll("\\", "/")}/retired.ddd.json`;
  const address = new URL(page.url());
  address.searchParams.set("file", retired);
  address.searchParams.set("variable", "CurveA");
  address.searchParams.set("view", "values");
  await page.goto(address.toString());

  // A grid is found by the object's name, whichever file the route names; only the way back,
  // which names the component by that file, finds none of the project's.
  await expect(page.getByRole("grid", { name: "Values of CurveA" })).toBeVisible();
  const back = page.getByRole("button", { name: "Back to component", exact: true });
  await expect(back).toBeVisible();
  await back.click();
  await expect(page.getByRole("alert")).toHaveText(
    `${retired} is not a description file of the open project`,
  );
});
