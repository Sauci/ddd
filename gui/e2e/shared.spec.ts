import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import { failing, held, PUMP, SERVER_FAILED, writeUnseen } from "./demo";
import { expect, type Gui, test } from "./fixtures";

/** Each vocabulary's file in a copy of examples/vocabulary: its name, which is also the key its
 * list of entries sits under, and the key each entry is named by. */
const FILES = {
  constants: { file: "constants.ddd.json", named: "name" },
  sections: { file: "sections.ddd.json", named: "section" },
  rasters: { file: "rasters.ddd.json", named: "raster" },
} as const;

type Vocabulary = keyof typeof FILES;

/** The entries of one vocabulary's file in a copy, as the file holds them on disk. */
function entriesOf(directory: string, vocabulary: Vocabulary): Record<string, unknown>[] {
  const text = readFileSync(join(directory, FILES[vocabulary].file), "utf8");
  return (JSON.parse(text) as Record<Vocabulary, Record<string, unknown>[]>)[vocabulary];
}

/** One entry of a vocabulary's file in a copy, found by its name, as the file holds it. */
function entryOf(directory: string, vocabulary: Vocabulary, name: string): Record<string, unknown> {
  const entry = entriesOf(directory, vocabulary).find(
    (each) => each[FILES[vocabulary].named] === name,
  );
  if (entry === undefined) throw new Error(`${FILES[vocabulary].file} declares no ${name}`);
  return entry;
}

/** One of Pump's own definitions in the copy's pump.ddd.json, as the file holds it on disk. */
function definitionOf(directory: string, name: string): Record<string, unknown> {
  const { component } = JSON.parse(readFileSync(join(directory, PUMP), "utf8")) as {
    component: { interface: { definition: Record<string, unknown> }[] };
  };
  const found = component.interface.find((each) => each.definition.name === name);
  if (found === undefined) throw new Error(`${PUMP} declares no ${name}`);
  return found.definition;
}

/** Opens an entry's panel the way a reader reaches it: the project, its Shared files tab, then
 * the entry's own row. */
async function openEntry(page: Page, gui: Gui, name: string): Promise<Locator> {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  await page.getByRole("row", { name, exact: true }).click();
  return page.getByRole("complementary", { name });
}

test("a raster nothing measures in is removed, row and panel", async ({ page, vocabularyGui }) => {
  const kept = entriesOf(vocabularyGui.directory, "rasters").filter(
    (entry) => entry.raster !== "100ms",
  );
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  const row = page.getByRole("row", { name: /^100ms/ });
  await row.click();
  const panel = page.getByRole("complementary", { name: "100ms" });
  await expect(
    panel.getByText("Nothing in the project measures in 100ms.", { exact: true }),
  ).toBeVisible();

  // The removal's own plan, shown before the press that applies it: no "Apply to 1 file" here,
  // the button itself says what it does.
  const removing = panel.getByRole("region", { name: "Remove from the rasters" });
  await expect(removing.getByText("Changes 1 file: rasters.ddd.json")).toBeVisible();
  await removing.getByRole("button", { name: "Remove from the rasters" }).click();
  await expect(row).toHaveCount(0);
  await expect(panel).toHaveCount(0);
  await expect(page).toHaveURL(/\/project\?view=shared$/);
  // Gone as the reader asked, so the tab says nothing of its going.
  await expect(page.getByText("no longer declared")).toHaveCount(0);
  // The entry alone, out of the file: the other two rasters are as they were.
  await expect.poll(() => entriesOf(vocabularyGui.directory, "rasters")).toEqual(kept);
});

test("a raster's event, cycle and description are each saved from its panel, and an event another raster claims is refused", async ({
  page,
  vocabularyGui,
}) => {
  const directory = vocabularyGui.directory;
  const before = entryOf(directory, "rasters", "100ms");
  const panel = await openEntry(page, vocabularyGui, "100ms");

  const event = panel.getByRole("region", { name: "Event" });
  const eventField = event.getByRole("textbox", { name: "Event" });
  await expect(eventField).toHaveValue("2");
  await eventField.fill("5");
  await expect(event.getByText("Changes 1 file: rasters.ddd.json")).toBeVisible();
  await event.getByRole("button", { name: "Save" }).click();
  await expect.poll(() => entryOf(directory, "rasters", "100ms")).toEqual({ ...before, event: 5 });
  await expect(event.getByText("Changes 1 file")).toHaveCount(0);

  const cycle = panel.getByRole("region", { name: "Cycle" });
  const cycleField = cycle.getByRole("textbox", { name: "Cycle" });
  await expect(cycleField).toHaveValue("100ms");
  await cycleField.fill("50ms");
  await expect(cycle.getByText("Changes 1 file: rasters.ddd.json")).toBeVisible();
  await cycle.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(() => entryOf(directory, "rasters", "100ms"))
    .toEqual({ ...before, event: 5, cycle: "50ms" });
  await expect(cycle.getByText("Changes 1 file")).toHaveCount(0);

  const describing = panel.getByRole("region", { name: "Description" });
  const description = describing.getByRole("textbox", { name: "Description" });
  await expect(description).toHaveValue("diagnostic task");
  await description.fill("slow diagnostic task");
  await expect(describing.getByText("Changes 1 file: rasters.ddd.json")).toBeVisible();
  await describing.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(() => entryOf(directory, "rasters", "100ms"))
    .toEqual({ ...before, event: 5, cycle: "50ms", description: "slow diagnostic task" });
  await expect(describing.getByText("Changes 1 file")).toHaveCount(0);
  await expect(page.getByRole("row", { name: "100ms", exact: true })).toContainText(
    "event 5, 50ms",
  );

  // An event is the project's alone: 1ms already claims 0, so there is nothing to save.
  await eventField.fill("0");
  await expect(event.getByRole("status")).toHaveText("event 0 is already claimed by raster '1ms'");
  await expect(event.getByRole("button", { name: "Save" })).toHaveCount(0);
});

