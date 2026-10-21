import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { driftMaxUnseen, restamp } from "./demo";
import { expect, test } from "./fixtures";

const MONITORING = "monitoring.ddd.json";
const SENSING = "sensing.ddd.json";
const TYPES = "types.ddd.json";

/**
 * Sensing's own `Inlet` output drifted from `Sensor_t` (a structure) to `DriverStatus_t` (an
 * external type), saved from outside.
 *
 * Measured directly (see the task's report): this is the substitution that actually lands a
 * `type-kind` finding inside a type's own entry. The refusal is filed on the declaration
 * itself, but its "declared here" note points at `DriverStatus_t`'s entry in types.ddd.json,
 * and the analysis mirrors every finding onto each place named in its notes
 * (`ddd.lsp.diagnostics._mirrors`) - which is the copy `ddd.finding_routes.route_of` matches
 * against `types[N]` and routes to the type. Naming a structure where a scalar belongs - the
 * brief's first suggestion for this journey - produces a `definition-mismatch` between the two
 * components declaring `Inlet` instead, filed on their two declarations, neither of which is
 * inside a type's own entry, so it never routes to a type.
 */
function driftToExternalType(directory: string): void {
  const path = join(directory, SENSING);
  const before = readFileSync(path, "utf8");
  writeFileSync(path, before.replace('"typename": "Sensor_t"', '"typename": "DriverStatus_t"'));
}

test("a finding inside a type leads to it", async ({ page, structuresGui }) => {
  driftToExternalType(structuresGui.directory);
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Findings" }).click();

  // Filed on both sides: the declaration in sensing.ddd.json (which routes to the variable
  // Inlet) and its mirror in types.ddd.json (which routes to the type). Waiting for the row to
  // exist is what waits for the once-a-second watcher to have noticed the drift above; a plan's
  // fingerprint is never in play here, so nothing more is needed before the click.
  const row = page.getByRole("row", { name: "type-kind" }).filter({ hasText: "types.ddd.json" });
  await expect(row).toBeVisible();
  await row.click();

  const panel = page.getByRole("complementary", { name: "type-kind" });
  await expect(panel.locator(".chip")).toHaveText("error");
  await expect(
    panel.getByText(
      "'Inlet' is declared as 'DriverStatus_t', but that is an external type, whose layout " +
        "and meaning DDD does not know; only a structure member may name one",
    ),
  ).toBeVisible();
  await panel.getByRole("link", { name: "Open DriverStatus_t" }).click();

  await expect(page).toHaveURL(/\/project\?view=types&type=DriverStatus_t$/);
  await expect(page.getByRole("complementary", { name: "DriverStatus_t" })).toBeVisible();
});

test("a key a declared type fixes leads to that type", async ({ page, vocabularyGui }) => {
  // No declaration of examples/structures names a scalar type directly: Temperature_t, the
  // brief's own example, is only ever reached through a structure's member, and a member fixes
  // no key a chooser edits, so no "from" link is ever drawn for it. examples/vocabulary's
  // TorqueLimit names the scalar Torque_t directly - the same declaration keys.spec.ts's own "a
  // key a declared type fixes is refused" is built on - which is what this journey needs.
  await page.goto(vocabularyGui.address);
  await page.getByRole("button", { name: "Pump", exact: true }).click();
  await page.getByRole("row", { name: "TorqueLimit", exact: true }).click();

  const panel = page.getByRole("complementary", { name: "TorqueLimit" });
  const unitRow = panel.getByRole("row", { name: "unit", exact: true });
  await expect(unitRow).toContainText("Nm");
  await unitRow.getByRole("link", { name: "Torque_t" }).click();

  await expect(page).toHaveURL(/\/project\?view=types&type=Torque_t$/);
  await expect(page.getByRole("complementary", { name: "Torque_t" })).toBeVisible();
});

