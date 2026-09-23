import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { driftIn, PUMP, UNITS } from "./demo";
import { expect, test } from "./fixtures";

/** The entries of a units file as it stands on disk: objects, in both examples' units files. */
function entriesOf(file: string): { unit: string; description: string }[] {
  return (
    JSON.parse(readFileSync(file, "utf8")) as { units: { unit: string; description: string }[] }
  ).units;
}

/** The demo's units in use, as adoption lists them: sorted, code unit by code unit. */
const DEMO_UNITS = ["%", "Hz", "V", "degC", "ms"];

test("adopting writes the units in use into a units file the project includes, and reports nothing more", async ({
  page,
  gui,
}) => {
  const adopted = join(gui.directory, UNITS);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Table" }).click();
  const summary = page.locator(".summary");
  await expect(summary).toBeVisible();
  const reported = await summary.innerText();

  await page.getByRole("link", { name: "Units" }).click();
  await expect(page).toHaveURL(/\?view=units$/);
  await expect(page.getByText("5 units · no units file")).toBeVisible();
  // Without a units file, a unit's panel says where it is stated, and nothing of a vocabulary.
  await page.getByRole("row", { name: "ms", exact: true }).click();
  const ms = page.getByRole("complementary", { name: "ms" });
  await expect(ms.getByText("stated in 1 place, 1 file", { exact: true })).toBeVisible();
  const banner = page.getByRole("status").filter({ hasText: "This project has no units file" });
  await expect(banner).toContainText("with the 5 units in use");
  await banner.getByRole("button", { name: "Show changes" }).click();
  const preview = page.getByRole("complementary", { name: "Adopt a vocabulary" });
  await expect(preview.getByText("Changes 2 files: demo.ddd.json, units.ddd.json")).toBeVisible();
  await expect(preview.getByText("units.ddd.json, new")).toBeVisible();
  await preview.getByRole("button", { name: "Adopt 5 units" }).click();

  // The file created, listing every unit in use, and included in the project.
  await expect.poll(() => existsSync(adopted)).toBe(true);
  expect(entriesOf(adopted)).toEqual(DEMO_UNITS.map((unit) => ({ unit, description: "" })));
  const project = JSON.parse(readFileSync(join(gui.directory, "demo.ddd.json"), "utf8"));
  expect(project.project.includes).toContain(UNITS);
  await expect(page.getByText("5 units · all in the vocabulary")).toBeVisible();
  await expect(banner).toHaveCount(0);
  await expect(preview).toHaveCount(0);

  // Every unit is in the vocabulary now, with a description to write.
  for (const unit of DEMO_UNITS) {
    await page.getByRole("row", { name: unit, exact: true }).click();
    const panel = page.getByRole("complementary", { name: unit });
    await expect(panel.getByText("in the vocabulary, units.ddd.json")).toBeVisible();
    await expect(panel.getByRole("textbox", { name: "Description" })).toHaveValue("");
  }

  // And nothing is reported that was not reported before.
  await page.getByRole("link", { name: "Table" }).click();
  await expect(summary).toHaveText(reported);
});

