import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator } from "@playwright/test";
import { CONTROLLER, writeBlockAInit } from "./demo";
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
  await expect(grid.getByRole("columnheader")).toHaveText([
    "",
    "0",
    "800",
    "1600",
    "3200",
    "4800",
    "8000",
  ]);
  await expectRow(grid, ["12", "9", "8", "7.5", "7", "6.5"]);

  await page.getByRole("button", { name: "Raw" }).click();
  await expect(grid.getByRole("columnheader")).toHaveText([
    "",
    "0",
    "3200",
    "6400",
    "12800",
    "19200",
    "32000",
  ]);
  await expectRow(grid, ["1200", "900", "800", "750", "700", "650"]);
});

test("a cell changed is written to the producer's file", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of CurveA" }).click();

  await page.getByRole("textbox", { name: "element 3" }).fill("7.5");
  await expect(page.getByText("Sets element 3 of CurveA to 7.5 ms")).toBeVisible();
  await page.getByRole("button", { name: "Show changes" }).click();
  await expect(page.getByText('"init": [1200, 900, 750, 750, 700, 650],')).toBeVisible();

  await page.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect
    .poll(() => readFileSync(join(gui.directory, CONTROLLER), "utf8"))
    .toContain('"init": [1200, 900, 750, 750, 700, 650]');
});

test("a map's cell names its row and its column", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Show the values of MapA" }).click();

  const grid = page.getByRole("grid", { name: "Values of MapA" });
  await expect(grid.getByRole("rowheader")).toHaveText(["0", "30", "70", "100"]);

  await page.getByRole("button", { name: "Raw" }).click();
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

  await page.getByRole("textbox", { name: "element 1" }).fill("70000");
  await expect(page.getByText("70000 does not fit into uint16 (0 .. 65535)")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
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
});