test("a type's unit settled from its panel is written, then undone", async ({
  page,
  structuresGui,
}) => {
  const typesFile = join(structuresGui.directory, TYPES);
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();

  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  await panel.getByRole("row", { name: "Unit", exact: true }).click();
  const picker = panel.getByRole("combobox", { name: "Unit of Temperature_t" });
  await expect(picker).toHaveValue("degC");
  await picker.fill("K");
  await picker.press("Enter");
  await expect(panel.getByText("Changes 1 file: types.ddd.json")).toBeVisible();
  await panel.getByRole("button", { name: "Show changes" }).click();
  await expect(panel.getByText('+ "unit": "K",')).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect.poll(() => readFileSync(typesFile, "utf8")).toContain('"unit": "K"');

  const undo = page.getByRole("button", { name: "Undo the unit of Temperature_t" });
  await expect(undo).toBeVisible();
  await undo.click();
  const strip = page.getByRole("region", { name: "Undo" });
  await expect(strip.getByText("Puts back 1 file: types.ddd.json")).toBeVisible();
  await strip.getByRole("button", { name: "Show changes" }).click();
  await expect(strip.getByText('+ "unit": "degC",')).toBeVisible();
  await strip.getByRole("button", { name: "Put back 1 file" }).click();

  await expect.poll(() => readFileSync(typesFile, "utf8")).toContain('"unit": "degC"');
  await expect(undo).toBeHidden();
});