/** Records, from now on and at every frame the page paints, the name of every panel drawn beside
 * the table, each once, in the order they first came: what a reader sees at each paint, which a
 * wait on any one moment can step over - a panel swapped for another and back within a few
 * frames. Read back with `panelsSeen`. */
async function watchPanels(page: Page): Promise<void> {
  await page.evaluate(() => {
    const seen: string[] = [];
    (window as unknown as { panelsSeen: string[] }).panelsSeen = seen;
    const each = () => {
      for (const aside of document.querySelectorAll("aside")) {
        const name = aside.getAttribute("aria-label") ?? "";
        if (!seen.includes(name)) seen.push(name);
      }
      requestAnimationFrame(each);
    };
    requestAnimationFrame(each);
  });
}

/** Every panel `watchPanels` has seen so far, in the order they first came. */
function panelsSeen(page: Page): Promise<string[]> {
  return page.evaluate(() => (window as unknown as { panelsSeen: string[] }).panelsSeen);
}

test("a raster is renamed everywhere, its panel moving straight to the new name, and a rename onto another raster's name is refused", async ({
  page,
  vocabularyGui,
}) => {
  const directory = vocabularyGui.directory;
  const before = entryOf(directory, "rasters", "1ms");
  const panel = await openEntry(page, vocabularyGui, "1ms");
  const renaming = panel.getByRole("region", { name: "Rename" });
  await renaming.getByRole("textbox", { name: "Rename 1ms to" }).fill("2ms");
  await expect(
    renaming.getByText("Changes 2 files: pump.ddd.json, rasters.ddd.json"),
  ).toBeVisible();
  await watchPanels(page);
  await renaming.getByRole("button", { name: "Apply to 2 files" }).click();

  // The raster and the one definition measured in it, both renamed; and the panel moved onto the
  // new spelling with nothing drawn between the two - not the form declaring "2ms", which the
  // table, not listing it yet, would have had the tab open instead.
  const moved = page.getByRole("complementary", { name: "2ms" });
  await expect(moved.getByRole("textbox", { name: "Rename 2ms to" })).toBeVisible();
  await expect(page).toHaveURL(/\/project\?view=shared&kind=raster&name=2ms$/);
  expect(entryOf(directory, "rasters", "2ms")).toEqual({ ...before, raster: "2ms" });
  expect(definitionOf(directory, "PumpSpeed").raster).toBe("2ms");
  expect(await panelsSeen(page)).toEqual(["1ms", "2ms"]);

  // Onto a name the vocabulary already declares: refused before anything is written, and
  // nothing left to press to write it anyway.
  await moved.getByRole("textbox", { name: "Rename 2ms to" }).fill("10ms");
  await expect(moved.getByRole("region", { name: "Rename" }).getByRole("status")).toHaveText(
    "'10ms' is already a raster this project declares",
  );
  await expect(moved.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
});

/** The Shared files tab loaded at an address naming one entry - a link from a finding, or a
 * bookmark - as a page opened there loads it. Signed in first at the address ddd gui printed,
 * whose token the page keeps for the next address this tab opens. */
async function openAt(
  page: Page,
  gui: Gui,
  kind: "constant" | "section" | "raster",
  name: string,
): Promise<void> {
  await page.goto(gui.address);
  await expect(page.getByRole("link", { name: "Shared files", exact: true })).toBeVisible();
  const origin = new URL(gui.address).origin;
  await page.goto(`${origin}/project?view=shared&kind=${kind}&name=${encodeURIComponent(name)}`);
}

test("a raster nothing declares any longer closes the panel an address opened, and the tab says so, even when the table hears of it first", async ({
  page,
  vocabularyGui,
}) => {
  const path = join(vocabularyGui.directory, FILES.rasters.file);
  // Its panel reached from an address rather than its row: no move of the tab's own picked it,
  // so all that holds it is that the tab drew it.
  await openAt(page, vocabularyGui, "raster", "100ms");
  const panel = page.getByRole("complementary", { name: "100ms" });
  await expect(panel.getByRole("textbox", { name: "Rename 100ms to" })).toBeVisible();

  // The panel's next read of the raster is held until the table has answered without it - the
  // order that swapped the panel for the form declaring "100ms", where the tab should have said
  // the raster went. Held once, and let through whatever happens below.
  const release = await held(
    page,
    (url) => url.pathname === "/api/raster" && url.searchParams.get("name") === "100ms",
  );
  try {
    // Rewritten from outside without 100ms's entry, and still a rasters file that loads.
    const declared = JSON.parse(readFileSync(path, "utf8")) as { rasters: { raster: string }[] };
    declared.rasters = declared.rasters.filter((raster) => raster.raster !== "100ms");
    writeFileSync(path, `${JSON.stringify(declared, null, 2)}\n`);
    await expect(page.getByRole("row", { name: "100ms", exact: true })).toHaveCount(0);
    // The table no longer lists it, and the panel is still the raster's own, waiting for its
    // own answer to say why.
    await expect(panel.getByRole("textbox", { name: "Rename 100ms to" })).toBeVisible();
  } finally {
    release();
  }

  const gone = page.getByRole("status").filter({ hasText: "no longer declared" });
  await expect(gone).toHaveText("100ms is no longer declared in the open project.");
  await expect(panel).toHaveCount(0);
  await expect(page).toHaveURL(/\/project\?view=shared$/);
});

/** The add form for one vocabulary, opened as an address naming an entry nothing declares opens
 * it, pre-filled with that name. */
async function openForm(
  page: Page,
  gui: Gui,
  kind: "constant" | "section" | "raster",
  name: string,
): Promise<Locator> {
  await openAt(page, gui, kind, name);
  const form = page.getByRole("complementary", { name: `Declare a ${kind}` });
  await expect(form.getByRole("textbox", { name: "Name" })).toHaveValue(name);
  return form;
}

test("a project declaring nothing offers a blank form, whose vocabulary brings its fields, and a constant declared from it is listed", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  await expect(
    page.getByText("This project declares nothing in its shared files.", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Declare an entry" }).click();

  // Blank: a chooser and nothing else, until a vocabulary is chosen.
  const blank = page.getByRole("complementary", { name: "Declare an entry" });
  const vocabulary = blank.getByRole("combobox", { name: "Vocabulary" });
  await expect(vocabulary).toHaveValue("");
  await expect(
    blank.getByText("Choose a vocabulary, and the fields it is declared with follow.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(blank.getByRole("textbox")).toHaveCount(0);

  await vocabulary.press("ArrowDown");
  await page.getByRole("option", { name: "constants", exact: true }).click();
  const form = page.getByRole("complementary", { name: "Declare a constant" });
  await form.getByRole("textbox", { name: "Name" }).fill("SPARE_SLOTS");
  await form.getByRole("textbox", { name: "Value" }).fill("4");
  // The demo has no constants file: declaring one writes it, and the project's includes name it.
  await expect(form.getByText("Changes 2 files: constants.ddd.json, demo.ddd.json")).toBeVisible();
  await form.getByRole("button", { name: "Apply to 2 files" }).click();

  await expect(page.getByRole("row", { name: "SPARE_SLOTS", exact: true })).toContainText("4");
  await expect(page.getByRole("complementary", { name: "SPARE_SLOTS" })).toBeVisible();
  await expect
    .poll(() => entriesOf(gui.directory, "constants"))
    .toEqual([{ name: "SPARE_SLOTS", value: 4, description: "" }]);
  const project = JSON.parse(readFileSync(join(gui.directory, "demo.ddd.json"), "utf8"));
  expect(project.project.includes).toContain("constants.ddd.json");
});

test("the add form refuses a section's name the project already declares, and offers no apply", async ({
  page,
  vocabularyGui,
}) => {
  const form = await openForm(page, vocabularyGui, "section", ".spare");
  await form.getByRole("combobox", { name: "Access" }).press("ArrowDown");
  await page.getByRole("option", { name: "read-write", exact: true }).click();
  await form.getByRole("textbox", { name: "Alignment" }).fill("4");
  await expect(form.getByText("Changes 1 file: sections.ddd.json")).toBeVisible();

  await form.getByRole("textbox", { name: "Name" }).fill(".fast_ram");
  await expect(form.getByRole("status")).toHaveText(
    "'.fast_ram' is already a section this project declares",
  );
  await expect(form.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
});

test("the add form refuses a value no constant may state, in the words of a constant's own model", async ({
  page,
  vocabularyGui,
}) => {
  const form = await openForm(page, vocabularyGui, "constant", "SPARE");
  const value = form.getByRole("textbox", { name: "Value" });
  await value.fill("4");
  await expect(form.getByText("Changes 1 file: constants.ddd.json")).toBeVisible();

  // Json a constant's model takes no value from: a string. Typed bare, `oops` is not json at all,
  // and the request is refused before any vocabulary is asked about it.
  await value.fill('"oops"');
  await expect(form.getByRole("status")).toHaveText(
    "\"oops\" is not a value a constant may state, so 'SPARE' cannot take it in " +
      "constants.ddd.json: a whole number a 64 bit target holds, of either sign, or a finite " +
      "fractional one",
  );
  await expect(form.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
});

test("the add form refuses an event another raster already claims", async ({
  page,
  vocabularyGui,
}) => {
  const form = await openForm(page, vocabularyGui, "raster", "5ms");
  const event = form.getByRole("textbox", { name: "Event" });
  await event.fill("3");
  await expect(form.getByText("Changes 1 file: rasters.ddd.json")).toBeVisible();

  await event.fill("0");
  await expect(form.getByRole("status")).toHaveText("event 0 is already claimed by raster '1ms'");
  await expect(form.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
});

test("a constant's value and description are each saved from its panel", async ({
  page,
  vocabularyGui,
}) => {
  const directory = vocabularyGui.directory;
  const before = entryOf(directory, "constants", "TREND_SAMPLES");
  const panel = await openEntry(page, vocabularyGui, "TREND_SAMPLES");

  const value = panel.getByRole("region", { name: "Value" });
  const valueField = value.getByRole("textbox", { name: "Value" });
  await expect(valueField).toHaveValue("16");
  await valueField.fill("32");
  await expect(value.getByText("Changes 1 file: constants.ddd.json")).toBeVisible();
  await value.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(() => entryOf(directory, "constants", "TREND_SAMPLES"))
    .toEqual({ ...before, value: 32 });
  await expect(value.getByText("Changes 1 file")).toHaveCount(0);
  await expect(page.getByRole("row", { name: "TREND_SAMPLES", exact: true })).toContainText("32");

  const describing = panel.getByRole("region", { name: "Description" });
  const description = describing.getByRole("textbox", { name: "Description" });
  await expect(description).toHaveValue(String(before.description));
  await description.fill("slots of the pressure trend buffer");
  await expect(describing.getByText("Changes 1 file: constants.ddd.json")).toBeVisible();
  await describing.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(() => entryOf(directory, "constants", "TREND_SAMPLES"))
    .toEqual({ ...before, value: 32, description: "slots of the pressure trend buffer" });
  await expect(describing.getByText("Changes 1 file")).toHaveCount(0);
  await expect(description).toHaveValue("slots of the pressure trend buffer");
});

test("a constant is renamed everywhere, and a rename onto a name c already holds is refused", async ({
  page,
  vocabularyGui,
}) => {
  const directory = vocabularyGui.directory;
  const before = entryOf(directory, "constants", "TREND_SAMPLES");
  const panel = await openEntry(page, vocabularyGui, "TREND_SAMPLES");
  const renaming = panel.getByRole("region", { name: "Rename" });
  await renaming.getByRole("textbox", { name: "Rename TREND_SAMPLES to" }).fill("TREND_SLOTS");
  await expect(
    renaming.getByText("Changes 2 files: constants.ddd.json, pump.ddd.json"),
  ).toBeVisible();
  await renaming.getByRole("button", { name: "Apply to 2 files" }).click();

  // The constant and the one shape naming it, PressureTrend's dimension, both renamed.
  const moved = page.getByRole("complementary", { name: "TREND_SLOTS" });
  await expect(moved.getByRole("textbox", { name: "Rename TREND_SLOTS to" })).toBeVisible();
  await expect(page).toHaveURL(/\/project\?view=shared&kind=constant&name=TREND_SLOTS$/);
  expect(entryOf(directory, "constants", "TREND_SLOTS")).toEqual({
    ...before,
    name: "TREND_SLOTS",
  });
  expect(definitionOf(directory, "PressureTrend").dimensions).toEqual(["TREND_SLOTS"]);

  // Onto the other constant's name, which c's namespace already holds: refused before anything is
  // written, and nothing left to press to write it anyway.
  await moved.getByRole("textbox", { name: "Rename TREND_SLOTS to" }).fill("PRESSURE_CELLS");
  await expect(moved.getByRole("region", { name: "Rename" }).getByRole("status")).toHaveText(
    "'PRESSURE_CELLS' is the name of the declared constant 'PRESSURE_CELLS', which shares c's " +
      "namespace with the variables",
  );
  await expect(moved.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
});

/** PressureTrend's own `dimensions` in a copy of examples/vocabulary's pump.ddd.json, sized `16`
 * rather than by `TREND_SAMPLES`, from outside the page: the one shape naming the constant, gone,
 * so that nothing in the project names it. Scoped by the declaration's name first, as
 * constants.spec.ts's own `breakPressureTrend` writes the same key; throws where nothing matched,
 * since a copy left naming it would offer no Remove at all. */
function sizePressureTrend(directory: string): void {
  const path = join(directory, PUMP);
  const before = readFileSync(path, "utf8");
  const text = before.replace(
    /("name": "PressureTrend"[\s\S]*?"dimensions": )\["TREND_SAMPLES"\]/,
    "$1[16]",
  );
  if (text === before) throw new Error(`PressureTrend names no TREND_SAMPLES in ${path}`);
  writeFileSync(path, text, "utf8");
}

test("a constant nothing names is removed, row and panel, where one in use says why it cannot be", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("vocabulary", sizePressureTrend);

  // In use: ManifoldPressure is sized by PRESSURE_CELLS, so its panel offers no Remove.
  const used = await openEntry(page, gui, "PRESSURE_CELLS");
  const blocked = used.getByRole("region", { name: "Remove from the constants" });
  await expect(blocked).toHaveText("1 shape names PRESSURE_CELLS, so it cannot be removed.");
  await expect(blocked.getByRole("button")).toHaveCount(0);

  await page.getByRole("row", { name: "TREND_SAMPLES", exact: true }).click();
  const panel = page.getByRole("complementary", { name: "TREND_SAMPLES" });
  await expect(
    panel.getByText("Nothing in the project uses TREND_SAMPLES.", { exact: true }),
  ).toBeVisible();
  const removing = panel.getByRole("region", { name: "Remove from the constants" });
  await expect(removing.getByText("Changes 1 file: constants.ddd.json")).toBeVisible();
  await removing.getByRole("button", { name: "Remove from the constants" }).click();

  await expect(page.getByRole("row", { name: "TREND_SAMPLES", exact: true })).toHaveCount(0);
  await expect(panel).toHaveCount(0);
  await expect(page).toHaveURL(/\/project\?view=shared$/);
  await expect.poll(() => entriesOf(gui.directory, "constants")).toEqual([]);
});

/** What a panel of the Shared files tab says when an Apply is refused because a file changed under
 * its preview. */
const STALE =
  "A file changed on disk, so nothing was written. The page now shows the files as they are.";

test("a save made from a constant's panel that is out of date is refused, and nothing is written", async ({
  page,
  vocabularyGui,
}) => {
  const path = join(vocabularyGui.directory, FILES.constants.file);
  const panel = await openEntry(page, vocabularyGui, "TREND_SAMPLES");
  const value = panel.getByRole("region", { name: "Value" });
  await value.getByRole("textbox", { name: "Value" }).fill("32");
  const save = value.getByRole("button", { name: "Save" });
  await expect(save).toBeEnabled();

  // The file changes under the page, between the preview it holds and the press that sends it:
  // its description, one word for another as long, written where the session's own watcher does
  // not see it (`writeUnseen`), so only the Apply's own fresh read of the bytes does.
  const before = readFileSync(path, "utf8");
  const changed = before.replace("sample slots", "sample cells");
  if (changed === before) throw new Error(`TREND_SAMPLES describes no sample slots in ${path}`);
  writeUnseen(vocabularyGui.directory, FILES.constants.file, changed);
  await save.click();
  await expect(value.getByRole("status")).toHaveText(STALE);
  // Nothing was written: the file is as the change from outside left it.
  expect(readFileSync(path, "utf8")).toBe(changed);
});

test("a constant whose file does not load keeps its panel, naming the file, until the file loads again", async ({
  page,
  vocabularyGui,
}) => {
  const path = join(vocabularyGui.directory, FILES.constants.file);
  const panel = await openEntry(page, vocabularyGui, "TREND_SAMPLES");
  const renaming = panel.getByRole("textbox", { name: "Rename TREND_SAMPLES to" });
  await expect(renaming).toBeVisible();
  const gone = page.getByRole("status").filter({ hasText: "no longer declared" });

  // Saved half-edited, as an editor saves a file being typed into: no file that loads declares
  // TREND_SAMPLES, and the table lists it no longer - but the file that does not load may, so the
  // panel stays, naming it, rather than becoming the form that declares it.
  const whole = readFileSync(path);
  writeFileSync(path, whole.subarray(0, Math.floor(whole.length / 2)));
  await expect(panel.getByRole("alert")).toHaveText(
    "'TREND_SAMPLES' is not declared in any file that loaded, and constants.ddd.json did not load",
  );
  await expect(page.getByRole("row", { name: "TREND_SAMPLES", exact: true })).toHaveCount(0);
  await expect(page.getByRole("complementary", { name: "Declare a constant" })).toHaveCount(0);
  await expect(page).toHaveURL(/\/project\?view=shared&kind=constant&name=TREND_SAMPLES$/);
  await expect(gone).toHaveCount(0);

  // Written back whole, the file loads again and the panel shows the constant again.
  writeFileSync(path, whole);
  await expect(renaming).toBeVisible();
  await expect(panel.getByRole("alert")).toHaveCount(0);
  await expect(gone).toHaveCount(0);
});

test("a section's access, alignment and description are each saved from its panel", async ({
  page,
  vocabularyGui,
}) => {
  const directory = vocabularyGui.directory;
  const before = entryOf(directory, "sections", ".calib");
  const panel = await openEntry(page, vocabularyGui, ".calib");

  // Taken from the chooser, which offers the model's own two words.
  const access = panel.getByRole("region", { name: "Access" });
  const accessField = access.getByRole("combobox", { name: "Access" });
  await expect(accessField).toHaveValue("read-only");
  await accessField.press("ArrowDown");
  await page.getByRole("option", { name: "read-write", exact: true }).click();
  await expect(access.getByText("Changes 1 file: sections.ddd.json")).toBeVisible();
  await access.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(() => entryOf(directory, "sections", ".calib"))
    .toEqual({ ...before, access: "read-write" });
  await expect(access.getByText("Changes 1 file")).toHaveCount(0);

  const alignment = panel.getByRole("region", { name: "Alignment" });
  const alignmentField = alignment.getByRole("textbox", { name: "Alignment" });
  await expect(alignmentField).toHaveValue("4");
  await alignmentField.fill("8");
  await expect(alignment.getByText("Changes 1 file: sections.ddd.json")).toBeVisible();
  await alignment.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(() => entryOf(directory, "sections", ".calib"))
    .toEqual({ ...before, access: "read-write", alignment: 8 });
  await expect(alignment.getByText("Changes 1 file")).toHaveCount(0);

  const describing = panel.getByRole("region", { name: "Description" });
  const description = describing.getByRole("textbox", { name: "Description" });
  await expect(description).toHaveValue(String(before.description));
  await description.fill("calibration flash");
  await expect(describing.getByText("Changes 1 file: sections.ddd.json")).toBeVisible();
  await describing.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(() => entryOf(directory, "sections", ".calib"))
    .toEqual({ ...before, access: "read-write", alignment: 8, description: "calibration flash" });
  await expect(describing.getByText("Changes 1 file")).toHaveCount(0);
  await expect(page.getByRole("row", { name: ".calib", exact: true })).toContainText(
    "read-write, align 8",
  );
});

test("a section renamed onto another section's name is refused, and a section nothing places data in is removed", async ({
  page,
  vocabularyGui,
}) => {
  const declared = entriesOf(vocabularyGui.directory, "sections");
  const panel = await openEntry(page, vocabularyGui, ".fast_ram");
  const renaming = panel.getByRole("region", { name: "Rename" });
  await renaming.getByRole("textbox", { name: "Rename .fast_ram to" }).fill(".calib");
  await expect(renaming.getByRole("status")).toHaveText(
    "'.calib' is already a section this project declares",
  );
  await expect(renaming.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);

  // Both shipped sections hold data, so the one to remove is declared first, from the form.
  const form = await openForm(page, vocabularyGui, "section", ".spare");
  await form.getByRole("combobox", { name: "Access" }).press("ArrowDown");
  await page.getByRole("option", { name: "read-write", exact: true }).click();
  await form.getByRole("textbox", { name: "Alignment" }).fill("4");
  await form.getByRole("button", { name: "Apply to 1 file" }).click();

  const fresh = page.getByRole("complementary", { name: ".spare" });
  await expect(
    fresh.getByText("Nothing in the project places its data in .spare.", { exact: true }),
  ).toBeVisible();
  const removing = fresh.getByRole("region", { name: "Remove from the sections" });
  await expect(removing.getByText("Changes 1 file: sections.ddd.json")).toBeVisible();
  await removing.getByRole("button", { name: "Remove from the sections" }).click();
  await expect(page.getByRole("row", { name: ".spare", exact: true })).toHaveCount(0);
  await expect(fresh).toHaveCount(0);
  await expect(page).toHaveURL(/\/project\?view=shared$/);
  await expect.poll(() => entriesOf(vocabularyGui.directory, "sections")).toEqual(declared);
});

test("a constant's Used by leads to the variable naming it, on its component's page", async ({
  page,
  vocabularyGui,
}) => {
  const panel = await openEntry(page, vocabularyGui, "TREND_SAMPLES");
  const use = panel.getByRole("row", { name: /^PressureTrend/ });
  await expect(use.getByRole("cell")).toHaveText(["PressureTrend", "pump.ddd.json", "Pump"]);
  await use.getByRole("button", { name: "PressureTrend" }).click();

  await expect(page).toHaveURL(/\/component\?file=[^&]*pump\.ddd\.json&variable=PressureTrend$/);
  await expect(page.getByRole("heading", { name: "Pump", level: 1 })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "PressureTrend" })).toBeVisible();
});

test("a raster's Used by leads to the component measuring everything it produces in it, and to no variable", async ({
  page,
  vocabularyGui,
}) => {
  // Pump's own default, which no definition stands between: its row says what it covers.
  const panel = await openEntry(page, vocabularyGui, "10ms");
  const use = panel.getByRole("row", { name: /^Pump/ });
  await expect(use.getByRole("cell")).toHaveText([
    "Pump",
    "pump.ddd.json",
    "everything it produces",
  ]);
  await use.getByRole("button", { name: "Pump" }).click();

  await expect(page).toHaveURL(/\/component\?file=[^&]*pump\.ddd\.json$/);
  await expect(page.getByRole("heading", { name: "Pump", level: 1 })).toBeVisible();
  await expect(page.getByRole("row", { name: "PumpSpeed", exact: true })).toBeVisible();
  await expect(page.getByRole("complementary")).toHaveCount(0);
  // Led there directly: a route naming a variable "Pump" ends on this same address too, once the
  // page finds nothing declares one - and says so, which a reader following a component would
  // read as their own component gone.
  await expect(page.getByText("no longer declared")).toHaveCount(0);
});

test("a shared file saved half-written is named above the table, whatever it declared untold", async ({
  page,
  vocabularyGui,
}) => {
  const path = join(vocabularyGui.directory, FILES.rasters.file);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  await expect(
    page.getByText("2 constants · 3 rasters · 2 sections", { exact: true }),
  ).toBeVisible();

  // Cut in half, the file no longer parses, so not even its kind is known: the tab cannot say the
  // entries missing are its own, only that whatever the file declares is not listed.
  const whole = readFileSync(path);
  writeFileSync(path, whole.subarray(0, Math.floor(whole.length / 2)));
  await expect(page.getByRole("status").filter({ hasText: "did not load" })).toHaveText(
    "rasters.ddd.json did not load, so whatever is declared there is not listed.",
  );
  await expect(page.getByText("2 constants · 2 sections", { exact: true })).toBeVisible();
  await expect(page.getByRole("row", { name: "100ms", exact: true })).toHaveCount(0);
});

test("a shared file that parses but breaks its model is named above the table, the entries declared there missing", async ({
  page,
  vocabularyGui,
}) => {
  const path = join(vocabularyGui.directory, FILES.sections.file);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  await expect(
    page.getByText("2 constants · 3 rasters · 2 sections", { exact: true }),
  ).toBeVisible();

  // .calib aligned to three bytes: still json, and plainly a sections file, but no power of two,
  // so the file fails its own model and does not load.
  const before = readFileSync(path, "utf8");
  const broken = before.replace(
    /("section": "\.calib"[^}]*?"alignment": )4/,
    (_, head: string) => `${head}3`,
  );
  if (broken === before) throw new Error(`.calib states no alignment 4 in ${path}`);
  writeFileSync(path, broken);
  await expect(page.getByRole("status").filter({ hasText: "did not load" })).toHaveText(
    "sections.ddd.json did not load, so the entries declared there are not listed.",
  );
  await expect(page.getByText("2 constants · 3 rasters", { exact: true })).toBeVisible();
  await expect(page.getByRole("row", { name: ".calib", exact: true })).toHaveCount(0);
});

test("the shared files tab says it is reading the project's shared files until they are read", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  // The canvas drawn, so that no tab has asked for the shared files yet: only `SharedPage` asks for
  // them, so the first `/api/shared` is the Shared files tab's own, and held, it is the read this
  // journey is about.
  await expect(page.getByRole("button", { name: "Pump", exact: true })).toBeVisible();
  const reading = page.getByText("Reading the project's shared files…", { exact: true });
  const summary = page.getByText("2 constants · 3 rasters · 2 sections", { exact: true });
  const release = await held(page, "/api/shared");
  try {
    await page.getByRole("link", { name: "Shared files", exact: true }).click();
    // The line stands alone: nothing of the tab is drawn until the shared files are read.
    await expect(reading).toBeVisible();
    await expect(page.getByRole("grid", { name: "Shared files" })).toHaveCount(0);
    await expect(summary).toHaveCount(0);
  } finally {
    release();
  }
  await expect(summary).toBeVisible();
  await expect(reading).toHaveCount(0);
});

test("the shared files failing to load leave the server's own error, with no table and no way to declare", async ({
  page,
  vocabularyGui,
}) => {
  const failed = await failing(page, "/api/shared", "http");
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Shared files", exact: true }).click();
  // A first read that fails shows the error alone, as the server worded it (`SharedPage`): the tab
  // keeps no earlier answer to draw a table from, and says no more than it knows. Not an empty
  // table beside the banner either, which would offer to declare an entry in a project that
  // declares seven.
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  const summary = page.getByText("2 constants · 3 rasters · 2 sections", { exact: true });
  await expect(summary).toHaveCount(0);
  await expect(page.getByRole("grid", { name: "Shared files" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Declare an entry" })).toHaveCount(0);
  expect(failed()).toBeGreaterThanOrEqual(1);
});

/** The three vocabularies' panels, one copy of one shape each (`ConstantPanel.tsx`,
 * `SectionPanel.tsx`, `RasterPanel.tsx`), each with its own reading line, refusal branch and save
 * failure: the entry a journey opens, the path its panel reads that entry from, and the first field
 * the panel draws once it has read it - its region, its role and what it holds. A loop of tests, so
 * that one copy's ablation kills one test. */
const PANELS = [
  {
    kind: "constant",
    name: "TREND_SAMPLES",
    path: "/api/constant",
    region: "Value",
    role: "textbox",
    value: "16",
  },
  {
    kind: "section",
    name: ".calib",
    path: "/api/section",
    region: "Access",
    role: "combobox",
    value: "read-only",
  },
  {
    kind: "raster",
    name: "100ms",
    path: "/api/raster",
    region: "Event",
    role: "textbox",
    value: "2",
  },
] as const;

for (const { kind, name, path, region, role, value } of PANELS) {
  test(`a ${kind}'s panel says it is reading the entry until it is read`, async ({
    page,
    vocabularyGui,
  }) => {
    await page.goto(vocabularyGui.address);
    await page.getByRole("link", { name: "Shared files", exact: true }).click();
    const row = page.getByRole("row", { name, exact: true });
    await expect(row).toBeVisible();

    // The panel's own read of the entry, held until the journey has seen the panel wait for it:
    // that read alone, by its name, so the tab's list and the entry's plans go straight through.
    const release = await held(
      page,
      (url) => url.pathname === path && url.searchParams.get("name") === name,
    );
    const panel = page.getByRole("complementary", { name, exact: true });
    const reading = panel.getByText(`Reading ${name}…`, { exact: true });
    try {
      await row.click();
      // The panel opens at once, under the entry's name, and offers nothing it has not read yet.
      await expect(reading).toBeVisible();
      await expect(panel.getByRole("textbox")).toHaveCount(0);
      await expect(panel.getByRole(role, { name: region, exact: true })).toHaveCount(0);
    } finally {
      release();
    }

    // Read: the entry's own field, and the reading line gone.
    await expect(panel.getByRole(role, { name: region, exact: true })).toHaveValue(value);
    await expect(reading).toHaveCount(0);
  });
}

for (const { kind, name, path, region, role } of PANELS) {
  test(`a ${kind}'s panel whose entry fails to load says why, beside the table`, async ({
    page,
    vocabularyGui,
  }) => {
    // The pathname is exact: the tab's list and the entry's plans go straight through.
    const failed = await failing(page, path, "http");
    const panel = await openEntry(page, vocabularyGui, name);
    const row = page.getByRole("row", { name, exact: true });

    await expect(panel.getByRole("heading", { name, exact: true })).toBeVisible();
    await expect(panel.getByRole("alert")).toHaveText(SERVER_FAILED);
    await expect(panel.getByRole(role, { name: region, exact: true })).toHaveCount(0);
    // The table stays beside it, the entry's row still marked. The table lists the entry, so the
    // tab draws its panel and not the form declaring it; and the failure is not the entry's going,
    // which is `not-found`, where the server's answer here is `internal`.
    await expect(row).toBeVisible();
    await expect(row).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("complementary", { name: `Declare a ${kind}` })).toHaveCount(0);
    await expect(page.getByRole("status").filter({ hasText: "no longer declared" })).toHaveCount(0);
    expect(failed()).toBeGreaterThanOrEqual(1);
  });
}

test("a constant declared inside a component leads to that component's page, where one in a constants file names its file alone", async ({
  page,
  vocabularyGui,
}) => {
  // One in a constants file names that file as text alone: a constants file is no component, with
  // no page of its own to lead to.
  const filed = await openEntry(page, vocabularyGui, "TREND_SAMPLES");
  await expect(filed.locator(".panel-meta")).toHaveText("Declared in constants.ddd.json");
  await expect(filed.getByRole("button", { name: "constants.ddd.json" })).toHaveCount(0);

  // One in a component's own constants names the component's file, and that file is a button.
  await page.getByRole("row", { name: "PRESSURE_CELLS", exact: true }).click();
  const inline = page.getByRole("complementary", { name: "PRESSURE_CELLS", exact: true });
  await expect(inline.locator(".panel-meta")).toHaveText("Declared in pump.ddd.json");
  await inline.getByRole("button", { name: "pump.ddd.json", exact: true }).click();

  // Led to the component's page itself, with no variable of it opened.
  await expect(page).toHaveURL(/\/component\?file=[^&]*pump\.ddd\.json$/);
  await expect(page.getByRole("heading", { name: "Pump", level: 1 })).toBeVisible();
  await expect(page.getByRole("row", { name: "PumpSpeed", exact: true })).toBeVisible();
  await expect(page.getByRole("complementary")).toHaveCount(0);
});

test("the add form's apply that is out of date is refused, and nothing is written", async ({
  page,
  vocabularyGui,
}) => {
  const path = join(vocabularyGui.directory, FILES.constants.file);
  const form = await openForm(page, vocabularyGui, "constant", "SPARE");
  await form.getByRole("textbox", { name: "Value" }).fill("4");
  await expect(form.getByText("Changes 1 file: constants.ddd.json")).toBeVisible();
  const apply = form.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeEnabled();

  // The file changes under the page, between the preview it holds and the press that sends it, as
  // the constant's save journey above has it: its description, one word for another as long,
  // written where the session's own watcher does not see it (`writeUnseen`).
  const before = readFileSync(path, "utf8");
  const changed = before.replace("sample slots", "sample cells");
  if (changed === before) throw new Error(`TREND_SAMPLES describes no sample slots in ${path}`);
  writeUnseen(vocabularyGui.directory, FILES.constants.file, changed);
  await apply.click();

  // Refused, in the form: the plan and its Apply are drawn only under no refusal (`SharedAddView`),
  // so none is left to press while it stands.
  await expect(form.getByRole("status")).toHaveText(STALE);
  await expect(form.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
  // Nothing was written: the file is as the change from outside left it, and declares no SPARE.
  expect(readFileSync(path, "utf8")).toBe(changed);
});

/** One save from each vocabulary's panel: the entry, the region whose field is saved and what is
 * typed into it. The section's is its Alignment, a plain field, where its Access is taken from a
 * chooser. */
const SAVES = [
  { kind: "constant", vocabulary: "constants", name: "TREND_SAMPLES", region: "Value", text: "32" },
  { kind: "section", vocabulary: "sections", name: ".calib", region: "Alignment", text: "8" },
  { kind: "raster", vocabulary: "rasters", name: "100ms", region: "Event", text: "5" },
] as const;

for (const { kind, vocabulary, name, region, text } of SAVES) {
  test(`a save made from a ${kind}'s panel that the server fails on says so in its words, keeps its plan and its Save, and is sent once`, async ({
    page,
    vocabularyGui,
  }) => {
    const before = entryOf(vocabularyGui.directory, vocabulary, name);
    const panel = await openEntry(page, vocabularyGui, name);
    const saving = panel.getByRole("region", { name: region });
    await saving.getByRole("textbox", { name: region }).fill(text);
    const plan = saving.getByText(`Changes 1 file: ${FILES[vocabulary].file}`, { exact: true });
    await expect(plan).toBeVisible();

    // Failed from here on, and the one press below is the only Apply sent.
    const failed = await failing(page, "/api/edit", "http");
    const save = saving.getByRole("button", { name: "Save" });
    await save.click();
    await expect(saving.getByRole("status")).toHaveText(`The change was refused: ${SERVER_FAILED}`);
    // The plan and its Save stay under the refusal, the Save offered again once the page has asked
    // for the plans again: unlike the add form's, a panel's refusal withdraws nothing.
    await expect(plan).toBeVisible();
    await expect(save).toBeEnabled();
    expect(failed()).toBe(1);
    // A guard against a write by another path: the POST is answered by `failing`, not the server.
    expect(entryOf(vocabularyGui.directory, vocabulary, name)).toEqual(before);
  });
}
