import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER, driftIn, failing, held, PUMP, SERVER_FAILED, UNITS } from "./demo";
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

/** What the Units tab says when an Apply is refused because a file changed under its preview. */
const STALE =
  "A file changed on disk, so nothing was written. The page now shows the files as they are.";

test("an adopt refused because its units file now exists says so in the banner, which goes once the units are read again", async ({
  page,
  gui,
}) => {
  const adopted = join(gui.directory, UNITS);
  const project = join(gui.directory, "demo.ddd.json");
  const before = readFileSync(project);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units" }).click();
  await expect(page.getByText("5 units · no units file")).toBeVisible();
  const banner = page.getByRole("status").filter({ hasText: "This project has no units file" });
  await banner.getByRole("button", { name: "Show changes" }).click();
  const preview = page.getByRole("complementary", { name: "Adopt a vocabulary" });
  await expect(preview.getByText("Changes 2 files: demo.ddd.json, units.ddd.json")).toBeVisible();

  // A units file made by hand between the preview and the press. The project does not include it,
  // so the watcher has nothing to notice, and the page still holds a preview that creates a file
  // which now exists.
  const written = `${JSON.stringify({ units: [{ unit: "ms", description: "milliseconds" }] })}\n`;
  writeFileSync(adopted, written);

  // Once that file is there the server offers no adoption (`ddd.lsp.units.adoption` refuses to
  // write over it), so the banner, the refusal in it, goes as soon as the page reads the units
  // again - which it does the moment its Apply is answered, a few tens of milliseconds after the
  // refusal is drawn: a window that polling finds only by luck. The units the page reads next are
  // held until the refusal has been seen, once only: the ones it reads later go straight through.
  const release = await held(page, "/api/units");
  try {
    await preview.getByRole("button", { name: "Adopt 5 units" }).click();
    await expect(banner.getByText(STALE, { exact: true })).toBeVisible();
    // Nothing was written: the project does not include the file, and the file is the reader's.
    expect(readFileSync(project).equals(before)).toBe(true);
    expect(readFileSync(adopted, "utf8")).toBe(written);
  } finally {
    release();
  }
  await expect(banner).toHaveCount(0);
  await expect(preview).toHaveCount(0);
  await expect(page.getByText("5 units · no units file")).toBeVisible();
});

test("the units tab says it is reading the project's units until they are read", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  // The canvas drawn, so that no tab has asked for the units yet: the first `/api/units` is the
  // Units tab's own (only `UnitsPage`, `UnitPanel`, `TypePanel` and `VariablePanel` ask for them),
  // and held, it is the read this journey is about.
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();
  const reading = page.getByText("Reading the project's units…", { exact: true });
  const summary = page.getByText("5 units · no units file", { exact: true });
  const release = await held(page, "/api/units");
  try {
    await page.getByRole("link", { name: "Units", exact: true }).click();
    // The line stands alone: nothing of the tab is drawn until the units are read.
    await expect(reading).toBeVisible();
    await expect(page.getByRole("grid", { name: "Units" })).toHaveCount(0);
    await expect(summary).toHaveCount(0);
  } finally {
    release();
  }
  await expect(summary).toBeVisible();
  await expect(reading).toHaveCount(0);
});

test("the units failing to load leave the server's own error, with no table", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, "/api/units", "http");
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units", exact: true }).click();
  // A first read that fails shows the error alone, as the server worded it (`UnitsPage`): the tab
  // keeps no earlier answer to draw a table from, and says no more than it knows.
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(page.getByText(/ units · /)).toHaveCount(0);
  await expect(page.getByRole("grid", { name: "Units" })).toHaveCount(0);
  await expect(
    page.getByRole("status").filter({ hasText: "This project has no units file" }),
  ).toHaveCount(0);
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("a unit's panel says it is reading the unit until it is read", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units", exact: true }).click();
  const row = page.getByRole("row", { name: "ms", exact: true });
  await expect(row).toBeVisible();
  // The unit's own read alone: the list is read already, and `/api/units` is another path.
  const release = await held(
    page,
    (url) => url.pathname === "/api/unit" && url.searchParams.get("name") === "ms",
  );
  const panel = page.getByRole("complementary", { name: "ms", exact: true });
  const reading = panel.getByText("Reading ms…", { exact: true });
  const renaming = panel.getByRole("combobox", { name: "Rename ms to" });
  try {
    await row.click();
    await expect(reading).toBeVisible();
    await expect(renaming).toHaveCount(0);
  } finally {
    release();
  }
  // The demo has no units file, so the panel's line is the places alone.
  await expect(panel.getByText("stated in 1 place, 1 file", { exact: true })).toBeVisible();
  await expect(reading).toHaveCount(0);
  await expect(renaming).toBeVisible();
});