test("a type is renamed everywhere, and a rename onto another type's name is refused", async ({
  page,
  structuresGui,
}) => {
  const files = [MONITORING, SENSING, TYPES].map((file) => join(structuresGui.directory, file));
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Sensor_t", exact: true }).click();

  const panel = page.getByRole("complementary", { name: "Sensor_t" });
  const renaming = panel.getByRole("textbox", { name: "Rename Sensor_t to" });
  await renaming.fill("Probe_t");
  await expect(
    panel.getByText("Changes 3 files: monitoring.ddd.json, sensing.ddd.json, types.ddd.json"),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Show changes" }).click();
  await expect(panel.locator(".hunk .added")).toHaveText([
    '+ "typename": "Probe_t",',
    '+ "typename": "Probe_t",',
    '+ "name": "Probe_t",',
  ]);
  await panel.getByRole("button", { name: "Apply to 3 files" }).click();

  for (const file of files) {
    await expect.poll(() => readFileSync(file, "utf8")).toContain("Probe_t");
    await expect.poll(() => readFileSync(file, "utf8")).not.toContain("Sensor_t");
  }
  await expect(page).toHaveURL(/\/project\?view=types&type=Probe_t$/);

  // Onto a name already in use elsewhere in c's own namespace: refused before anything is
  // written, and nothing left to press to write it anyway.
  const moved = page.getByRole("complementary", { name: "Probe_t" });
  await moved.getByRole("textbox", { name: "Rename Probe_t to" }).fill("Sample_t");
  await expect(
    moved.getByText(
      "'Sample_t' is the name of the type 'Sample_t', which shares c's namespace with the variables",
    ),
  ).toBeVisible();
  await expect(moved.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
});

/** What the Types panel says when an Apply is refused because a file changed under its preview. */
const STALE =
  "A file changed on disk, so nothing was written. The page now shows the files as they are.";

/** One type's entry in the types file of a copy, as it stands on disk. */
function entryOf(directory: string, name: string): Record<string, unknown> {
  const { types } = JSON.parse(readFileSync(join(directory, TYPES), "utf8")) as {
    types: { name: string }[];
  };
  const entry = types.find((type) => type.name === name);
  if (entry === undefined) throw new Error(`${TYPES} declares no type called ${name}`);
  return entry;
}

test("a type's range is settled from its two fields, and written", async ({
  page,
  structuresGui,
}) => {
  const before = entryOf(structuresGui.directory, "Temperature_t");
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();

  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  const limits = panel.getByRole("row", { name: "Limits", exact: true });
  await expect(limits).toContainText("-40 … 150");
  await limits.click();
  // The two fields the variable's own panel settles a range with (`KeyChooser`), here on a type.
  await expect(panel.getByLabel("Min", { exact: true })).toHaveValue("-40");
  await expect(panel.getByLabel("Max", { exact: true })).toHaveValue("150");
  await panel.getByLabel("Max", { exact: true }).fill("120");
  await expect(panel.getByText("Changes 1 file: types.ddd.json")).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();

  // The range alone, in the type's own entry: every other key of it is as it was.
  await expect
    .poll(() => entryOf(structuresGui.directory, "Temperature_t"))
    .toEqual({ ...before, limits: { min: -40, max: 120 } });
  await expect(limits).toContainText("-40 … 120");
});

test("a type's datatype is picked from the list of datatypes, and written", async ({
  page,
  structuresGui,
}) => {
  const before = entryOf(structuresGui.directory, "Temperature_t");
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();

  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  const datatype = panel.getByRole("row", { name: "Datatype", exact: true });
  await expect(datatype).toContainText("uint16");
  await datatype.click();
  const field = panel.getByRole("combobox", { name: "Datatype of Temperature_t" });
  await expect(field).toHaveValue("uint16");
  await field.press("ArrowDown");
  // The list is a popover at the root of the page, not inside the panel: the datatype the type
  // states, then the datatypes DDD knows.
  await expect(page.getByRole("group", { name: "Declared for Temperature_t" })).toBeVisible();
  const known = page.getByRole("group", { name: "Datatypes" });
  await expect(known).toBeVisible();
  await known.getByRole("option", { name: "sint16", exact: true }).click();
  await expect(field).toHaveValue("sint16");
  await expect(panel.getByText("Changes 1 file: types.ddd.json")).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();

  await expect
    .poll(() => entryOf(structuresGui.directory, "Temperature_t"))
    .toEqual({ ...before, datatype: "sint16" });
  await expect(datatype).toContainText("sint16");
});

test("a type's datatype and conversion offer no way to state nothing, where its unit and limits do", async ({
  page,
  structuresGui,
}) => {
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  // The list is a popover at the root of the page, not inside the panel.
  const choices = page.getByRole("listbox");

  // A type cannot do without its datatype or its conversion, so their lists offer no way of
  // taking the key away: only the value the type states, and for the datatype the datatypes.
  for (const [key, declared] of [
    ["Datatype", "uint16"],
    ["Conversion", "linear ×0.1 -40"],
  ] as const) {
    await panel.getByRole("row", { name: key, exact: true }).click();
    const field = panel.getByRole("combobox", { name: `${key} of Temperature_t` });
    await field.press("ArrowDown");
    await expect(choices.getByRole("option", { name: declared, exact: true })).toBeVisible();
    await expect(choices.getByRole("option", { name: "state nothing" })).toHaveCount(0);
    await expect(choices.getByRole("group", { name: "State nothing" })).toHaveCount(0);
    await field.press("Escape");
    await expect(choices).toBeHidden();
  }

  // The unit and the limits may be left out, and their lists end with the way to do it: the
  // unit picker's own "no unit", and "state nothing" for the range.
  for (const [key, nothing] of [
    ["Unit", "no unit"],
    ["Limits", "state nothing"],
  ] as const) {
    await panel.getByRole("row", { name: key, exact: true }).click();
    const field = panel.getByRole("combobox", { name: `${key} of Temperature_t` });
    await field.press("ArrowDown");
    await expect(choices.getByRole("option", { name: nothing, exact: true })).toBeVisible();
    await field.press("Escape");
    await expect(choices).toBeHidden();
  }
});

test("a type's description is typed, and written", async ({ page, structuresGui }) => {
  const before = entryOf(structuresGui.directory, "Temperature_t");
  const description = "A temperature in degrees Celsius, as every component agrees to see it";
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();

  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  const field = panel
    .getByRole("region", { name: "Description" })
    .getByRole("textbox", { name: "Description" });
  await expect(field).toHaveValue(String(before.description));
  await field.fill(description);
  await expect(panel.getByText("Changes 1 file: types.ddd.json")).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();

  // The description alone, in the type's own entry; the field and the tab's row follow the file.
  await expect
    .poll(() => entryOf(structuresGui.directory, "Temperature_t"))
    .toEqual({ ...before, description });
  await expect(field).toHaveValue(description);
  await expect(panel.getByText("Changes 1 file")).toHaveCount(0);
  await expect(page.getByRole("row", { name: "Temperature_t", exact: true })).toContainText(
    description,
  );
});

test("a type nothing declares any longer closes its panel, and the tab says so", async ({
  page,
  structuresGui,
}) => {
  const path = join(structuresGui.directory, TYPES);
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Sample_t", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "Sample_t" });
  await expect(panel.getByRole("textbox", { name: "Rename Sample_t to" })).toBeVisible();
  await expect(page).toHaveURL(/\/project\?view=types&type=Sample_t$/);

  // Rewritten from outside without Sample_t's entry, and still a types file that loads: its
  // other entries are as they were, one structure's member naming the type that is gone.
  const declared = JSON.parse(readFileSync(path, "utf8")) as { types: { name: string }[] };
  declared.types = declared.types.filter((type) => type.name !== "Sample_t");
  writeFileSync(path, `${JSON.stringify(declared, null, 2)}\n`);

  const gone = page.getByRole("status").filter({ hasText: "no longer declared" });
  await expect(gone).toHaveText("Sample_t is no longer declared in the open project.");
  await expect(panel).toHaveCount(0);
  await expect(page).toHaveURL(/\/project\?view=types$/);
  await expect(page.getByRole("row", { name: "Sample_t", exact: true })).toHaveCount(0);

  // Another type selected, the banner has said what it had to.
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "Temperature_t" })).toBeVisible();
  await expect(gone).toHaveCount(0);
});

