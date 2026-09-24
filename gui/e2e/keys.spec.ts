import { readFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, driftFactor, driftMax, openPanel, PUMP, SENSOR_HUB } from "./demo";
import { expect, test } from "./fixtures";

/** ValueA's definition in one file of the copy, read back from disk. */
function valueA(directory: string, file: string): Record<string, never> {
  const data = JSON.parse(readFileSync(join(directory, file), "utf8"));
  const entry = data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === "ValueA",
  );
  return entry.definition;
}

test("a conversion drifted from outside is carried back from the producer", async ({
  page,
  gui,
}) => {
  // The demo's two declarations of ValueA state one conversion; drifting Controller's factor
  // makes the row disagree, and the row a reader settles is the producer's own value.
  driftFactor(gui.directory, CONTROLLER, "ValueA", 0.25);
  // The server checks the disk for a change once a second (Session.poll_interval); the row
  // below already disagrees, since the panel reads it live from disk regardless, but a plan's
  // own fingerprint only carries the drifted bytes once the server has reanalysed - the same
  // hazard project-units.spec.ts's "an apply made from a panel that is out of date" names, and
  // this waits for it the same way, so the Apply below lands on a fingerprint it can act on.
  const reanalysed = page.waitForResponse((response) =>
    response.url().includes("/api/state?after="),
  );
  const panel = await openPanel(page, gui.address, "ValueA");
  await reanalysed;
  await panel.getByRole("row", { name: /^conversion/ }).click();
  const field = panel.getByRole("combobox", { name: "Conversion of ValueA" });
  await expect(field).toHaveValue("linear ×0.5");
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
  // Scoped to the key chooser's own region: the removal offer beside it (part 7) carries a
  // second "Show changes" of its own.
  const settle = panel.getByRole("region", { name: "Settle the key" });
  await settle.getByRole("button", { name: "Show changes" }).click();
  await expect(panel.locator(".hunk .added")).toContainText("0.5");

  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible();
  expect(valueA(gui.directory, CONTROLLER).conversion).toEqual({ kind: "linear", factor: 0.5 });
});

test("a range typed into the two fields reaches every declaration", async ({ page, gui }) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  await panel.getByRole("row", { name: /^limits/ }).click();
  await expect(panel.getByLabel("Max")).toHaveValue("100");
  await panel.getByLabel("Max").fill("50");
  await expect(
    panel.getByText("Changes 2 files: controller.ddd.json, sensor_hub.ddd.json"),
  ).toBeVisible();

  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible();
  expect(valueA(gui.directory, SENSOR_HUB).limits).toEqual({ min: 0, max: 50 });
  expect(valueA(gui.directory, CONTROLLER).limits).toEqual({ min: 0, max: 50 });
});

test("a limits row the panel opens by itself settles on the producer's range", async ({
  page,
  gui,
}) => {
  // Drifting Controller's greatest limit makes `limits` the one row that disagrees, so the
  // panel opens on it with nothing pressed but the variable's row - the path the component
  // table and the canvas both take, where no chooser is asked for by name.
  driftMax(gui.directory, CONTROLLER, "ValueA", 50);
  // As in the conversion journey: an Apply carries the fingerprint the analysis read the file
  // at, so wait for the server to have reanalysed the drift before pressing it.
  const reanalysed = page.waitForResponse((response) =>
    response.url().includes("/api/state?after="),
  );
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("rowheader", { name: "ValueA" }).click();
  await reanalysed;
  const panel = page.getByRole("complementary", { name: "ValueA" });

  // The producer's own range, in the field and in the two fields under it - not the removal
  // two empty fields would ask for.
  await expect(panel.getByRole("combobox", { name: "Limits of ValueA" })).toHaveValue("0 … 100");
  await expect(panel.getByLabel("Min")).toHaveValue("0");
  await expect(panel.getByLabel("Max")).toHaveValue("100");
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
  // Scoped to the key chooser's own region, as above: the removal offer carries a "Show
  // changes" of its own too.
  await panel
    .getByRole("region", { name: "Settle the key" })
    .getByRole("button", { name: "Show changes" })
    .click();
  await expect(panel.locator(".hunk .added")).toContainText('"max": 100');
  // Nothing is written until Apply, and both files still state the limits they had.
  expect(valueA(gui.directory, SENSOR_HUB).limits).toEqual({ min: 0, max: 100 });
  expect(valueA(gui.directory, CONTROLLER).limits).toEqual({ min: 0, max: 50 });

  // The other range in play is offered too, and a range taken from the list fills the two
  // fields with it, which is what would be written; the producer's is chosen back again.
  const field = panel.getByRole("combobox", { name: "Limits of ValueA" });
  await field.press("ArrowDown");
  // The list is a popover at the root of the page, not inside the panel.
  await page.getByRole("option", { name: "0 … 50", exact: true }).click();
  await expect(panel.getByLabel("Max")).toHaveValue("50");
  await expect(panel.getByText("Changes 1 file: sensor_hub.ddd.json")).toBeVisible();
  await field.press("ArrowDown");
  await page.getByRole("option", { name: "0 … 100", exact: true }).click();
  await expect(panel.getByLabel("Max")).toHaveValue("100");
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();

  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  // The range settled, so nothing disagrees any longer and the row the panel opened by itself
  // closes with it: the reader never picked a key, and there is none left to pick for them.
  await expect(panel.getByText("Select a key to settle it")).toBeVisible();
  await expect(panel.getByRole("row", { name: /^limits/ })).toContainText("0 … 100");
  expect(valueA(gui.directory, SENSOR_HUB).limits).toEqual({ min: 0, max: 100 });
  expect(valueA(gui.directory, CONTROLLER).limits).toEqual({ min: 0, max: 100 });
});

