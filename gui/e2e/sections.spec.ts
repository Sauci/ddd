import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { PUMP } from "./demo";
import { expect, test } from "./fixtures";

/** PumpSpeed's own `section` in a copy of examples/vocabulary's pump.ddd.json, moved to a
 * section no file of the project declares - `.fast_buffer` rather than the `.fast_ram` the file
 * ships with - from outside the page, the way `constants.spec.ts`'s own `breakPressureTrend`
 * writes a file: scoped by the declaration's name first, so that ManifoldPressure's own
 * `.fast_ram` two declarations below stays where it is and the copy keeps exactly one thing
 * wrong with it.
 *
 * Throws where nothing matched. A replace that found no `section` key would leave a copy that
 * checks clean, and every assertion below would then be waiting for a finding this journey never
 * made - a failure reported as a timeout on the Findings tab, twenty seconds away from saying
 * what actually happened. */
function misplacePumpSpeed(directory: string): void {
  const path = join(directory, PUMP);
  const before = readFileSync(path, "utf8");
  const text = before.replace(
    /("name": "PumpSpeed"[\s\S]*?"section": )"\.fast_ram"/,
    '$1".fast_buffer"',
  );
  if (text === before) throw new Error(`PumpSpeed states no '.fast_ram' section in ${path}`);
  writeFileSync(path, text, "utf8");
}

test("a finding nobody could act on becomes a section declared in two clicks", async ({
  page,
  vocabularyGui,
}) => {
  misplacePumpSpeed(vocabularyGui.directory);

  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Findings" }).click();

  await page.getByRole("row", { name: "unknown-section" }).click();
  const finding = page.getByRole("complementary", { name: "unknown-section" });
  await expect(finding.locator(".chip")).toHaveText("error");
  // The subject as well as the check, where the finding is read: which definition, and which
  // section it names. The check id and the clause below are true of a complaint about any
  // definition in any project, and this copy is broken in exactly one place on purpose - the
  // assertion that says so belongs here rather than only in the route the next line follows.
  await expect(finding).toContainText("'PumpSpeed' is placed in '.fast_buffer'");
  await expect(
    finding.getByText("is not a section any file of this project declares"),
  ).toBeVisible();

  await finding.getByRole("link", { name: "Open .fast_buffer" }).click();

  // The Shared files tab, the add form open and pre-filled: `.fast_buffer` names nothing the
  // project declares yet, and `SharedPage`'s own `isDeclared` is what turns that into the form
  // rather than a panel - the very same address a declared section's own panel opens from, and
  // the same shape the constants journey lands on with `kind=constant`. "One route kind, and the
  // page decides" is part 13's design saying it, which this part inherits rather than restates;
  // its own design says only that `route_of` gains a section route (§4.5).
  await expect(page).toHaveURL(/\/project\?view=shared&kind=section&name=\.fast_buffer$/);
  const form = page.getByRole("complementary", { name: "Declare a section" });
  await expect(form.getByRole("textbox", { name: "Name" })).toHaveValue(".fast_buffer");

  // Both of a section's required keys, because the model defaults neither: a section declared
  // without either is one whose file would not load, where a constant's add needs its one value.
  // The access is taken from the chooser rather than typed - the model's own two words are the
  // list, and picking one is what spares a reader guessing at the spelling; the alignment is
  // typed, being a number nobody can offer a list of.
  await form.getByRole("combobox", { name: "Access" }).press("ArrowDown");
  await page.getByRole("option", { name: "read-write", exact: true }).click();
  await expect(form.getByRole("combobox", { name: "Access" })).toHaveValue("read-write");
  await form.getByRole("textbox", { name: "Alignment" }).fill("4");

  // The preview, which is also the wait: the sentence naming the file arrives with the plan the
  // Apply button is drawn under, so there is no press to make before the server has said what
  // pressing it would change. It names the project's own sections file, not a new one - this
  // copy includes one already, and `add` appends to the first of the vocabulary's files.
  await expect(form.getByText("Changes 1 file: sections.ddd.json")).toBeVisible();
  await form.getByRole("button", { name: "Apply to 1 file" }).click();

  // Declared: the tab moves onto the new section's own panel, holding what was just declared,
  // and the table beside it gains the row - the reader's second click, from a finding nobody
  // could act on. The row arrives already used once: the definition that complained places its
  // data in something the project declares now, which is the whole point of the route.
  const panel = page.getByRole("complementary", { name: ".fast_buffer" });
  await expect(panel.getByRole("combobox", { name: "Access" })).toHaveValue("read-write");
  await expect(panel.getByRole("textbox", { name: "Alignment" })).toHaveValue("4");
  const row = page.getByRole("row", { name: ".fast_buffer" });
  await expect(row).toContainText("sections");
  await expect(row).toContainText("read-write, align 4");
  await expect(row).toContainText("1 place");

  // And the finding itself is gone: examples/vocabulary checks clean, and giving back the one
  // section this journey took away is the only thing standing between it and clean again.
  // `read-write` and `4` are what keep it that way - PumpSpeed is a measurement, which the
  // software writes, and a uint16, so a read-only section would be `section-access` and a
  // section aligned to one byte `section-alignment`. Both are findings a reader would meet on
  // the same key, from the same form, with nothing to say which answer was wrong.
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();

  // The way back out (spec 5.2's Used by): the section names every definition placing data in
  // it, and each leads to the declaration itself. A reader who has just declared `.fast_buffer`
  // out of a complaint about PumpSpeed reaches PumpSpeed from it, without knowing which
  // component the complaint came from.
  await page.getByRole("link", { name: "Shared files" }).click();
  await page.getByRole("row", { name: ".fast_buffer" }).click();
  await panel.getByRole("button", { name: "PumpSpeed" }).click();
  await expect(page).toHaveURL(/\/component\?file=.*variable=PumpSpeed$/);
  await expect(page.getByRole("heading", { name: "Pump", level: 1 })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "PumpSpeed" })).toBeVisible();
});