test("a type whose file does not load keeps its panel, naming the file, until the file loads again", async ({
  page,
  structuresGui,
}) => {
  const path = join(structuresGui.directory, TYPES);
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  const renaming = panel.getByRole("textbox", { name: "Rename Temperature_t to" });
  await expect(renaming).toBeVisible();
  const gone = page.getByRole("status").filter({ hasText: "no longer declared" });

  // Saved half-edited, as an editor saves a file being typed into: no file that loads declares
  // Temperature_t, but the file that does not load may, so the panel stays, naming it.
  const whole = readFileSync(path);
  writeFileSync(path, whole.subarray(0, Math.floor(whole.length / 2)));
  await expect(panel.getByRole("alert")).toHaveText(
    "'Temperature_t' is not declared in any file that loaded, and types.ddd.json did not load",
  );
  await expect(panel.getByRole("heading", { name: "Temperature_t" })).toBeVisible();
  await expect(page).toHaveURL(/\/project\?view=types&type=Temperature_t$/);
  await expect(gone).toHaveCount(0);

  // Written back whole, the file loads again and the panel shows the type again.
  writeFileSync(path, whole);
  await expect(renaming).toBeVisible();
  await expect(panel.getByRole("alert")).toHaveCount(0);
  await expect(gone).toHaveCount(0);
});

test("an apply made from a type's panel that is out of date is refused, and goes through once the page has caught up", async ({
  page,
  structuresGui,
}) => {
  const before = entryOf(structuresGui.directory, "Temperature_t");
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  const limits = panel.getByRole("row", { name: "Limits", exact: true });
  await limits.click();
  await panel.getByLabel("Max", { exact: true }).fill("120");
  const apply = panel.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeEnabled();

  // The file changes under the page, between the preview it is holding and the press that sends
  // it, so that preview is against the old bytes. The session's own watcher never sees the write
  // `driftMaxUnseen` makes (it keeps the file's size and modification time), so only a fresh read
  // of the bytes does, which is the check an Apply itself makes - the same hazard as keys.spec.ts's
  // "a change refused as stale can be applied again once the analysis has caught up".
  driftMaxUnseen(structuresGui.directory, TYPES, "Temperature_t", 999);
  await apply.click();
  const refused = panel.getByRole("status").filter({ hasText: "A file changed on disk" });
  await expect(refused).toHaveText(STALE);
  // Nothing was written: the type's entry is as the drift left it.
  expect(entryOf(structuresGui.directory, "Temperature_t")).toEqual({
    ...before,
    limits: { min: -40, max: 999 },
  });

  // Hidden from the watcher for good, the drift is not what the rest can wait on: a plain bump of
  // the file's modification time is a real difference in what the watcher compares, so the next
  // poll reads the file as it is - drifted - and the page takes that revision on board, which is
  // when the sentence goes and the preview is asked for again against the bytes just read.
  restamp(structuresGui.directory, TYPES);
  await expect(refused).toBeHidden({ timeout: 15000 });
  await expect(limits).toContainText("-40 … 999");
  await apply.click();
  await expect
    .poll(() => entryOf(structuresGui.directory, "Temperature_t"))
    .toEqual({ ...before, limits: { min: -40, max: 120 } });
  await expect(limits).toContainText("-40 … 120");
});