test("a unit renamed from its panel is renamed everywhere, merging into the vocabulary's spelling", async ({
  page,
  vocabularyGui,
}) => {
  const pump = join(vocabularyGui.directory, PUMP);
  const units = join(vocabularyGui.directory, UNITS);
  // PumpSpeed's unit drifted to a spelling the vocabulary does not list, saved from outside.
  const before = driftIn(vocabularyGui.directory, PUMP, "PumpSpeed", "RPM");
  const vocabulary = readFileSync(units);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await expect(page.getByText("5 units · 1 not in the vocabulary")).toBeVisible();
  // Its finding puts it first.
  await expect(page.getByRole("rowheader").first()).toHaveText("RPM");
  await page.getByRole("row", { name: "RPM", exact: true }).click();

  const panel = page.getByRole("complementary", { name: "RPM" });
  await expect(panel.getByText("not in the vocabulary · stated in 1 place, 1 file")).toBeVisible();
  await expect(panel.getByText("unknown-unit", { exact: true })).toBeVisible();
  const renaming = panel.getByRole("region", { name: "Rename" });
  const picker = renaming.getByRole("combobox", { name: "Rename RPM to" });

  // Taken from the list: another unit of the vocabulary, which RPM would merge into.
  await renaming.getByRole("button", { name: "Show the choices for Rename RPM to" }).click();
  await page.getByRole("option", { name: "kPa", exact: true }).click();
  await expect(picker).toHaveValue("kPa");
  await expect(
    renaming.getByText(
      "Changes 1 file: pump.ddd.json. kPa is in the vocabulary already, so RPM merges into it.",
    ),
  ).toBeVisible();

  // Typed and confirmed with Enter: the spelling the finding suggests.
  await picker.fill("rpm");
  await picker.press("Enter");
  await expect(picker).toHaveValue("rpm");
  await expect(
    renaming.getByText(
      "Changes 1 file: pump.ddd.json. rpm is in the vocabulary already, so RPM merges into it.",
    ),
  ).toBeVisible();
  await renaming.getByRole("button", { name: "Show changes" }).click();
  await expect(renaming.locator(".hunk .removed")).toHaveText(['- "unit": "RPM",']);
  await expect(renaming.locator(".hunk .added")).toHaveText(['+ "unit": "rpm",']);
  await renaming.getByRole("button", { name: "Apply to 1 file" }).click();

  // The file is as it was before the drift, and the vocabulary untouched: rpm was listed.
  await expect.poll(() => readFileSync(pump).equals(before)).toBe(true);
  expect(readFileSync(units).equals(vocabulary)).toBe(true);
  // The panel follows the unit to its one spelling; the other is gone from the tab, unannounced.
  const merged = page.getByRole("complementary", { name: "rpm" });
  await expect(
    merged.getByText("in the vocabulary, units.ddd.json · stated in 1 place, 1 file"),
  ).toBeVisible();
  await expect(page).toHaveURL(/\?view=units&unit=rpm$/);
  await expect(page.getByRole("row", { name: "RPM", exact: true })).toHaveCount(0);
  await expect(page.getByText("4 units · all in the vocabulary")).toBeVisible();
  await expect(page.getByText("no longer stated or listed")).toHaveCount(0);
});

test("the vocabulary is described, added to and pruned from the units' panels", async ({
  page,
  vocabularyGui,
}) => {
  const units = join(vocabularyGui.directory, UNITS);
  // ManifoldPressure's unit drifted to a spelling the vocabulary does not list; PressureTrend
  // still states kPa.
  driftIn(vocabularyGui.directory, PUMP, "ManifoldPressure", "mbar");
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await expect(page.getByText("5 units · 1 not in the vocabulary")).toBeVisible();

  // Described: its entry's description, written on Save.
  await page.getByRole("row", { name: "rpm", exact: true }).click();
  const rpm = page.getByRole("complementary", { name: "rpm" });
  const describing = rpm.getByRole("region", { name: "Description" });
  const description = describing.getByRole("textbox", { name: "Description" });
  await expect(description).toHaveValue("rotational speed, revolutions per minute");
  await description.fill("revolutions per minute");
  await expect(describing.getByText("Changes 1 file: units.ddd.json")).toBeVisible();
  await describing.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(() => entriesOf(units)[0])
    .toEqual({ unit: "rpm", description: "revolutions per minute" });
  await expect(describing.getByText("Changes 1 file")).toHaveCount(0);
  await expect(description).toHaveValue("revolutions per minute");

  // Added: the unit outside the vocabulary, in the form the file's entries take.
  await page.getByRole("row", { name: "mbar", exact: true }).click();
  const mbar = page.getByRole("complementary", { name: "mbar" });
  await expect(mbar.getByText("not in the vocabulary · stated in 1 place, 1 file")).toBeVisible();
  const adding = mbar.getByRole("region", { name: "Add to the vocabulary" });
  await expect(adding.getByText("Changes 1 file: units.ddd.json")).toBeVisible();
  await adding.getByRole("button", { name: "Show changes" }).click();
  await expect(adding.locator(".hunk .added").last()).toContainText('"mbar"');
  await adding.getByRole("button", { name: "Add to the vocabulary" }).click();
  await expect.poll(() => entriesOf(units)).toContainEqual({ unit: "mbar", description: "" });
  await expect(
    mbar.getByText("in the vocabulary, units.ddd.json · stated in 1 place, 1 file"),
  ).toBeVisible();
  await expect(mbar.getByRole("textbox", { name: "Description" })).toHaveValue("");

  // Removed: a unit nothing states, and its panel with it, without a word of its going.
  await page.getByRole("row", { name: "degC", exact: true }).click();
  const degC = page.getByRole("complementary", { name: "degC" });
  await expect(degC.getByText("in the vocabulary, units.ddd.json · stated nowhere")).toBeVisible();
  const removing = degC.getByRole("region", { name: "Remove from the vocabulary" });
  await removing.getByRole("button", { name: "Remove from the vocabulary" }).click();
  await expect
    .poll(() => entriesOf(units).map((entry) => entry.unit))
    .toEqual(["rpm", "Nm", "kPa", "mbar"]);
  await expect(degC).toHaveCount(0);
  await expect(page.getByRole("row", { name: "degC", exact: true })).toHaveCount(0);
  await expect(page).toHaveURL(/\?view=units$/);
  await expect(page.getByText("no longer stated or listed")).toHaveCount(0);
});

