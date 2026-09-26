import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, drift, driftIn, EVENT_LOGGER, PUMP, USER_INTERFACE, unstamp } from "./demo";
import { expect, test } from "./fixtures";

/** ValueE's own `"unit"` in a file, read back from disk - its own declaration's and no other, so
 * a stray `"unit": "Hz"` elsewhere in the same file (AxisA's, in user_interface.ddd.json) cannot
 * make a fix that wrote nothing look like one that worked. Found through the file's own
 * structure, as `valueH` below is: a regex scoped by "the next unit after the name" would read
 * straight past a ValueE that states none and report the following declaration's instead, which
 * is the one way this assertion could go quiet rather than fail. */
function unitOfValueE(bytes: Buffer): string | undefined {
  const data = JSON.parse(bytes.toString("utf8"));
  const entry = data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === "ValueE",
  );
  return entry?.definition.unit;
}

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

test("a disagreement is settled from the finding that reports it", async ({ page, gui }) => {
  // ValueE is written by Controller and read by UserInterface and EventLogger, all three in
  // Hz - the only demo variable with one producer and two consumers, so drifting one reader's
  // unit shows a fix that reaches one file, and drifting both shows the same button reaching
  // two: the settlement follows the variable, not the finding that happened to report it.
  driftIn(gui.directory, USER_INTERFACE, "ValueE", "kHz");
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings" }).click();

  const panel = page.getByRole("complementary", { name: "definition-mismatch" });

  const uiRow = page
    .getByRole("row", { name: "definition-mismatch" })
    .filter({ hasText: "user_interface.ddd.json" });
  await uiRow.click();
  await panel.getByRole("button", { name: "Use the unit declared in controller" }).click();
  await expect(panel.getByRole("button", { name: "Apply to 1 file" })).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();

  await expect(page.getByText("Nothing to report")).toBeVisible();
  expect(unitOfValueE(readFileSync(join(gui.directory, USER_INTERFACE)))).toBe("Hz");

  // Both readers disagree now. The button offered on EventLogger's own finding must still
  // change UserInterface's file too - the reach is the whole variable, not the one file this
  // finding was filed on.
  driftIn(gui.directory, USER_INTERFACE, "ValueE", "kHz");
  driftIn(gui.directory, EVENT_LOGGER, "ValueE", "kHz");

  const eventRow = page
    .getByRole("row", { name: "definition-mismatch" })
    .filter({ hasText: "event_logger.ddd.json" });
  await eventRow.click();
  await panel.getByRole("button", { name: "Use the unit declared in controller" }).click();
  await expect(panel.getByRole("button", { name: "Apply to 2 files" })).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();

  await expect(page.getByText("Nothing to report")).toBeVisible();
  expect(unitOfValueE(readFileSync(join(gui.directory, USER_INTERFACE)))).toBe("Hz");
  expect(unitOfValueE(readFileSync(join(gui.directory, EVENT_LOGGER)))).toBe("Hz");
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