test("a unit's panel whose unit fails to load says why, beside the table", async ({
  page,
  gui,
}) => {
  // The pathname is exact: `/api/units`, which draws the table, and `/api/unit-plan` go through.
  const failed = await failing(page, "/api/unit", "http");
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units", exact: true }).click();
  const row = page.getByRole("row", { name: "ms", exact: true });
  await row.click();

  const panel = page.getByRole("complementary", { name: "ms", exact: true });
  await expect(panel.getByRole("heading", { name: "ms" })).toBeVisible();
  await expect(panel.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(panel.getByRole("combobox", { name: "Rename ms to" })).toHaveCount(0);
  // The table stays beside it, and the failure is not the unit's going: that is `not-found`, and
  // the server's answer here is `internal`.
  await expect(row).toBeVisible();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "ms is no longer stated or listed in the open project." }),
  ).toHaveCount(0);
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("a units file listing no unit has the units in use adopted into it, and nothing else written", async ({
  page,
  copiedGui,
}) => {
  // examples/vocabulary with its units file emptied before the server starts. The project includes
  // the file already, so adopting fills it (`adopt_units`'s `into`): nothing is created and no
  // include is added.
  const gui = await copiedGui("vocabulary", (directory) => {
    writeFileSync(join(directory, UNITS), '{ "units": [] }\n', "utf8");
  });
  const units = join(gui.directory, UNITS);
  const project = join(gui.directory, "project.ddd.json");
  const projectBefore = readFileSync(project);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units", exact: true }).click();
  // A project with a units file is opted in to the check, so each unit it states is outside it.
  await expect(page.getByText("3 units · 3 not in the vocabulary", { exact: true })).toBeVisible();

  // The sentence for a units file that lists nothing, not the one for a project with no file
  // (`adoptionSentence`).
  const banner = page.getByRole("status").filter({ hasText: "No unit this project states" });
  await expect(
    banner.getByText(
      "No unit this project states is in its vocabulary. Adopting lists the 3 units in use in a units file: nothing is reported that is not reported today.",
      { exact: true },
    ),
  ).toBeVisible();
  await banner.getByRole("button", { name: "Show changes" }).click();
  const preview = page.getByRole("complementary", { name: "Adopt a vocabulary" });
  await expect(preview.getByText("Changes 1 file: units.ddd.json", { exact: true })).toBeVisible();
  await expect(preview.getByText("units.ddd.json, new")).toHaveCount(0);
  await preview.getByRole("button", { name: "Adopt 3 units" }).click();

  // The units in use, in code point order, each with an empty description; nothing else written.
  await expect
    .poll(() => entriesOf(units))
    .toEqual(["Nm", "kPa", "rpm"].map((unit) => ({ unit, description: "" })));
  expect(readFileSync(project).equals(projectBefore)).toBe(true);
  await expect(page.getByText("3 units · all in the vocabulary", { exact: true })).toBeVisible();
  await expect(banner).toHaveCount(0);
  await expect(preview).toHaveCount(0);
});

/** Every `unit` key taken out of the named files of a copy, wherever it is written: on a
 * declaration, a scalar type or a structure member. Rewritten whole, as `typeCurveA` (demo.ts)
 * rewrites a file whose shape changes: a line taken out by text would leave a comma behind where
 * the unit was the last key of its object (Sample_t's `timestamp`). */
function stateNoUnit(directory: string, files: readonly string[]): void {
  const stripped = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(stripped);
    if (value === null || typeof value !== "object") return value;
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => key !== "unit")
        .map(([key, inner]) => [key, stripped(inner)]),
    );
  };
  for (const file of files) {
    const path = join(directory, file);
    const text = JSON.stringify(stripped(JSON.parse(readFileSync(path, "utf8"))), null, 2);
    writeFileSync(path, `${text}\n`, "utf8");
  }
}