test("a change refused as stale can be applied again once the analysis has caught up", async ({
  page,
  gui,
}) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  await panel.getByRole("row", { name: /^limits/ }).click();
  await panel.getByLabel("Max").fill("50");
  const apply = panel.getByRole("button", { name: /^Apply to/ });
  await expect(apply).toBeEnabled();

  // The file changes under the page, between the preview it is holding and the press that sends
  // it, so that preview is against the old bytes. The order is the whole test: the session polls
  // once a second (`session.py`, `poll_interval`), so anything awaited between the change and the
  // press is a chance for the page to catch up first and for there to be nothing stale left to
  // refuse - which is how this failed on a CI runner and never here.
  driftMax(gui.directory, CONTROLLER, "ValueA", 60);
  await apply.click();
  await expect(panel.getByText("A file changed on disk")).toBeVisible();

  // The watcher catches up within a second; the sentence goes and Apply works.
  await expect(panel.getByText("A file changed on disk")).toBeHidden({ timeout: 15000 });
  await panel.getByLabel("Max").fill("50");
  await panel.getByRole("button", { name: /^Apply to/ }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible({ timeout: 15000 });
});

test("a range the two fields do not make offers no Apply, and changes nothing", async ({
  page,
  gui,
}) => {
  const before = new Map(
    [SENSOR_HUB, CONTROLLER].map((file) => [file, readFileSync(join(gui.directory, file))]),
  );
  const panel = await openPanel(page, gui.address, "ValueA");
  await panel.getByRole("row", { name: /^limits/ }).click();
  const field = panel.getByRole("combobox", { name: "Limits of ValueA" });
  // A whole range first, so what follows shows that nothing of it is kept behind the fields.
  await panel.getByLabel("Max").fill("50");
  await expect(panel.getByRole("button", { name: "Apply to 2 files" })).toBeVisible();

  await panel.getByLabel("Min").fill("100");
  await expect(panel.getByText("The maximum is below the minimum")).toBeVisible();
  await expect(field).toHaveValue("");
  await expect(panel.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  await panel.getByLabel("Max").fill("");
  await expect(panel.getByText("A range needs a minimum and a maximum")).toBeVisible();
  await expect(panel.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  // Taking the key out is a choice the list still offers, and it empties the two fields.
  await field.fill("state nothing");
  await field.press("Enter");
  await expect(panel.getByLabel("Min")).toHaveValue("");
  await expect(panel.getByLabel("Max")).toHaveValue("");
  await expect(panel.getByRole("button", { name: "Apply to 2 files" })).toBeVisible();

  // Nothing was applied, so the row still reads what the files say, and the files say what
  // they always did.
  await expect(panel.getByRole("row", { name: /^limits/ })).toContainText("0 … 100");
  for (const [file, bytes] of before) {
    expect(readFileSync(join(gui.directory, file)).equals(bytes)).toBe(true);
  }
});

test("a truth value is typed, confirmed with Enter, and cannot be left unstated", async ({
  page,
  gui,
}) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  await panel.getByRole("row", { name: /^volatile/ }).click();
  const field = panel.getByRole("combobox", { name: "Volatile of ValueA" });
  await expect(field).toHaveValue("false");
  // Every kind states its volatile, so the list has no way of taking it away.
  await field.press("ArrowDown");
  await expect(panel.getByRole("option", { name: "state nothing" })).toHaveCount(0);

  await field.fill("true");
  await field.press("Enter");
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible();
  expect(valueA(gui.directory, SENSOR_HUB).volatile).toBe(true);
  expect(valueA(gui.directory, CONTROLLER).volatile).toBe(true);
});

test("a key a declared type fixes is refused, and nothing is written", async ({
  page,
  vocabularyGui,
}) => {
  // The pump's TorqueLimit names Torque_t, which fixes its unit at Nm.
  const before = readFileSync(join(vocabularyGui.directory, PUMP));
  const panel = await openPanel(page, vocabularyGui.address, "TorqueLimit", "Pump");
  const field = panel.getByRole("combobox", { name: "Unit of TorqueLimit" });
  await field.fill("rpm");
  await field.press("Enter");
  await expect(panel.getByText("which fixes its unit")).toBeVisible();
  await expect(panel.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
  expect(readFileSync(join(vocabularyGui.directory, PUMP)).equals(before)).toBe(true);
});

test("a key that may be left unstated goes from every declaration", async ({ page, gui }) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  // The unit's own chooser is part 1's picker, whose entry for no unit reads "no unit".
  const field = panel.getByRole("combobox", { name: "Unit of ValueA" });
  await field.fill("no unit");
  await field.press("Enter");
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect(panel.getByRole("row", { name: /^unit/ })).toContainText("none");
  expect(valueA(gui.directory, SENSOR_HUB).unit).toBeUndefined();
  expect(valueA(gui.directory, CONTROLLER).unit).toBeUndefined();
});
