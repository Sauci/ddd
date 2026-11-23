import { chmodSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator } from "@playwright/test";
import {
  CONTROLLER,
  chooseUnit,
  drift,
  openPanel,
  renameValueA,
  SENSOR_HUB,
  scrolledIntoView,
} from "./demo";
import { expect, test } from "./fixtures";

test("a disagreement written from outside is resolved from the component page", async ({
  page,
  gui,
}) => {
  const before = drift(gui.directory);
  await page.goto(gui.address);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, error")).toBeVisible();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();

  const panel = page.getByRole("complementary", { name: "ValueA" });
  const picker = panel.getByRole("combobox", { name: "Unit of ValueA" });
  await expect(picker).toHaveValue("%");
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
  // Filed on both of the files it concerns, the disagreement is still one sentence here.
  await expect(panel.getByText("is declared differently by component 'Controller'")).toHaveCount(1);
  // Scoped to the key chooser's own region: the removal offer beside it (part 7) carries a
  // second "Show changes" of its own.
  await panel
    .getByRole("region", { name: "Settle the key" })
    .getByRole("button", { name: "Show changes" })
    .click();
  await expect(panel.getByText('"unit": "rpm"')).toBeVisible();

  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect.poll(() => readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
  await expect(panel.getByText("Nothing to change")).toBeVisible();

  await page.getByRole("button", { name: "DemoDevice" }).click();
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, agreed")).toBeVisible();
});

test("a unit typed and confirmed with Enter is the unit chosen, listed or not", async ({
  page,
  gui,
}) => {
  drift(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  const picker = panel.getByRole("combobox", { name: "Unit of ValueA" });
  const added = panel.locator(".hunk .added");
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();

  // Listed: since the drift, Controller's own reading of ValueA states rpm.
  await picker.fill("rpm");
  await picker.press("Enter");
  await expect(picker).toHaveValue("rpm");
  await expect(panel.getByText("Changes 1 file: sensor_hub.ddd.json")).toBeVisible();
  // Scoped to the key chooser's own region: the removal offer beside it (part 7) carries a
  // second "Show changes" of its own.
  await panel
    .getByRole("region", { name: "Settle the key" })
    .getByRole("button", { name: "Show changes" })
    .click();
  await expect(added).toHaveText(['+ "unit": "rpm",']);

  // In no list at all: taken exactly as typed.
  await picker.fill("kPa");
  await picker.press("Enter");
  await expect(picker).toHaveValue("kPa");
  await expect(
    panel.getByText("Changes 2 files: controller.ddd.json, sensor_hub.ddd.json"),
  ).toBeVisible();
  await expect(added).toHaveText(['+ "unit": "kPa",', '+ "unit": "kPa",']);

  // An entry reached with ArrowDown is the one Enter takes, not the text that narrowed the list.
  await picker.fill("r");
  await picker.press("ArrowDown");
  await picker.press("Enter");
  await expect(picker).toHaveValue("rpm");
  await expect(panel.getByText("Changes 1 file: sensor_hub.ddd.json")).toBeVisible();
});

test("a unit with spaces around it is refused, as the Units tab refuses it, and nothing is planned", async ({
  page,
  gui,
}) => {
  // 15:M10: `V ` and Enter wrote "unit": "V ", while the Units tab refuses that spelling.
  const files = [SENSOR_HUB, CONTROLLER].map((file) => join(gui.directory, file));
  const before = files.map((file) => readFileSync(file));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  const picker = panel.getByRole("combobox", { name: "Unit of ValueA" });
  await picker.click();
  await picker.clear();
  await picker.pressSequentially("V ");
  await picker.press("Enter");
  await expect(picker).toHaveAccessibleDescription("'V ' has spaces around it");
  // The field reads what was chosen, and the note under it why it is refused.
  await expect(picker).toHaveValue("V ");
  await expect(panel.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
  await expect(panel.getByText(/^Changes \d+ file/)).toHaveCount(0);
  expect(files.map((file, at) => readFileSync(file).equals(before[at] as Buffer))).toEqual([
    true,
    true,
  ]);
});

test("text left without Enter chooses nothing, and the field reads the chosen unit again", async ({
  page,
  gui,
}) => {
  drift(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  const picker = panel.getByRole("combobox", { name: "Unit of ValueA" });
  // The unit cell hands the reader the field, not the list over what is below it.
  await expect(picker).toBeFocused();
  await expect(picker).toHaveAttribute("aria-expanded", "false");
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();

  await picker.fill("r");
  await expect(picker).toHaveAttribute("aria-expanded", "true");
  await picker.press("Escape");
  await expect(picker).toHaveValue("%");
  await expect(picker).toHaveAttribute("aria-expanded", "false");

  // An Enter that takes nothing - a blank field - keeps the text; Escape puts the unit back.
  await picker.fill("");
  await picker.press("Enter");
  await expect(picker).toHaveValue("");
  await expect(picker).toHaveAttribute("aria-expanded", "false");
  await picker.press("Escape");
  await expect(picker).toHaveValue("%");

  await picker.fill("r");
  await picker.press("Tab");
  await expect(picker).not.toBeFocused();
  await expect(picker).toHaveValue("%");
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
});

test("after Apply the panel stays on the unit applied, and asks again only what Apply changed", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await chooseUnit(page, "rpm");
  await expect(
    panel.getByText("Changes 2 files: controller.ddd.json, sensor_hub.ddd.json"),
  ).toBeVisible();

  const asked: string[] = [];
  page.on("request", (request) => {
    const { pathname, searchParams } = new URL(request.url());
    if (pathname === "/api/settle") asked.push(`settle ${searchParams.get("raw")}`);
    if (pathname === "/api/session") asked.push("session");
  });
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  // The new revision's declarations, both stating the unit applied...
  await expect(panel.getByRole("gridcell", { name: "rpm", exact: true })).toHaveCount(2);
  // ...and the panel still on that unit with nothing left to change, never a preview of undoing
  // it; nor was anything asked for again that an Apply cannot change, such as the session.
  await expect(panel.getByRole("combobox", { name: "Unit of ValueA" })).toHaveValue("rpm");
  await expect(panel.getByText("Nothing to change")).toBeVisible();
  expect(asked.filter((entry) => entry !== 'settle "rpm"')).toEqual([]);
});

test("a unit settled into a read-only file is refused in the server's words, writes nothing, and is applied once the file is writable", async ({
  page,
  gui,
}) => {
  const controller = join(gui.directory, CONTROLLER);
  const hub = join(gui.directory, SENSOR_HUB);
  const before = { controller: readFileSync(controller), hub: readFileSync(hub) };
  const mode = statSync(controller).mode & 0o7777;
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await chooseUnit(page, "rpm");
  await expect(
    panel.getByText("Changes 2 files: controller.ddd.json, sensor_hub.ddd.json"),
  ).toBeVisible();
  const settle = panel.getByRole("region", { name: "Settle the key" });

  // Read-only to everyone, as a checkout kept read-only is: Windows' read-only flag on Windows.
  chmodSync(controller, 0o444);
  try {
    const answered = page.waitForResponse(
      (response) => new URL(response.url()).pathname === "/api/edit",
    );
    await settle.getByRole("button", { name: "Apply to 2 files" }).click();
    // A refusal the reader can mend, `409`, where a `500` is ddd gui failing on the request.
    const answer = await answered;
    expect([answer.status(), (await answer.json()).error]).toEqual([409, "unwritable"]);
    await expect(settle.getByRole("status")).toHaveText(
      /^The change was refused: .*controller\.ddd\.json is read-only, so nothing was written$/,
    );
    // Neither file of the edit is written: the one it may write is refused with the other.
    expect(readFileSync(controller).equals(before.controller)).toBe(true);
    expect(readFileSync(hub).equals(before.hub)).toBe(true);
  } finally {
    chmodSync(controller, mode);
  }

  // Writable again, the same unit chosen again - typed and taken with Enter, the field reading
  // it already - is applied to both files.
  const picker = panel.getByRole("combobox", { name: "Unit of ValueA" });
  await picker.clear();
  await picker.pressSequentially("rpm");
  await picker.press("Enter");
  await settle.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(panel.getByRole("gridcell", { name: "rpm", exact: true })).toHaveCount(2);
  expect(readFileSync(controller).equals(before.controller)).toBe(false);
  expect(readFileSync(hub).equals(before.hub)).toBe(false);
});

test("the picker lists the variable's units, then the project's, narrowed by what is typed", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const picker = page.getByRole("combobox", { name: "Unit of ValueA" });
  await page.getByRole("button", { name: /^Show the choices for Unit of ValueA/ }).click();
  await expect(page.getByRole("option", { name: "%", exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: "Hz", exact: true })).toBeVisible();
  // The list spans the field it belongs to, edge to edge: the panel's, the masthead holding the
  // go-to's field too.
  const panel = page.getByRole("complementary", { name: "ValueA" });
  const field = await panel.locator(".combo-field").boundingBox();
  const list = await page.locator(".combo-popover").boundingBox();
  expect([list?.x, list?.width]).toEqual([field?.x, field?.width]);
  await picker.fill("h");
  await expect(page.getByRole("option", { name: "Hz", exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: "%", exact: true })).toHaveCount(0);
});

test("a unit cell pressed again, once focus has moved elsewhere, moves it back to the picker", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const cell = page.getByRole("button", { name: "Set the unit of ValueA" });
  const picker = page.getByRole("combobox", { name: "Unit of ValueA" });
  await cell.click();
  await expect(picker).toBeFocused();
  await page.getByRole("button", { name: "DemoDevice" }).focus();
  await expect(picker).not.toBeFocused();
  await cell.click();
  await expect(picker).toBeFocused();
});

test("Close pressed from the keyboard puts the focus back on the unit cell the panel was opened from", async ({
  page,
  gui,
}) => {
  await openPanel(page, gui.address, "ValueA");
  await page.getByRole("button", { name: "Close ValueA" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("complementary", { name: "ValueA" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Set the unit of ValueA" })).toBeFocused();
});

/** Presses Close in a panel from the keyboard, and waits for the panel to go. */
async function closedByKeyboard(panel: Locator, title: string): Promise<void> {
  await panel.getByRole("button", { name: `Close ${title}` }).focus();
  await panel.page().keyboard.press("Enter");
  await expect(panel).toHaveCount(0);
}

test("Close puts the focus back on the row the panel was opened from", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const row = page
    .getByRole("grid", { name: "Declarations of Controller" })
    .getByRole("row", { name: /ValueB/ });
  await row.focus();
  await page.keyboard.press("Enter");
  const panel = page.getByRole("complementary", { name: "ValueB" });
  await expect(panel).toBeVisible();
  await closedByKeyboard(panel, "ValueB");
  await expect(row).toBeFocused();
});

test("Close puts the focus on the panel's row once the filter puts it back, in the table while the filter leaves it out, and on the heading where no row is left", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const table = page.getByRole("grid", { name: "Declarations of Controller" });
  const row = table.getByRole("row", { name: /ValueB/ });
  const panel = page.getByRole("complementary", { name: "ValueB" });
  const filter = page.getByRole("textbox", { name: "Filter declarations" });

  // Left out and put back, the row the panel was opened from is drawn anew, as another element:
  // the focus goes back to it all the same, though the table moved its own place off it meanwhile.
  await row.click();
  await expect(panel).toBeVisible();
  await filter.fill("State");
  await expect(row).toHaveCount(0);
  await filter.fill("");
  await expect(row).toBeVisible();
  await closedByKeyboard(panel, "ValueB");
  await expect(row).toBeFocused();

  // Left out, the panel's row cannot take it: the table does, at the place it moved to as the row
  // went, in the row standing nearest - its cell, where a cell of the row was clicked.
  await row.click();
  await expect(panel).toBeVisible();
  await filter.fill("State");
  await expect(row).toHaveCount(0);
  await closedByKeyboard(panel, "ValueB");
  const nearest = table.getByRole("row", { name: /StateA/ });
  await expect
    .poll(() => nearest.evaluate((element) => element.contains(document.activeElement)))
    .toBe(true);

  // No row left, no table is drawn, and the page's heading takes it.
  await filter.fill("");
  await row.click();
  await expect(panel).toBeVisible();
  await filter.fill("nothing has this name");
  await expect(table).toHaveCount(0);
  await closedByKeyboard(panel, "ValueB");
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeFocused();
});

test("Close puts the focus on the panel's row where its address opened it", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("row", { name: /ValueB/ }).click();
  await expect(page).toHaveURL(/variable=ValueB/);
  await page.reload();
  const panel = page.getByRole("complementary", { name: "ValueB" });
  await expect(panel).toBeVisible();
  await closedByKeyboard(panel, "ValueB");
  await expect(
    page.getByRole("grid", { name: "Declarations of Controller" }).getByRole("row", {
      name: /ValueB/,
    }),
  ).toBeFocused();
});

test("the address keeps the panel open across a reload", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("row", { name: /ValueB/ }).click();
  await expect(page).toHaveURL(/variable=ValueB/);
  await page.reload();
  await expect(page.getByRole("complementary", { name: "ValueB" })).toBeVisible();
});

test("a variable no longer declared closes its panel, and the page says so", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await expect(panel).toBeVisible();
  await expect(page).toHaveURL(/variable=ValueA/);
  const bookmark = page.url();

  renameValueA(gui.directory, "ValueZ");
  const gone = page
    .getByRole("status")
    .filter({ hasText: "ValueA is no longer declared in the open project." });
  await expect(gone).toBeVisible();
  await expect(panel).toHaveCount(0);
  await expect(page).not.toHaveURL(/variable=/);

  // Another variable selected, the banner has said what it had to.
  await page.getByRole("row", { name: /ValueB/ }).click();
  await expect(page.getByRole("complementary", { name: "ValueB" })).toBeVisible();
  await expect(gone).toHaveCount(0);

  // An address naming it from before the rename - a bookmark - is answered the same way, on the
  // component page as on the canvas.
  await page.goto(bookmark);
  await expect(gone).toBeVisible();
  await expect(page.getByRole("complementary", { name: "ValueA" })).toHaveCount(0);
  await expect(page).not.toHaveURL(/variable=/);
  await page.goto(new URL("/project?variable=ValueA", page.url()).href);
  await expect(gone).toBeVisible();
  await expect(page.getByRole("complementary", { name: "ValueA" })).toHaveCount(0);
  await expect(page).toHaveURL(/\/project$/);
});

