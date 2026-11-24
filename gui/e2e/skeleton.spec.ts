import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import {
  CONTROLLER,
  chooseUnit,
  drift,
  held,
  includesNothing,
  namingAScalarType,
  openValues,
  SENSOR_HUB,
  twoFrames,
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

test("a row followed from the keyboard opens its page with the focus on its heading, and Back the page before with its own", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Table" }).click();
  await componentRow(page, "Controller").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeFocused();
  // The keyboard goes on from the page's top: its first control, not the masthead's.
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Add a declaration" })).toBeFocused();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "DemoDevice", level: 1 })).toBeFocused();
});

test("a tab, the masthead's Projects and a grid's way back put the focus on the heading of the page they open", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\?view=units$/);
  await expect(page.getByRole("heading", { name: "DemoDevice", level: 1 })).toBeFocused();
  // A row selected is no change of page: the focus stays on it as its panel opens.
  const row = page.getByRole("grid", { name: "Units" }).getByRole("row", { name: /Hz/ });
  await row.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("complementary", { name: "Hz" })).toBeVisible();
  await expect(row).toBeFocused();

  await openValues(page, gui.address, "MapA");
  await expect(page.getByRole("heading", { name: "MapA", level: 1 })).toBeFocused();
  await page.getByRole("button", { name: "Back to Controller" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeFocused();

  await page.getByRole("button", { name: "Projects" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Open a project", level: 1 })).toBeFocused();
});

test("every page is titled by its name and the project's", async ({ page, gui }) => {
  await page.goto(gui.address);
  await expect(page).toHaveTitle("Graph · DemoDevice · ddd gui");
  await page.getByRole("link", { name: "Units" }).click();
  await expect(page).toHaveTitle("Units · DemoDevice · ddd gui");
  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page).toHaveTitle("Controller · DemoDevice · ddd gui");
  await openValues(page, gui.address, "MapA");
  await expect(page).toHaveTitle("MapA · Controller · DemoDevice · ddd gui");
  await page.getByRole("button", { name: "Projects" }).click();
  await expect(page).toHaveTitle("Open a project · ddd gui");
});

test("a page's heading drawn once its file is read takes the focus then, unless a key was pressed meanwhile", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Table" }).click();
  const reading = page.getByText("Reading the file…");
  let release = await held(page, "/api/file");
  try {
    await componentRow(page, "Controller").focus();
    await page.keyboard.press("Enter");
    await expect(reading).toBeVisible();
  } finally {
    release();
  }
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeFocused();

  // The reader in the masthead's go-to, a key pressed there while SensorHub's file is read: the
  // heading drawn after leaves the focus where the reader has it.
  await page.goBack();
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  release = await held(page, "/api/file");
  try {
    await componentRow(page, "SensorHub").focus();
    await page.keyboard.press("Enter");
    await expect(reading).toBeVisible();
    await goTo.focus();
    await page.keyboard.press("Shift");
  } finally {
    release();
  }
  await expect(page.getByRole("heading", { name: "SensorHub", level: 1 })).toBeVisible();
  // Two frames on, the heading's own effects have run.
  await page.evaluate(
    () => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))),
  );
  await expect(goTo).toBeFocused();
});

/**
 * A change of page whose panel is drawn after the page (16:I13, ruling B11-41): GainA's panel on
 * the Graph links to Gain_t, the scalar type giving it its unit, on the Types tab, which draws its
 * table and the type's panel once the project's types are read. The page's heading holds the focus
 * meanwhile, and the type's panel takes it as it is drawn.
 */
test("a type a panel links to takes the focus once its panel is drawn, the page's heading holding it meanwhile", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", namingAScalarType);
  await page.goto(gui.address);
  const graph = new URL(page.url());
  graph.pathname = "/project";
  graph.search = "?variable=GainA";
  await page.goto(graph.href);
  const link = page
    .getByRole("complementary", { name: "GainA" })
    .getByRole("link", { name: "Gain_t" })
    .first();
  await expect(link).toBeVisible();
  const release = await held(page, "/api/types");
  try {
    await link.click();
    await expect(page.getByText("Reading the project's types…")).toBeVisible();
    await expect(page.getByRole("heading", { name: "DemoDevice", level: 1 })).toBeFocused();
  } finally {
    release();
  }
  await expect(
    page
      .getByRole("complementary", { name: "Gain_t" })
      .getByRole("heading", { name: "Gain_t", level: 2 }),
  ).toBeFocused();
});

/**
 * The page scrolled by the reader as a change of page opens a panel (16:M9): the go-to opens
 * ParameterA beside Controller's declarations in a window 1000 by 420, its panel still reading its
 * variable, and the reader scrolls the page down past the panel's heading, by the wheel or by a
 * key. The panel, read and drawn taller, leaves the page where the reader scrolled it: only what
 * the page itself moved is scrolled back to the panel.
 */
