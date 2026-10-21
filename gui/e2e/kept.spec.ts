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
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
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
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
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
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
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
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
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
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
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
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(page.getByRole("grid", { name: "Declarations of Controller" })).toBeVisible();
  await expect(panel).toBeVisible();
  await expect(unit).toHaveValue("rpm");
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
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(page.getByRole("heading", { name: "CurveA" })).toBeVisible();
  await expect(grid).toBeVisible();
  expect(failed()).toBeGreaterThanOrEqual(1);
});
