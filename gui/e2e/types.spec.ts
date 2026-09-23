import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
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