test("the same disagreement is resolved from its arrow on the canvas", async ({ page, gui }) => {
  const before = drift(gui.directory);
  await page.goto(gui.address);
  await page.locator(".flow-label.error").click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await expect(panel).toBeVisible();
  await expect(page).toHaveURL(/\/project\?variable=ValueA$/);
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect.poll(() => readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, agreed")).toBeVisible();
});

test("an arrow in disagreement about two variables asks which, from the keyboard too", async ({
  page,
  gui,
}) => {
  // Both flow from SensorHub to Controller in the demo, and Controller reads each in another unit.
  drift(gui.directory, "ValueA", "rpm");
  drift(gui.directory, "ValueB", "mV");
  await page.goto(gui.address);
  const arrow = page.getByRole("button", { name: "SensorHub to Controller: 2 variables, error" });
  await expect(arrow).toBeVisible();
  // Reached the way a keyboard reaches it, one Tab at a time.
  for (let stop = 0; stop < 50; stop += 1) {
    if (await arrow.evaluate((element) => element === document.activeElement)) break;
    await page.keyboard.press("Tab");
  }
  await expect(arrow).toBeFocused();
  await page.keyboard.press("Enter");

  const chooser = page.getByRole("complementary", { name: "SensorHub to Controller" });
  await expect(chooser.getByRole("listitem")).toHaveText(["ValueA", "ValueB"]);
  await chooser.getByRole("button", { name: "ValueB", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "ValueB" })).toBeVisible();
  await expect(page).toHaveURL(/\/project\?variable=ValueB$/);
});