test("an apply made from a panel that is out of date is refused, and the panel shows the files as they are", async ({
  page,
  vocabularyGui,
}) => {
  const units = join(vocabularyGui.directory, UNITS);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await page.getByRole("row", { name: "degC", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "degC" });
  const removing = panel.getByRole("region", { name: "Remove from the vocabulary" });
  await expect(removing.getByText("Changes 1 file: units.ddd.json")).toBeVisible();

  // Described from outside between the preview and Apply.
  await page.route("**/api/edit", async (route) => {
    writeFileSync(
      units,
      readFileSync(units, "utf8").replace('"temperature"', '"temperature, degrees Celsius"'),
    );
    await route.continue();
  });
  await removing.getByRole("button", { name: "Remove from the vocabulary" }).click();
  const refused = removing.getByRole("status").filter({ hasText: "changed on disk" });
  await expect(refused).toBeVisible();
  await expect(panel.getByRole("textbox", { name: "Description" })).toHaveValue(
    "temperature, degrees Celsius",
  );
  expect(entriesOf(units).map((entry) => entry.unit)).toContain("degC");

  // Chosen again, once the server has caught up with the file as it now is, it is applied. The
  // server checks the disk once a second (Session.poll_interval), and only a plan asked for
  // after that carries the file's new fingerprint. The sentence is what says so: it is held
  // until the analysis moves past the revision the edit was refused at, so its going is the
  // page saying it has taken the newer one on board - and the preview goes with it until the
  // plan asked for again answers, which is what puts the Apply back. Waiting instead on the
  // response that carries that revision let this press land in the moment between the two,
  // sending the very fingerprints the server had just refused; the same wait as keys.spec.ts's
  // "a change refused as stale can be applied again once the analysis has caught up".
  await page.unroute("**/api/edit");
  await expect(refused).toBeHidden({ timeout: 15000 });
  await removing.getByRole("button", { name: "Remove from the vocabulary" }).click();
  await expect
    .poll(() => entriesOf(units).map((entry) => entry.unit))
    .toEqual(["rpm", "Nm", "kPa"]);
});

test("a unit nothing states any longer closes its panel and the tab says so, but not while a file does not load", async ({
  page,
  vocabularyGui,
}) => {
  const pump = join(vocabularyGui.directory, PUMP);
  const before = driftIn(vocabularyGui.directory, PUMP, "PumpSpeed", "RPM");
  const drifted = readFileSync(pump);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await page.getByRole("row", { name: "RPM", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "RPM" });
  const picker = panel.getByRole("combobox", { name: "Rename RPM to" });
  await expect(picker).toBeVisible();
  await expect(page).toHaveURL(/\?view=units&unit=RPM$/);
  const bookmark = page.url();

  // Saved half-edited, as an editor saves a file being typed into: nothing that loads states RPM,
  // but the file that does not load may, and the panel stays, naming it.
  writeFileSync(pump, drifted.subarray(0, Math.floor(drifted.length / 2)));
  await expect(panel.getByRole("alert")).toContainText("pump.ddd.json");
  await expect(page).toHaveURL(/\?view=units&unit=RPM$/);
  writeFileSync(pump, drifted);
  await expect(picker).toBeVisible();

  // Renamed back from outside: nothing states RPM any longer, and its panel closes, saying so.
  writeFileSync(pump, before);
  const gone = page
    .getByRole("status")
    .filter({ hasText: "RPM is no longer stated or listed in the open project." });
  await expect(gone).toBeVisible();
  await expect(panel).toHaveCount(0);
  await expect(page).toHaveURL(/\?view=units$/);

  // Another unit selected, the banner has said what it had to.
  await page.getByRole("row", { name: "rpm", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "rpm" })).toBeVisible();
  await expect(gone).toHaveCount(0);

  // An address naming it from before - a bookmark - is answered the same way.
  await page.goto(bookmark);
  await expect(gone).toBeVisible();
  await expect(page.getByRole("complementary", { name: "RPM" })).toHaveCount(0);
  await expect(page).toHaveURL(/\?view=units$/);
});
