import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import {
  CONTROLLER,
  chooseUnit,
  failing,
  openPanel,
  openValues,
  restamp,
  SERVER_FAILED,
  UNITS,
} from "./demo";
import { expect, test } from "./fixtures";

// A screen whose read of a new revision fails keeps its last good answer, with the error above it
// (spec 2026-10-21 §5). Each journey fails every read of the screen's own answer once the screen
// is drawn, then restamps a file of its project, as the units' own says why.

/** The types file of a copy of examples/structures, as types.spec.ts names it. */
const TYPES = "types.ddd.json";

/** The page's alert, standing above what the screen kept (`kept`, a CSS selector): the error said
 * over the kept answer, as files.spec.ts's "the list failing once drawn" asserts it. */
function alertAbove(page: Page, kept: string) {
  return page.getByRole("alert").and(page.locator(`:above(${kept})`));
}

test("the units failing on a new revision keep the table, with the error above it", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).click();
  const ms = page.getByRole("row", { name: "ms", exact: true });
  await expect(ms).toBeVisible();
  // Every read of the units fails from here; the restamp makes a new revision at once (P19b-9),
  // whose units the tab asks for under a new key - the read P19b-20 found dropped the table.
  const failed = await failing(page, "/api/units", "http");
  restamp(gui.directory, CONTROLLER);
  await expect(alertAbove(page, '[role="grid"]')).toHaveText(SERVER_FAILED);
  await expect(ms).toBeVisible();
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("the types failing on a new revision keep the table, with the error above it", async ({
  page,
  structuresGui,
}) => {
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  const temperature = page.getByRole("row", { name: "Temperature_t", exact: true });
  await expect(temperature).toBeVisible();
  const failed = await failing(page, "/api/types", "http");
  restamp(structuresGui.directory, TYPES);
  await expect(alertAbove(page, '[role="grid"]')).toHaveText(SERVER_FAILED);
  await expect(temperature).toBeVisible();
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("the shared files failing on a new revision keep the table, with the error above it", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  const raster = page.getByRole("row", { name: "100ms", exact: true });
  await expect(raster).toBeVisible();
  const failed = await failing(page, "/api/shared", "http");
  restamp(vocabularyGui.directory, UNITS);
  await expect(alertAbove(page, '[role="grid"]')).toHaveText(SERVER_FAILED);
  await expect(raster).toBeVisible();
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("the graph failing on a new revision keeps the canvas, with the error above it", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  const controller = page.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();
  const failed = await failing(page, "/api/graph", "http");
  restamp(gui.directory, CONTROLLER);
  await expect(alertAbove(page, 'section[aria-label="Modules"]')).toHaveText(SERVER_FAILED);
  await expect(controller).toBeVisible();
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("the files failing on a new revision keep the table, with the error above it", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  const units = page.getByRole("row", { name: UNITS });
  await expect(units).toBeVisible();
  const failed = await failing(page, "/api/files", "http");
  restamp(vocabularyGui.directory, UNITS);
  await expect(alertAbove(page, '[role="grid"]')).toHaveText(SERVER_FAILED);
  await expect(units).toBeVisible();
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("a component's file failing on a new revision keeps the page and its open panel, with the error above it", async ({
  page,
  gui,
}) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  // A choice the reader has made in the panel and not applied: what the page dropping with its
  // read would lose with the panel.
  await chooseUnit(page, "rpm");
  const unit = panel.getByRole("combobox", { name: "Unit of ValueA" });
  await expect(unit).toHaveValue("rpm");
  const failed = await failing(page, "/api/file", "http");
  restamp(gui.directory, CONTROLLER);
  await expect(alertAbove(page, '[aria-label="Declarations of Controller"]')).toHaveText(
    SERVER_FAILED,
  );
  await expect(page.getByRole("grid", { name: "Declarations of Controller" })).toBeVisible();
  await expect(panel).toBeVisible();
  await expect(unit).toHaveValue("rpm");
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("a component's file failing on a new revision keeps the parse error it last read, with the failure above it", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeVisible();
  // Saved half-edited and plainly, as declarations.spec.ts's journey of a file that stops parsing
  // saves it: the watcher sees it, and the page's last good answer is the parser's words. Read
  // off the page, and the same on every system: the file is checked out with LF (.gitattributes).
  const file = join(gui.directory, CONTROLLER);
  const before = readFileSync(file);
  writeFileSync(file, before.subarray(0, Math.floor(before.length / 2)));
  const parsed = `${file} is not json: Unterminated string starting at: line 110 column 27 (char 3427)`;
  await expect(page.getByRole("alert")).toHaveText(parsed);
  // Every read of the file fails from here, and the restamp makes a new revision at once: the
  // parse error is kept, under the failure - never alone, as if it were the new revision's.
  const failed = await failing(page, "/api/file", "http");
  restamp(gui.directory, CONTROLLER);
  await expect(page.getByRole("alert")).toHaveText([SERVER_FAILED, parsed]);
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("the values failing on a new revision keep the grid, with the error above it", async ({
  page,
  gui,
}) => {
  await openValues(page, gui.address, "CurveA");
  const grid = page.getByRole("grid", { name: "Values of CurveA" });
  await expect(grid).toBeVisible();
  const failed = await failing(page, "/api/values", "http");
  restamp(gui.directory, CONTROLLER);
  await expect(alertAbove(page, '[aria-label="Values of CurveA"]')).toHaveText(SERVER_FAILED);
  await expect(page.getByRole("heading", { name: "CurveA" })).toBeVisible();
  await expect(grid).toBeVisible();
  expect(failed()).toBeGreaterThanOrEqual(1);
});
