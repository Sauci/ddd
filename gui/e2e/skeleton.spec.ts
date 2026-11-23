import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import {
  CONTROLLER,
  chooseUnit,
  drift,
  held,
  SENSOR_HUB,
  withUnitOfValueA,
  writeUnseen,
} from "./demo";
import { expect, test } from "./fixtures";

const COMPONENTS = ["Controller", "SensorHub", "UserInterface", "EventLogger"];

/** The project page's row for one component, to read its Errors and Warnings cells from - its
 * own Component column is a row header (part 17's task 9: the table is React Aria's), so it
 * answers `role="rowheader"` rather than joining these `gridcell`s; Errors leads them, then
 * Warnings, then File. */
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
    const cells = componentRow(page, name).getByRole("gridcell");
    await expect(cells.nth(0)).toHaveText("0");
    await expect(cells.nth(1)).toHaveText("0");
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
  // Written is not finished. An edit is answered as soon as its files are written, and the panel
  // stays busy - its unit field disabled - until what the edit changed has been asked for again:
  // typed into in that moment, the field can turn disabled under the typing, and the text never
  // goes in. A reader sees the Apply finish as the panel saying there is nothing left to change,
  // and the field taking typing again.
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await expect(panel.getByText("Nothing to change")).toBeVisible();
  await expect(panel.getByRole("combobox", { name: "Unit of ValueA" })).toBeEnabled();

  await chooseUnit(page, "%");
  await page.getByRole("button", { name: "Apply to 2 files" }).click();
  for (const [index, file] of files.entries()) {
    await expect.poll(() => readFileSync(file).equals(before[index] as Buffer)).toBe(true);
  }
});

/** A unit's settlement on its way (16:M17): the panel says so where its consequence will stand,
 * and says the consequence once the plan has come, held until then. */
test("a unit chosen says it is planning while its settlement is on its way", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  const settle = panel.getByRole("region", { name: "Settle the key" });
  const picker = panel.getByRole("combobox", { name: "Unit of ValueA" });
  await picker.clear();
  await picker.pressSequentially("rpm");

  const release = await held(page, "/api/settle");
  try {
    await page.getByRole("option", { name: "rpm", exact: true }).first().click();
    await expect(settle.getByText("Planning…", { exact: true })).toBeVisible();
  } finally {
    release();
  }
  await expect(
    settle.getByText("Changes 2 files: controller.ddd.json, sensor_hub.ddd.json"),
  ).toBeVisible();
  await expect(settle.getByText("Planning…")).toHaveCount(0);
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
  writeFileSync(file, readFileSync(file, "utf8").replace('"unit": "V"', '"unit": "mV"'));
  // The reader is still typing, so the picker's list is still open, and while it is React Aria
  // hides the rest of the page from assistive technology: ValueB's button is looked for there
  // all the same.
  await expect(
    page.getByRole("button", { name: "Set the unit of ValueB", includeHidden: true }),
  ).toHaveText("mV", { timeout: 5_000 });
  // The table and the panel stay while the file is read again for the new revision, so the
  // picker does too: swapped for a loading line, it lost what the reader was typing.
  await expect(picker).toHaveValue("rp");
  await expect(picker).toHaveAttribute("aria-expanded", "true");
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
  // ValueB's unit changed on disk as the Apply goes out, unseen by the session's own watcher
  // (`writeUnseen`), so that only the Apply's own fresh read of the bytes sees it; the refusal is
  // held until the reader's next choice, whatever revision comes meanwhile (`Refused`,
  // lib/refusals.ts). `"unit":"mV"` is as many bytes as `"unit": "V"`, and reads the same.
  await page.route("**/api/edit", async (route) => {
    const changed = readFileSync(file, "utf8").replace('"unit": "V"', '"unit":"mV"');
    writeUnseen(gui.directory, CONTROLLER, changed);
    await route.continue();
  });
  await page.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(page.getByRole("status").filter({ hasText: "changed on disk" })).toBeVisible();
  // The file reloaded, as the refusal says: the watcher never sees the change, and the page's own
  // reading of the file again, or the analysis the refusal asks for (`Session._refused`), is what
  // shows ValueB in mV.
  await expect(page.getByRole("button", { name: "Set the unit of ValueB" })).toHaveText("mV");
  expect(readFileSync(file, "utf8")).toMatch(/"name": "ValueA"[\s\S]*?"unit": "%"/);
});