for (const way of ["wheel", "key"] as const) {
  test(`a page the reader scrolls by the ${way} as the go-to opens a panel stays where it is scrolled`, async ({
    page,
    gui,
  }) => {
    await page.setViewportSize({ width: 1000, height: 420 });
    await page.goto(gui.address);
    const goTo = page.getByRole("combobox", { name: "Go to a variable" });
    await goTo.pressSequentially("ParameterA");
    await expect(page.getByRole("option", { name: "ParameterA" })).toBeVisible();
    const panel = page.getByRole("complementary", { name: "ParameterA" });
    const release = await held(page, "/api/variable");
    let scrolled = 0;
    try {
      await goTo.press("Enter");
      await expect(panel.getByText("Reading ParameterA…")).toBeVisible();
      if (way === "wheel") {
        const box = await panel.boundingBox();
        if (box === null) throw new Error("the panel is not drawn");
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.mouse.wheel(0, 400);
      } else {
        await page.keyboard.press("PageDown");
      }
      // Past the panel's heading, the scroll come to rest.
      const heading = panel.getByRole("heading", { name: "ParameterA", level: 2 });
      await expect(heading).not.toBeInViewport();
      await expect
        .poll(async () => {
          const before = await page.evaluate(() => window.scrollY);
          await page.waitForTimeout(100);
          return (await page.evaluate(() => window.scrollY)) === before;
        })
        .toBe(true);
      scrolled = await page.evaluate(() => window.scrollY);
    } finally {
      release();
    }
    await expect(panel.getByRole("grid", { name: "Keys of ParameterA" })).toBeVisible();
    // Two frames on, what the page watches of its own layout has run.
    await page.evaluate(
      () => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))),
    );
    expect(await page.evaluate(() => window.scrollY)).toBe(scrolled);
  });
}

/**
 * A focus moved by no key and no pointer once a change of page's panel has read (16:I13, ruling
 * B11-45): the go-to opens ParameterA beside Controller's declarations in a window 1000 by 420, its
 * heading in view and focused. An assistive technology moves the focus on to the panel's Remove
 * button, the page scrolling it into view, and the window then narrows. The focus stays where it
 * was moved, in view: nothing the change of page left waiting takes it, or the page, back.
 */
test("a focus moved by no key and no pointer once a change of page's panel has read stays where it was moved, in view", async ({
  page,
  gui,
}) => {
  await page.setViewportSize({ width: 1000, height: 420 });
  await page.goto(gui.address);
  const goTo = page.getByRole("combobox", { name: "Go to a variable" });
  await goTo.pressSequentially("ParameterA");
  await expect(page.getByRole("option", { name: "ParameterA" })).toBeVisible();
  await goTo.press("Enter");
  const panel = page.getByRole("complementary", { name: "ParameterA" });
  await expect(panel.getByRole("grid", { name: "Keys of ParameterA" })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "ParameterA", level: 2 })).toBeFocused();
  const remove = panel.getByRole("button", { name: "Remove from Controller" });
  await expect(remove).toBeVisible();
  await remove.focus();
  await expect(remove).toBeInViewport();
  await page.setViewportSize({ width: 960, height: 420 });
  await twoFrames(page);
  await expect(remove).toBeFocused();
  await expect(remove).toBeInViewport();
});

/** GainA's panel on the Graph, and its link to Gain_t, the scalar type giving GainA its unit. */
async function gainLink(page: Page, address: string): Promise<Locator> {
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

/**
 * A focus moved by no key and no pointer while a change of page waits for its panel (16:I13,
 * ruling B11-45): GainA's link to Gain_t opens the Types tab, whose types are held back, the
 * page's heading holding the focus meanwhile. An assistive technology moves the focus on to the
 * Units tab: the type's panel, drawn once the types are read, leaves it there.
 */
test("a focus moved by no key and no pointer while a type a panel links to is read stays where it was moved", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", namingAScalarType);
  const link = await gainLink(page, gui.address);
  const units = page.getByRole("link", { name: "Units", exact: true });
  const release = await held(page, "/api/types");
  try {
    await link.click();
    await expect(page.getByText("Reading the project's types…")).toBeVisible();
    await expect(page.getByRole("heading", { name: "DemoDevice", level: 1 })).toBeFocused();
    await units.focus();
  } finally {
    release();
  }
  await expect(
    page
      .getByRole("complementary", { name: "Gain_t" })
      .getByRole("heading", { name: "Gain_t", level: 2 }),
  ).toBeVisible();
  await twoFrames(page);
  await expect(units).toBeFocused();
});

/** What the Graph and the Table say of a project that includes no component (16:M13). */
const NEW_FILE =
  "This project includes no component yet: New file, on the Files tab, writes one and includes it.";

test("a project that includes no component points at New file from its table", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", includesNothing);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Table", exact: true }).click();
  await expect(page.getByText("0 errors, 0 warnings", { exact: true })).toBeVisible();
  const line = page.getByText("This project includes no component yet:");
  await expect(line).toHaveText(NEW_FILE);
  // The table stays in the page as it was while nothing is typed in its filter (`tableDrawn`): a
  // table with no row, whose box stands nothing high.
  await expect(page.getByRole("grid", { name: "Components" })).toHaveCount(1);
  await line.getByRole("link", { name: "New file", exact: true }).click();
  await expect(page).toHaveURL(/\/project\?view=files$/);
  await expect(page.getByRole("button", { name: "New file", exact: true })).toBeVisible();
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
  await expect(page.getByRole("status").filter({ hasText: "project's checks" })).toHaveText(
    "controller.ddd.json did not load, so the project's checks wait until it does, and the pages " +
      "show what the files that loaded declare.",
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