test("a project stating no unit is told there is nothing to adopt, and offered nothing to press", async ({
  page,
  copiedGui,
}) => {
  // examples/structures states a unit in two files only: degC (sensing.ddd.json's InletTemperature
  // and types.ddd.json's Temperature_t) and ms (Sample_t's `timestamp` member). Without them it
  // states none, and has no units file.
  const gui = await copiedGui("structures", (directory) => {
    stateNoUnit(directory, ["sensing.ddd.json", "types.ddd.json"]);
  });
  // Every ask for a plan, recorded from the start: the page must make none. A listener intercepts
  // nothing, so it leaves no request hanging into the teardown (P19b-7).
  const asked: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/unit-plan") asked.push(request.url());
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units", exact: true }).click();
  await expect(page.getByText("0 units · no units file", { exact: true })).toBeVisible();

  const banner = page.getByRole("status").filter({ hasText: "This project has no units file" });
  await expect(banner).toHaveText(
    "This project has no units file, so no unit is checked against a vocabulary. It states no unit, so there is nothing to adopt.",
  );
  // `AdoptBannerView` draws its buttons only under a plan, and `adoptionAsked` asks none for 0.
  await expect(banner.getByRole("button", { name: "Show changes" })).toHaveCount(0);
  await expect(banner.getByRole("button", { name: /^Adopt/ })).toHaveCount(0);

  // A plan the page asked for would be asked as the tab opened, and refused a few tens of
  // milliseconds later - after the assertions above had passed: the banner's whole text is read
  // before the refusal joins it. The reader leaves the tab, and whatever it asked for on its way
  // in has been asked by then.
  await page.getByRole("link", { name: "Table", exact: true }).click();
  await expect(page.getByRole("grid", { name: "Components" })).toBeVisible();
  expect(asked).toEqual([]);
});

test("a removal the server fails on says so in its words, and nothing is written", async ({
  page,
  vocabularyGui,
}) => {
  const units = join(vocabularyGui.directory, UNITS);
  const before = readFileSync(units);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Units", exact: true }).click();
  await page.getByRole("row", { name: "degC", exact: true }).click();
  // degC is listed and stated by nothing, so its panel offers its removal.
  const panel = page.getByRole("complementary", { name: "degC", exact: true });
  const removing = panel.getByRole("region", { name: "Remove from the vocabulary" });
  await expect(removing.getByText("Changes 1 file: units.ddd.json", { exact: true })).toBeVisible();

  // The page's only request to `/api/edit` is an Apply's POST, which is never sent again.
  const failed = await failing(page, "/api/edit", "http");
  const remove = removing.getByRole("button", { name: "Remove from the vocabulary" });
  await remove.click();
  // The server's own words behind `refusalOf`'s prefix, drawn by `Outcome` above the plan, which
  // is asked for again.
  await expect(removing.getByRole("status")).toHaveText(`The change was refused: ${SERVER_FAILED}`);
  expect(readFileSync(units).equals(before)).toBe(true);
  expect(entriesOf(units).map((entry) => entry.unit)).toContain("degC");
  expect(failed()).toBe(1);
  // The refusal does not take the removal away: it is offered again once the plan is.
  await expect(remove).toBeVisible();
  await expect(remove).toBeEnabled();
});

test("a rename the plan refuses says why in the panel, and offers nothing to apply", async ({
  page,
  gui,
}) => {
  const controller = join(gui.directory, CONTROLLER);
  const before = readFileSync(controller);
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units", exact: true }).click();
  await page.getByRole("row", { name: "ms", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "ms", exact: true });
  const renaming = panel.getByRole("region", { name: "Rename" });
  const picker = renaming.getByRole("combobox", { name: "Rename ms to" });

  // A spelling with a space around it: the plan the server is asked for is refused, in its own
  // words (`ddd.lsp.units._spelling`), and the panel draws that refusal where the plan would be.
  await picker.fill(" x");
  await picker.press("Enter");
  await expect(renaming.getByRole("status")).toHaveText("' x' has spaces around it");
  await expect(renaming.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
  expect(readFileSync(controller).equals(before)).toBe(true);
});

test("a unit listed twice is flagged by its chip, and its panel says it is already declared", async ({
  page,
  copiedGui,
}) => {
  // examples/vocabulary with rpm listed a second time in its units file, before the server starts.
  const gui = await copiedGui("vocabulary", (directory) => {
    const path = join(directory, UNITS);
    const file = JSON.parse(readFileSync(path, "utf8")) as {
      units: { unit: string; description: string }[];
    };
    file.units.push({ unit: "rpm", description: "listed a second time" });
    writeFileSync(path, `${JSON.stringify(file, null, 2)}\n`, "utf8");
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Units", exact: true }).click();
  await expect(page.getByText("4 units · all in the vocabulary", { exact: true })).toBeVisible();

  // A unit with a finding comes first, and its row draws the check's name: the only chip on the
  // page (`findingCheck`).
  await expect(page.getByRole("rowheader").first()).toHaveText("rpm");
  const row = page.getByRole("row", { name: "rpm", exact: true });
  await expect(row.locator(".chip")).toHaveText("duplicate-unit");
  await expect(page.locator(".chip")).toHaveCount(1);

  await row.click();
  const panel = page.getByRole("complementary", { name: "rpm", exact: true });
  await expect(panel.getByRole("listitem")).toHaveText([
    "duplicate-unit unit 'rpm' is already declared",
  ]);
});
