import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

const CONTROLLER = join("components", "controller.ddd.json");
const COMPONENTS = ["Controller", "SensorHub", "UserInterface", "EventLogger"];

/** The project page's row for one component, to read its Errors and Warnings cells from. */
const componentRow = (page: Page, name: string) =>
  page.getByRole("row").filter({ has: page.getByRole("button", { name, exact: true }) });

test("the demo opens on its project page, with every component", async ({ page, gui }) => {
  await page.goto(gui.address);
  await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
  for (const name of COMPONENTS) {
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
    const cells = componentRow(page, name).getByRole("cell");
    await expect(cells.nth(1)).toHaveText("0");
    await expect(cells.nth(2)).toHaveText("0");
  }
});

test("a unit is written as one value and the disagreement is shown on both sides", async ({
  page,
  gui,
}) => {
  const file = join(gui.directory, CONTROLLER);
  const before = readFileSync(file);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();

  await page.getByRole("button", { name: "Change unit of ValueA" }).click();
  await page.getByRole("textbox", { name: "Unit of ValueA" }).fill("rpm");
  await page.getByRole("textbox", { name: "Unit of ValueA" }).press("Enter");
  await expect(page.getByRole("button", { name: "Change unit of ValueA" })).toHaveText("rpm");
  const expected = Buffer.from(
    before.toString("utf8").replace('"unit": "%"', '"unit": "rpm"'),
    "utf8",
  );
  await expect.poll(() => readFileSync(file).equals(expected)).toBe(true);
  await expect(page.locator(".findings").getByText("definition-mismatch")).toBeVisible();

  await page.getByRole("button", { name: "DemoDevice" }).click();
  await expect(componentRow(page, "Controller").getByRole("cell").nth(1)).toHaveText("1");
  await expect(componentRow(page, "SensorHub").getByRole("cell").nth(1)).toHaveText("1");
  await page.getByRole("button", { name: "SensorHub", exact: true }).click();
  await expect(page.locator(".findings").getByText("definition-mismatch")).toBeVisible();

  await page.goBack();
  await page.goBack();
  await page.getByRole("button", { name: "Change unit of ValueA" }).click();
  await page.getByRole("textbox", { name: "Unit of ValueA" }).fill("%");
  await page.getByRole("textbox", { name: "Unit of ValueA" }).press("Enter");
  await expect(page.getByText("None.")).toBeVisible();
  await expect.poll(() => readFileSync(file).equals(before)).toBe(true);
});

test("escape leaves a unit as it was", async ({ page, gui }) => {
  const file = join(gui.directory, CONTROLLER);
  const before = readFileSync(file);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Change unit of ValueA" }).click();
  await page.getByRole("textbox", { name: "Unit of ValueA" }).fill("rpm");
  await page.getByRole("textbox", { name: "Unit of ValueA" }).press("Escape");
  await expect(page.getByRole("button", { name: "Change unit of ValueA" })).toHaveText("%");
  expect(readFileSync(file).equals(before)).toBe(true);
});

test("a change saved by another editor reaches the page, and a unit being typed keeps its draft", async ({
  page,
  gui,
}) => {
  const file = join(gui.directory, CONTROLLER);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page.getByRole("button", { name: "Change unit of ValueB" })).toHaveText("V");
  await page.getByRole("button", { name: "Change unit of ValueA" }).click();
  await page.getByRole("textbox", { name: "Unit of ValueA" }).fill("rp");
  writeFileSync(file, readFileSync(file, "utf8").replace('"unit": "V"', '"unit": "mV"'));
  await expect(page.getByRole("button", { name: "Change unit of ValueB" })).toHaveText("mV", {
    timeout: 5_000,
  });
  // The table stays while the file is read again for the new revision, so the editor open in it
  // does too: swapped for "Reading the file…", it lost the draft.
  await expect(page.getByRole("textbox", { name: "Unit of ValueA" })).toHaveValue("rp");
});

test("an edit made from a page that is out of date is refused, and the file reloaded", async ({
  page,
  gui,
}) => {
  const file = join(gui.directory, CONTROLLER);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page.getByRole("button", { name: "Change unit of ValueB" })).toHaveText("V");
  await page.route("**/api/edit", async (route) => {
    writeFileSync(file, readFileSync(file, "utf8").replace('"unit": "V"', '"unit": "mV"'));
    await route.continue();
  });
  await page.getByRole("button", { name: "Change unit of ValueA" }).click();
  await page.getByRole("textbox", { name: "Unit of ValueA" }).fill("rpm");
  await page.getByRole("textbox", { name: "Unit of ValueA" }).press("Enter");
  await expect(page.getByRole("status")).toContainText("changed on disk");
  await expect(page.getByRole("button", { name: "Change unit of ValueB" })).toHaveText("mV");
  expect(readFileSync(file, "utf8")).toContain('"unit": "%"');
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
