import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { CONTROLLER, chooseUnit, SENSOR_HUB, withUnitOfValueA } from "./demo";
import { expect, test } from "./fixtures";

const COMPONENTS = ["Controller", "SensorHub", "UserInterface", "EventLogger"];

/** The project page's row for one component, to read its Errors and Warnings cells from. */
const componentRow = (page: Page, name: string) =>
  page.getByRole("row").filter({ has: page.getByRole("button", { name, exact: true }) });

test("the demo opens on its project page, with every component", async ({ page, gui }) => {
  await page.goto(gui.address);
  // The project screen now opens on the canvas (milestone 2); the component counts this
  // journey checks are the table's, one tab away.
  await page.getByRole("link", { name: "Table" }).click();
  await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
  for (const name of COMPONENTS) {
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
    const cells = componentRow(page, name).getByRole("cell");
    await expect(cells.nth(1)).toHaveText("0");
    await expect(cells.nth(2)).toHaveText("0");
  }
});

test("a unit set from the panel is written as one value in every file declaring it", async ({
  page,
  gui,
}) => {
  const files = [join(gui.directory, CONTROLLER), join(gui.directory, SENSOR_HUB)];
  const before = files.map((file) => readFileSync(file));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();

  await chooseUnit(page, "rpm");
  await expect(
    page.getByText("Changes 2 files: controller.ddd.json, sensor_hub.ddd.json"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Apply to 2 files" }).click();
  for (const [index, file] of files.entries()) {
    const expected = withUnitOfValueA(before[index] as Buffer, "rpm");
    await expect.poll(() => readFileSync(file).equals(expected)).toBe(true);
  }

  await chooseUnit(page, "%");
  await page.getByRole("button", { name: "Apply to 2 files" }).click();
  for (const [index, file] of files.entries()) {
    await expect.poll(() => readFileSync(file).equals(before[index] as Buffer)).toBe(true);
  }
});

test("a unit chosen but not applied changes nothing", async ({ page, gui }) => {
  const files = [join(gui.directory, CONTROLLER), join(gui.directory, SENSOR_HUB)];
  const before = files.map((file) => readFileSync(file));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  await chooseUnit(page, "rpm");
  await expect(page.getByText("Changes 2 files", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Close ValueA" }).click();
  await expect(page.getByRole("complementary", { name: "ValueA" })).toHaveCount(0);
  expect(files.map((file, index) => readFileSync(file).equals(before[index] as Buffer))).toEqual([
    true,
    true,
  ]);
});

test("a change saved by another editor reaches the page, and a unit being typed keeps its draft", async ({
  page,
  gui,
}) => {
  const file = join(gui.directory, CONTROLLER);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page.getByRole("button", { name: "Set the unit of ValueB" })).toHaveText("V");
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const picker = page.getByRole("combobox", { name: "Unit of ValueA" });
  await picker.fill("rp");
  // React Aria's popover is a dialog by default: open, it hides the rest of the page from the
  // accessibility tree, which would hide ValueB's own button below. Escape closes it without
  // losing the draft the reader typed, exactly as leaving the field for the row below would.
  await picker.press("Escape");
  writeFileSync(file, readFileSync(file, "utf8").replace('"unit": "V"', '"unit": "mV"'));
  await expect(page.getByRole("button", { name: "Set the unit of ValueB" })).toHaveText("mV", {
    timeout: 5_000,
  });
  // The table and the panel stay while the file is read again for the new revision, so the
  // picker does too: swapped for a loading line, it lost what the reader was typing.
  await expect(picker).toHaveValue("rp");
});

test("an edit made from a page that is out of date is refused, and the file reloaded", async ({
  page,
  gui,
}) => {
  const file = join(gui.directory, CONTROLLER);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page.getByRole("button", { name: "Set the unit of ValueB" })).toHaveText("V");
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  await chooseUnit(page, "rpm");
  await page.route("**/api/edit", async (route) => {
    writeFileSync(file, readFileSync(file, "utf8").replace('"unit": "V"', '"unit": "mV"'));
    await route.continue();
  });
  await page.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(page.getByRole("status").filter({ hasText: "changed on disk" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Set the unit of ValueB" })).toHaveText("mV");
  expect(readFileSync(file, "utf8")).toMatch(/"name": "ValueA"[\s\S]*?"unit": "%"/);
});

test("the page says so when the server stops", async ({ page, gui }) => {
  await page.goto(gui.address);
  await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
  await gui.stop();
  await expect(page.getByRole("alert")).toContainText("stopped");
});

test("without a project the start page lists the ones found and opens the one chosen", async ({
  page,
  bareGui,
}) => {
  await page.goto(bareGui.address);
  await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
  await page.getByRole("button", { name: /DemoDevice/ }).click();
  await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
});

test("the demo opens on a canvas of its four modules", async ({ page, gui }) => {
  await page.goto(gui.address);
  const canvas = page.getByRole("region", { name: "Modules" });
  await expect(canvas).toBeVisible();
  for (const name of COMPONENTS) {
    await expect(canvas.getByRole("button", { name, exact: true })).toBeVisible();
  }
  // Every arrow is its own focusable group, named by the sentence a reader hears; the demo's
  // components all agree with each other until a journey below changes one.
  const arrows = await canvas.getByRole("group").all();
  expect(arrows.length).toBeGreaterThan(0);
  for (const arrow of arrows) {
    await expect(arrow).toHaveAccessibleName(/agreed$/);
  }
});

test("a disagreement colours its arrow", async ({ page, gui }) => {
  const file = join(gui.directory, CONTROLLER);
  const before = readFileSync(file);
  writeFileSync(file, withUnitOfValueA(before, "rpm"));
  await page.goto(gui.address);
  // SensorHub owns both ValueA and ValueB that Controller reads, so the arrow's count is the
  // pair's, not the disagreement's: it stays "2 variables" whether one of them disagrees or not.
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  writeFileSync(file, before);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, agreed")).toBeVisible();
});

test("an arrow says what is wrong", async ({ page, gui }) => {
  const file = join(gui.directory, CONTROLLER);
  writeFileSync(file, withUnitOfValueA(readFileSync(file), "rpm"));
  await page.goto(gui.address);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  // The label sits on the middle of the curve and is a tooltip trigger in its own right, so a
  // reader can aim at it without hitting the stroke underneath.
  await page.locator(".flow-label.error").hover();
  const tooltip = page.getByRole("tooltip");
  await expect(tooltip).toContainText("ValueA");
  await expect(tooltip).toContainText("definition-mismatch");
});

test("clicking a module opens its component page, and the back button returns to the canvas", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Controller" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("region", { name: "Modules" })).toBeVisible();
});

test("the table is one tab away", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Table" }).click();
  await expect(componentRow(page, "Controller").getByRole("cell").nth(1)).toHaveText("0");
  await expect(page).toHaveURL(/\?view=table$/);

  await page.reload();
  await expect(componentRow(page, "Controller").getByRole("cell").nth(1)).toHaveText("0");
  await expect(page).toHaveURL(/\?view=table$/);
});

test("a dragged module stays where it was put after a revision, and Tidy puts it back", async ({
  page,
  gui,
}) => {
  const file = join(gui.directory, SENSOR_HUB);
  await page.goto(gui.address);
  const controller = page
    .locator(".react-flow__node")
    .filter({ has: page.getByRole("button", { name: "Controller", exact: true }) });
  await expect(controller).toBeVisible();
  const original = await controller.evaluate((node) => (node as HTMLElement).style.transform);

  const box = await controller.boundingBox();
  if (box === null) throw new Error("the Controller node has no bounding box");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 40, box.y + box.height / 2 - 190, { steps: 12 });
  await page.mouse.up();
  const dragged = await controller.evaluate((node) => (node as HTMLElement).style.transform);
  expect(dragged).not.toBe(original);

  // Saved from outside the page, as milestone 1's own "a change saved by another editor" journey
  // does, so a new revision arrives while the canvas is still open.
  const redrawn = page.waitForResponse("**/api/graph");
  writeFileSync(
    file,
    readFileSync(file, "utf8").replace(
      "Produces the raw input values of the device",
      "Produces the raw input values of the device, revised",
    ),
  );
  await redrawn;
  await expect
    .poll(() => controller.evaluate((node) => (node as HTMLElement).style.transform))
    .toBe(dragged);

  await page.getByRole("button", { name: "Tidy" }).click();
  await expect
    .poll(() => controller.evaluate((node) => (node as HTMLElement).style.transform))
    .toBe(original);
});