/** An entry with one key left out, as the file holds it once that key is taken away. */
function without(entry: Record<string, unknown>, key: string): Record<string, unknown> {
  return Object.fromEntries(Object.entries(entry).filter(([each]) => each !== key));
}

test("a type's unit stated as nothing leaves its entry", async ({ page, structuresGui }) => {
  const before = entryOf(structuresGui.directory, "Temperature_t");
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();

  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  const unit = panel.getByRole("row", { name: "Unit", exact: true });
  await expect(unit).toContainText("degC");
  await unit.click();
  const field = panel.getByRole("combobox", { name: "Unit of Temperature_t" });
  await field.press("ArrowDown");
  // The list is a popover at the root of the page, not inside the panel.
  await page.getByRole("listbox").getByRole("option", { name: "no unit", exact: true }).click();
  await expect(field).toHaveValue("no unit");
  await panel.getByRole("button", { name: "Show changes" }).click();
  await expect(panel.locator(".hunk .removed")).toHaveText(['- "unit": "degC",']);
  await expect(panel.locator(".hunk .added")).toHaveCount(0);
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();

  // The unit alone is gone from the type's entry: every other key of it is as it was.
  await expect
    .poll(() => entryOf(structuresGui.directory, "Temperature_t"))
    .toEqual(without(before, "unit"));
  await expect(unit).toContainText("state nothing");
});

test("a type's limits stated as nothing leave its entry", async ({ page, structuresGui }) => {
  const before = entryOf(structuresGui.directory, "Temperature_t");
  await page.goto(structuresGui.address);
  await page.getByRole("link", { name: "Types" }).click();
  await page.getByRole("row", { name: "Temperature_t", exact: true }).click();

  const panel = page.getByRole("complementary", { name: "Temperature_t" });
  const limits = panel.getByRole("row", { name: "Limits", exact: true });
  await expect(limits).toContainText("-40 … 150");
  await limits.click();
  const field = panel.getByRole("combobox", { name: "Limits of Temperature_t" });
  await field.press("ArrowDown");
  // The list is a popover at the root of the page, not inside the panel.
  await page
    .getByRole("listbox")
    .getByRole("option", { name: "state nothing", exact: true })
    .click();
  // Stated as nothing, the range is the two fields left empty.
  await expect(field).toHaveValue("state nothing");
  await expect(panel.getByLabel("Min", { exact: true })).toHaveValue("");
  await expect(panel.getByLabel("Max", { exact: true })).toHaveValue("");
  await panel.getByRole("button", { name: "Show changes" }).click();
  // The range's lines go, and no line is put in their place.
  await expect(panel.locator(".hunk .removed")).toContainText([
    '"limits": {',
    '"min": -40,',
    '"max": 150',
  ]);
  await expect(panel.locator(".hunk .added")).toHaveCount(0);
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();

  // The range alone is gone from the type's entry: every other key of it is as it was.
  await expect
    .poll(() => entryOf(structuresGui.directory, "Temperature_t"))
    .toEqual(without(before, "limits"));
  await expect(limits).toContainText("state nothing");
});
