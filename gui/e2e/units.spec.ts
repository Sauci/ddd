import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, chooseUnit, drift, renameValueA } from "./demo";
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
  await panel.getByRole("button", { name: "Show changes" }).click();
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
  await panel.getByRole("button", { name: "Show changes" }).click();
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

  await picker.fill("");
  await picker.press("Enter");
  await expect(picker).toHaveValue("%");
  await expect(picker).toHaveAttribute("aria-expanded", "false");

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
  // The list spans the field it belongs to, edge to edge.
  const field = await page.locator(".combo-field").boundingBox();
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

  await page.getByRole("link", { name: "Table" }).click();
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Set the unit of ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await panel.getByRole("button", { name: "Show changes" }).click();
  await expect(panel.locator(".hunk")).toBeVisible();
  await panel.getByRole("combobox", { name: "Unit of ValueA" }).press("ArrowDown");
  await expect(page.getByRole("option", { name: "%", exact: true })).toBeVisible();
  await panel.getByRole("combobox", { name: "Unit of ValueA" }).press("Escape");

  // The keys table's other rows and choosers (part 2), open on the page too.
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
