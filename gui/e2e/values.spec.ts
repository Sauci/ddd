import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator } from "@playwright/test";
import { CONTROLLER, paste, SENSOR_HUB, typeCurveA, widenBlockA, writeBlockAInit } from "./demo";
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

test("a curve is read against its axis, raw and physical", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of CurveA" }).click();

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

test("a cell changed is written to the producer's file", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of CurveA" }).click();

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

test("a reader's page names the producer's file, not its own", async ({ page, gui }) => {
  // Spec 5.3's own example: ValueB on Controller is an `input`, its numbers live in SensorHub,
  // and the preview names sensor_hub.ddd.json. Nothing is applied here - the sentence before
  // Apply is the whole subject.
  const before = readFileSync(join(gui.directory, SENSOR_HUB));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of ValueB" }).click();

  await page.getByRole("textbox", { name: "element 1" }).fill("1");
  await expect(page.getByText("Sets element 1 of ValueB to 1 V")).toBeVisible();
  await expect(page.getByText("Changes 1 file: sensor_hub.ddd.json")).toBeVisible();
  expect(readFileSync(join(gui.directory, SENSOR_HUB)).equals(before)).toBe(true);
});

test("a map's cell names its row and its column", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of MapA" }).click();

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
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of CurveA" }).click();

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
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of CurveA" }).click();
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
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of CurveA" }).click();

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
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of CurveA" }).click();

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
// journey. The one mechanism this file already has for that failure is the out-of-range cell
// above ("a value the datatype cannot hold is refused, and nothing is written"), and it cannot
// reach one: `_value_plan` (`api.py`) runs `set_cell`'s own range check before ever answering a
// plan, so a value out of range never renders an `Apply to` button at all - that test's own
// `toHaveCount(0)` is exactly this - and `apply.mutate()`, the only place `ValuesPage.tsx` sets
// its non-stale `failed`, is never reached. Nothing reachable through a cell's own Apply button
// can fail non-stale without the file also changing underneath it, which is staleness itself; the
// only way left is a mechanism of its own (an unwritable file, say), which is not reusing this
// one - left untried rather than invented.
test("a pasted curve replaces every value in one edit", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of CurveA" }).click();

  await paste(page, "13\t9.5\t8.5\t8\t7.5\t7");
  await expect(page.getByText("Replaces every value of CurveA")).toBeVisible();
  await expect(page.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();

  await page.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect
    .poll(() => readFileSync(join(gui.directory, CONTROLLER), "utf8"))
    .toContain('"init": [1300, 950, 850, 800, 750, 700]');
  await expect(page.getByRole("button", { name: "Undo the values of CurveA" })).toBeVisible();
});

test("a pasted map takes its header row and column", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of MapA" }).click();
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
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of CurveA" }).click();

  await paste(page, ["1\t2\t3\t4\t5\t6", "7\t8\t9\t10\t11\t12"].join("\n"));
  await expect(
    page.getByText("expected 1 row of 6, or 2 rows of 7 with a header; got 2 rows of 6"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
});

test("a value the datatype cannot hold names every offender", async ({ page, gui }) => {
  const before = readFileSync(join(gui.directory, CONTROLLER));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of MapA" }).click();
  await page.getByRole("button", { name: "Raw" }).click();

  await paste(page, MAP_A_OVER_RANGE);
  await expect(
    page.getByText(
      "element 1, 1, element 1, 3 and element 1, 6 of 'MapA' are refused: " +
        "200 does not fit into sint8 (-128 .. 127)",
    ),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
});

test("a pasted table is put back", async ({ page, gui }) => {
  const before = readFileSync(join(gui.directory, CONTROLLER));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of CurveA" }).click();

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

  // The Type cell reads the type, since there is no datatype of its own to read.
  await expect(page.getByRole("gridcell", { name: "Millis_t" })).toBeVisible();
  await page.getByRole("button", { name: "Show the values of CurveA" }).click();

  const grid = page.getByRole("grid", { name: "Values of CurveA" });
  await expect(grid.getByRole("rowheader")).toHaveText(["CurveA (ms)"]);
  await expectRow(grid, ["12", "9", "8", "7.5", "7", "6.5"]);
});