test("Close puts the focus back on the arrow a panel was opened from, through the chooser", async ({
  page,
  gui,
}) => {
  drift(gui.directory, "ValueA", "rpm");
  drift(gui.directory, "ValueB", "mV");
  await page.goto(gui.address);
  const arrow = page.getByRole("button", { name: "SensorHub to Controller: 2 variables, error" });
  await arrow.focus();
  await page.keyboard.press("Enter");
  // The chooser's own Close, then the variable's panel the chooser opened in its place.
  const chooser = page.getByRole("complementary", { name: "SensorHub to Controller" });
  await closedByKeyboard(chooser, "SensorHub to Controller");
  await expect(arrow).toBeFocused();
  await page.keyboard.press("Enter");
  await chooser.getByRole("button", { name: "ValueB", exact: true }).focus();
  await page.keyboard.press("Enter");
  const panel = page.getByRole("complementary", { name: "ValueB" });
  await expect(panel).toBeVisible();
  await closedByKeyboard(panel, "ValueB");
  await expect(arrow).toBeFocused();
});

test("no page reports a violation of its content security policy", async ({ page, gui }) => {
  // A disagreement, so that an arrow opens a panel and the panel has changes to show.
  drift(gui.directory);
  await page.addInitScript(() => {
    const seen: string[] = [];
    Object.assign(window, { violations: seen });
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  await page.goto(gui.address);
  await expect(page.getByRole("region", { name: "Modules" })).toBeVisible();
  await page.locator(".flow-label.error").click();
  await expect(page.getByRole("complementary", { name: "ValueA" })).toBeVisible();

  await page.getByRole("button", { name: "Projects" }).click();
  await expect(page.getByRole("heading", { name: "Open a project" })).toBeVisible();
  await page.getByRole("button", { name: "DemoDevice", exact: true }).click();

  // The Units tab: a unit's panel with a rename's changes shown, then - the demo having no units
  // file - the adoption's preview in its place.
  await page.getByRole("link", { name: "Units" }).click();
  await page.getByRole("row", { name: "rpm", exact: true }).click();
  const unit = page.getByRole("complementary", { name: "rpm" });
  const rename = unit.getByRole("combobox", { name: "Rename rpm to" });
  await rename.fill("%");
  await rename.press("Enter");
  await unit.getByRole("button", { name: "Show changes" }).click();
  await expect(unit.locator(".hunk")).toBeVisible();
  await page
    .getByRole("status")
    .filter({ hasText: "no units file" })
    .getByRole("button", { name: "Show changes" })
    .click();
  const adoption = page.getByRole("complementary", { name: "Adopt a vocabulary" });
  await expect(adoption.getByText("units.ddd.json, new")).toBeVisible();

  // The Findings tab (part 4): its table and the panel a row opens, on the page too - visited
  // here, still on the project screen, rather than from the component page below, which carries
  // no tabs of its own to follow back to it.
  await page.getByRole("link", { name: "Findings" }).click();
  await page.getByRole("row", { name: "definition-mismatch" }).first().click();
  await expect(page.getByRole("complementary", { name: "definition-mismatch" })).toBeVisible();

  // The Types tab (part 6), on the page too - visited here for the same reason as Findings
  // above, while the project's own tabs are still there to follow it from. The demo's only two
  // types are DriverState_t and SensorDiagnosis_t, neither a scalar, so neither offers part 1's
  // chooser; a rename is the one write path every kind of type offers, and its own preview is
  // what stands in for it here.
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "SensorDiagnosis_t", exact: true }).click();
  const diagnosis = page.getByRole("complementary", { name: "SensorDiagnosis_t" });
  await diagnosis
    .getByRole("textbox", { name: "Rename SensorDiagnosis_t to" })
    .fill("SensorDiagnostics_t");
  await diagnosis.getByRole("button", { name: "Show changes" }).click();
  // The type's own entry and the declaration naming it both change: two hunks, one file.
  await expect(diagnosis.locator(".hunk")).toHaveCount(2);

  // The values grid (part 8), on the component page too - visited here for the same reason as
  // Types above, while the project's own tabs are still there to follow it from.
  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const curveButton = page.getByRole("button", { name: "Show the values of CurveA" });
  await scrolledIntoView(page, "Declarations of Controller", curveButton);
  await curveButton.click();
  await expect(page.getByRole("textbox", { name: "element 1" })).toHaveValue("12");
  await page.getByRole("button", { name: "Back to Controller" }).click();

  // Back on the component page, which carries no tabs of its own - the same reason the add
  // panel section below returns through the masthead before its own "Table" click.
  await page.getByRole("button", { name: "DemoDevice" }).click();

  // The add panel (part 7), on the component page. Opened and filled far enough to draw its
  // preview - the panel's own chooser, its consequence and its hunks are the three things a
  // policy would otherwise catch - then closed, so the walk below starts where it did.
  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  await adding.getByRole("combobox", { name: "Name" }).fill("ValueC");
  await adding.getByRole("combobox", { name: "Name" }).press("Enter");
  await adding.getByRole("button", { name: "Show changes" }).click();
  await expect(adding.locator(".hunk")).toHaveCount(1);
  await adding.getByRole("button", { name: "Close" }).click();

  // The component page carries no tabs of its own - App.tsx draws `LinkTabs` only for the
  // project screen - so the walk goes back through the masthead's project button before its own
  // "Table" click below, which needs a project-level page under it to land on.
  await page.getByRole("button", { name: "DemoDevice" }).click();

  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });

  // The undo strip (part 5), whose Show changes prints the same hunks the panels do: settling
  // ValueA's unit here - the journey drifted it at the very top - gives the session something
  // to offer.
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await page.getByRole("button", { name: "Undo the unit of ValueA" }).click();
  const undone = page.getByRole("region", { name: "Undo" });
  await undone.getByRole("button", { name: "Show changes" }).click();
  await expect(undone.locator(".hunk")).toBeVisible();

  await panel.getByRole("combobox", { name: "Unit of ValueA" }).press("ArrowDown");
  await expect(page.getByRole("option", { name: "%", exact: true })).toBeVisible();
  await panel.getByRole("combobox", { name: "Unit of ValueA" }).press("Escape");

  // The keys table's other rows and choosers (part 3), open on the page too.
  await panel.getByRole("row", { name: /^limits/ }).click();
  await panel.getByRole("combobox", { name: "Limits of ValueA" }).press("ArrowDown");
  await expect(panel.getByLabel("Max")).toBeVisible();

  expect(
    await page.evaluate(() => (window as unknown as { violations: string[] }).violations),
  ).toEqual([]);
});