test("the page says so when the server stops", async ({ page, gui }) => {
  await page.goto(gui.address);
  await expect(page.getByRole("heading", { name: "DemoDevice" })).toBeVisible();
  await gui.stop();
  // Stopped in the middle of the canvas's own request, the server also leaves the canvas saying
  // that request went unanswered (the module graph's spec 5.6): a second alert, beside this one.
  await expect(page.getByRole("alert").filter({ hasText: "stopped" })).toBeVisible();
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

/** The demo's arrows, read once off its served canvas (Chrome on the Linux development PC, at
 * 13e805f) and pinned literally, as values.spec.ts pins its points: Controller to UserInterface
 * and to EventLogger; SensorHub to Controller, to UserInterface and to EventLogger; UserInterface
 * to EventLogger; and EventLogger to UserInterface. */
const DEMO_ARROWS = 7;

test("the demo opens on a canvas of its four modules", async ({ page, gui }) => {
  await page.goto(gui.address);
  const canvas = page.getByRole("region", { name: "Modules" });
  await expect(canvas).toBeVisible();
  for (const name of COMPONENTS) {
    await expect(canvas.getByRole("button", { name, exact: true })).toBeVisible();
  }
  // Every arrow is its own focusable group, named by the sentence a reader hears; the demo's
  // components all agree with each other until a journey below changes one. Counted with
  // `toHaveCount`, which waits for every one of them, not read once with `.all()`, which counts
  // whatever is drawn when it asks: today the arrows come in the same frame as the module
  // buttons (measured), because `nodesOf` (lib/canvas.ts) hands React Flow every node already
  // measured - but nothing this journey waited for said so.
  const arrows = canvas.getByRole("group");
  await expect(arrows).toHaveCount(DEMO_ARROWS);
  for (const arrow of await arrows.all()) {
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
  // The tab is an address of its own, which a new tab or window opens as well.
  await expect(page.getByRole("link", { name: "Table" })).toHaveAttribute(
    "href",
    "/project?view=table",
  );
  await page.getByRole("link", { name: "Table" }).click();
  await expect(componentRow(page, "Controller").getByRole("gridcell").nth(0)).toHaveText("0");
  await expect(page).toHaveURL(/\?view=table$/);

  await page.reload();
  await expect(componentRow(page, "Controller").getByRole("gridcell").nth(0)).toHaveText("0");
  await expect(page).toHaveURL(/\?view=table$/);
});

test("a dragged module stays where it was put after a revision, and Tidy puts it back", async ({
  page,
  gui,
}) => {
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

  // Saved from outside the page, so that a new revision arrives while the canvas is open - and
  // waited for by what it changes on the canvas, the arrow it colours, rather than by a
  // response the page may or may not have asked for yet.
  drift(gui.directory);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await expect
    .poll(() => controller.evaluate((node) => (node as HTMLElement).style.transform))
    .toBe(dragged);

  await page.getByRole("button", { name: "Tidy" }).click();
  await expect
    .poll(() => controller.evaluate((node) => (node as HTMLElement).style.transform))
    .toBe(original);
});

/**
 * The masthead's go-to (16:I14): its list opens on the first key, saying it is finding names until
 * they come from the server, and that none matches where none does; Escape empties it. `ValueA`,
 * which Controller - the component the project lists first - reads and SensorHub produces, typed
 * key by key, is listed with its kind and its producer, and Enter opens it on SensorHub's page, its
 * panel open.
 */
test("the masthead's go-to opens a variable on the page of the component producing it", async ({
  page,
  gui,
}) => {
  // Every text the go-to asks the server for: never the empty one, which the field holds before
  // anything is typed and again once a name is gone to.
  const asked: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname === "/api/names") asked.push(url.searchParams.get("text") ?? "");
  });
  await page.goto(gui.address);
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  const list = page.getByRole("listbox");
  const options = list.getByRole("option");
  const release = await held(page, "/api/names");
  try {
    await goTo.pressSequentially("V");
    // React Aria draws what an empty list says as its one row.
    await expect(options).toHaveText(["Finding names…"]);
  } finally {
    release();
  }
  // Every name holding a v, by name: CurveA first.
  await expect(options.first()).toHaveAccessibleName("CurveA");
  await goTo.pressSequentially("alueZ");
  await expect(options).toHaveText(["no variable matches"]);
  await goTo.press("Escape");
  await expect(goTo).toHaveValue("");

  await goTo.pressSequentially("ValueA");
  await expect(options).toHaveCount(1);
  await expect(options.first()).toHaveAccessibleName("ValueA");
  await expect(options.first()).toHaveAccessibleDescription("measurement in SensorHub");
  await goTo.press("Enter");
  await expect(page).toHaveURL(/\/component\?file=[^&]*sensor_hub\.ddd\.json&variable=ValueA$/);
  await expect(page.getByRole("heading", { name: "SensorHub", level: 1 })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "ValueA" })).toBeVisible();
  await expect(goTo).toHaveValue("");
  expect(asked).toContain("ValueA");
  expect(asked).not.toContain("");
});

/**
 * A name only a file that did not load declares is in no index (B11-28): the go-to's list says no
 * variable of a file that loaded matches, and names the file, rather than that no variable does -
 * as a removal's sentence says it (16:I10). ParameterA is Controller's own calibration.
 */
test("the masthead's go-to says no variable of a file that loaded matches while a file did not load", async ({
  page,
  gui,
}) => {
  const path = join(gui.directory, CONTROLLER);
  const bytes = readFileSync(path);
  writeFileSync(path, bytes.subarray(0, Math.floor(bytes.length / 2)));
  await page.goto(gui.address);
  // The banner under the masthead says it once the revision reading the cut file has landed.
  await expect(page.getByRole("status").filter({ hasText: "analysed without it" })).toHaveText(
    "controller.ddd.json did not load, so the project is analysed without it.",
  );
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  await goTo.pressSequentially("ParameterA");
  await expect(page.getByRole("listbox").getByRole("option")).toHaveText([
    "no variable of a file that loaded matches, and controller.ddd.json did not load",
  ]);
});

/**
 * A project the analysis could not index (16:I14): the go-to says why under its field, in the
 * server's words, rather than listing nothing as though no name held the text.
 */
test("the masthead's go-to says why a project it cannot search lists no name", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", (directory) => {
    const description = { project: { name: "DemoDevice", includes: 3 } };
    writeFileSync(join(directory, "demo.ddd.json"), JSON.stringify(description), "utf8");
  });
  await page.goto(gui.address);
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  await goTo.pressSequentially("Value");
  await expect(goTo).toHaveAccessibleDescription(
    "demo.ddd.json did not load, so no variable of the project can be found",
  );
  await expect(page.getByRole("listbox")).toHaveCount(0);
});
