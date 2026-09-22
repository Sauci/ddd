import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, drift, driftIn, PUMP, unstamp } from "./demo";
import { expect, test } from "./fixtures";

/** ValueH's definition in the copy's own controller.ddd.json, read back from disk - the one
 * local declaration `unstamp` below takes an id from. */
function valueH(directory: string): Record<string, never> {
  const data = JSON.parse(readFileSync(join(directory, CONTROLLER), "utf8"));
  const entry = data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === "ValueH",
  );
  return entry.definition;
}

test("a disagreement leads to its variable", async ({ page, gui }) => {
  // Drifting Controller's own reading disagrees with SensorHub's, so the analysis files
  // `definition-mismatch` twice - once on each file it concerns - both leading to ValueA.
  drift(gui.directory);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();

  const row = page
    .getByRole("row", { name: "definition-mismatch" })
    .filter({ hasText: "controller.ddd.json" });
  await row.click();

  const panel = page.getByRole("complementary", { name: "definition-mismatch" });
  await expect(panel.locator(".chip")).toHaveText("error");
  await expect(panel.getByText("is declared differently by component 'Controller'")).toBeVisible();
  await expect(panel.locator(".panel-notes")).toContainText("reference declaration");
  await expect(panel.locator(".panel-notes")).toContainText("sensor_hub.ddd.json");

  await panel.getByRole("link", { name: "Open ValueA" }).click();

  // Controller's own page, with ValueA's panel open on the row that disagrees - part 3's own
  // rule, reached this time by a finding's route rather than by hand.
  await expect(page).toHaveURL(/\/component\?file=.*variable=ValueA$/);
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeVisible();
  const variablePanel = page.getByRole("complementary", { name: "ValueA" });
  await expect(variablePanel).toBeVisible();
  await expect(variablePanel.getByRole("combobox", { name: "Unit of ValueA" })).toHaveValue("%");
});

test("an unknown unit leads to its unit", async ({ page, vocabularyGui }) => {
  // A typo `unknown-unit` already knows how to say (the demo's own EngineSpeed states the same
  // RPM/rpm pair) - here on the vocabulary example's own PumpSpeed instead.
  driftIn(vocabularyGui.directory, PUMP, "PumpSpeed", "RPM");
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Findings" }).click();

  await page.getByRole("row", { name: "unknown-unit" }).click();
  const panel = page.getByRole("complementary", { name: "unknown-unit" });
  await expect(panel.locator(".chip")).toHaveText("error");
  await expect(panel.getByText("did you mean 'rpm'")).toBeVisible();

  await panel.getByRole("link", { name: "Open RPM" }).click();

  await expect(page).toHaveURL(/\/project\?view=units&unit=RPM$/);
  await expect(page.getByRole("complementary", { name: "RPM" })).toBeVisible();
});

test("a missing id is fixed", async ({ page, gui }) => {
  // ValueH is local to Controller - units.spec.ts's own reason for picking it too - so stripping
  // its id reports `missing-id` with nothing else in play, and the fix touches one file alone.
  unstamp(gui.directory, CONTROLLER, "ValueH");
  expect(valueH(gui.directory).id).toBeUndefined();

  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await page.getByRole("row", { name: "missing-id" }).click();

  const panel = page.getByRole("complementary", { name: "missing-id" });
  await expect(panel.locator(".chip")).toHaveText("note");
  await expect(panel.getByText("'ValueH' has no 'id'")).toBeVisible();

  await panel.getByRole("button", { name: "Give 'ValueH' an id" }).click();
  await panel.getByRole("button", { name: "Show changes" }).click();
  const added = panel.locator(".hunk .added").filter({ hasText: '"id":' });
  await expect(added).toHaveText(/^\+\s*"id": "[abcdefghjkmnpqrstvwxyz0-9]{12}"$/);

  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();
  await expect(page.getByRole("row", { name: "missing-id" })).toHaveCount(0);

  expect(valueH(gui.directory).id).toMatch(/^[abcdefghjkmnpqrstvwxyz0-9]{12}$/);
});

test("a finding that leads nowhere says why", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();

  // Saved half-edited, as units.spec.ts's own half-edited journey does to the same file: it no
  // longer parses, and the loader itself files the finding this time - on the file itself,
  // nowhere within it, so there is nowhere for a route to lead.
  const file = join(gui.directory, CONTROLLER);
  const before = readFileSync(file);
  writeFileSync(file, before.subarray(0, Math.floor(before.length / 2)));

  await page.getByRole("row", { name: "json-syntax" }).click();
  const panel = page.getByRole("complementary", { name: "json-syntax" });
  await expect(panel.locator(".chip")).toHaveText("error");
  await expect(panel.getByText("controller.ddd.json did not load")).toBeVisible();
  await expect(panel.getByRole("link", { name: /^Open/ })).toHaveCount(0);
});

test("the tab says when there is nothing to report", async ({ page, vocabularyGui }) => {
  // Served exactly as it ships: checked against the running server that examples/vocabulary's
  // own findings are already empty, so nothing here needs silencing or fixing first.
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();
});