test("a file saved half-edited leaves open the panel of a variable only it declares", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await expect(page.getByLabel("SensorHub to Controller: 2 variables, agreed")).toBeVisible();
  // ValueH is local to Controller: no other file declares it. A single declaration never
  // disagrees with itself, so the panel opens on the table alone - this journey is about the
  // file that stops loading, not about a chooser.
  await page.goto(`${new URL(gui.address).origin}/project?variable=ValueH`);
  const panel = page.getByRole("complementary", { name: "ValueH" });
  await expect(panel).toBeVisible();

  // Saved half-edited, as an editor saves a file being typed into: it no longer parses, and the
  // variable is gone from every file that loads - but not from the project, and the panel stays,
  // naming the file rather than closing for good.
  const file = join(gui.directory, CONTROLLER);
  const before = readFileSync(file);
  writeFileSync(file, before.subarray(0, Math.floor(before.length / 2)));
  await expect(panel.getByText("controller.ddd.json did not load")).toBeVisible();
  await expect(page).toHaveURL(/\/project\?variable=ValueH$/);
  await expect(page.getByText("ValueH is no longer declared")).toHaveCount(0);

  // Saved again whole: the panel shows the variable as it did.
  writeFileSync(file, before);
  await expect(panel.getByText("controller.ddd.json did not load")).toHaveCount(0);
  await expect(panel).toBeVisible();
  await expect(page).toHaveURL(/\/project\?variable=ValueH$/);
});
