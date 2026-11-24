import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import {
  CONTROLLER,
  chooseUnit,
  drift,
  driftDatatypeIn,
  driftFactor,
  driftIn,
  driftMax,
  driftMaxUnseen,
  openPanel,
  PUMP,
  readAsText,
  SENSOR_HUB,
  USER_INTERFACE,
} from "./demo";
import { expect, test } from "./fixtures";

/** What the panel says while a chooser's text is not the value settled on. */
const UNSETTLED = "Press Enter to take what you typed, or pick it from the list.";

/** What a variable's panel says when a settle is refused because a file changed under its plan:
 * `VariablePanel.tsx`'s own sentence, held until the reader's next choice. */
const STALE =
  "A file changed on disk, so nothing was written. The panel now shows the files as they are.";

/** BlockA made a uint64 stating limits up to the most a uint64 holds, written as text: as a
 * number here the maximum would already be the double nearest it. */
function wideBlockA(directory: string): void {
  const path = join(directory, USER_INTERFACE);
  const text = readFileSync(path, "utf8");
  const changed = text.replace(
    /("name": "BlockA",[\s\S]*?"datatype": )"uint8"/,
    '$1"uint64",\n          "limits": { "min": 0, "max": 18446744073709551615 }',
  );
  if (changed === text) throw new Error(`${USER_INTERFACE} declares no BlockA of uint8`);
  writeFileSync(path, changed, "utf8");
}

test("a limit past 2^53 is shown as its file writes it, and no range holding one is applied", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", wideBlockA);
  const path = join(gui.directory, USER_INTERFACE);
  const before = readFileSync(path);
  await page.goto(gui.address);
  await page.getByRole("button", { name: "UserInterface", exact: true }).click();
  await page.getByRole("rowheader", { name: "BlockA" }).click();
  const panel = page.getByRole("complementary", { name: "BlockA" });
  await panel.getByRole("row", { name: /^limits/ }).click();

  // The file's own digits in the field and in the key's row, not 18446744073709552000, the
  // double they read as - which an edit of Min alone used to send back, a file that would not load.
  await expect(panel.getByLabel("Max")).toHaveValue("18446744073709551615");
  // And all of them: the field is as wide as its text, where a field of a fixed width showed
  // 1844674 and hid the rest, with no sign of it.
  await expect
    .poll(() =>
      panel
        .getByLabel("Max")
        .evaluate((field: HTMLInputElement) => field.scrollWidth - field.clientWidth),
    )
    .toBeLessThanOrEqual(0);
  await expect(panel.getByRole("row", { name: /^limits/ })).toContainText(
    "0 … 18446744073709551615",
  );
  const note = panel.getByText(
    "Max: '18446744073709551615' is past 2^53, where the page cannot hold every whole number exactly",
    { exact: true },
  );
  await expect(note).toBeVisible();
  const apply = panel.getByRole("button", { name: /^Apply to/ });
  await expect(apply).toHaveCount(0);
  await panel.getByLabel("Min").fill("1");
  await expect(note).toBeVisible();
  await expect(apply).toHaveCount(0);
  expect(readFileSync(path).equals(before)).toBe(true);

  // A maximum the page holds is the range written, as it was typed.
  await panel.getByLabel("Max").fill("9007199254740991");
  await expect(panel.getByText("Changes 1 file: user_interface.ddd.json")).toBeVisible();
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect
    .poll(() => readFileSync(path, "utf8"))
    .toContain('"limits": { "min": 1, "max": 9007199254740991 }');
});

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
  // hazard project-units.spec.ts's "an apply made from a panel that is out of date" names. The
  // panel says when it has: the disagreement is then among its findings, which it lists from the
  // revision it holds, and every plan it asks for after carries that revision's fingerprints,
  // so the Apply below lands on one it can act on - whether that analysis landed before the page
  // opened or after.
  const panel = await openPanel(page, gui.address, "ValueA");
  await expect(
    panel.getByRole("listitem").filter({ hasText: "definition-mismatch" }),
  ).toBeVisible();
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
  // at, so wait until the panel lists the disagreement the drift brought - the revision it holds
  // has read the drifted bytes then - before pressing it.
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("rowheader", { name: "ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await expect(
    panel.getByRole("listitem").filter({ hasText: "definition-mismatch" }),
  ).toBeVisible();

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
  // it, so that preview is against the old bytes - made so deterministically, rather than by
  // racing the click: the session's own watcher (`stamped`, `session.py` - keyed on
  // `(st_mtime_ns, st_size)`) never sees the write `driftMaxUnseen` makes, which keeps both, so
  // only a fresh read of the bytes does, which is the check an Apply itself makes: the
  // fingerprint is the authority and the watcher only a convenience, which this pins rather than
  // merely relying on. Written in place with its stamp put back after, the write stood visible
  // for as long as putting the stamp back took, and a poll landing then re-analysed the project
  // and left nothing stale to refuse - on a slow CI runner, never here.
  driftMaxUnseen(gui.directory, CONTROLLER, "ValueA", 999);
  await apply.click();
  const refused = panel.getByText("A file changed on disk");
  await expect(refused).toBeVisible();

  // The watcher never notices the drift, and nothing needs it to: refusing the Apply as stale,
  // the server asks for the analysis itself (`Session._refused`), which reads the drifted bytes.
  // The panel's rows say nothing of that analysis - the variable's reply reads its declarations
  // as the files stand, and is asked again as soon as the Apply is answered - but the
  // disagreement the drift makes is the analysis's own finding, which the panel lists only once
  // that analysis has landed. The sentence is still there then: it is held until the reader's
  // next choice, not until a revision.
  await expect(
    panel.getByText(
      "'ValueA' is declared differently by component 'Controller' than by 'SensorHub' (limits: [0, 999] != [0, 100])",
      { exact: true },
    ),
  ).toBeVisible({ timeout: 15000 });
  await expect(refused).toBeVisible();

  // The reader's next choice, a new maximum typed, takes the sentence away, and what it asks
  // for is planned against the files as they now are: applied, both files state it.
  await panel.getByLabel("Max").fill("60");
  await expect(refused).toBeHidden();
  await panel.getByRole("button", { name: /^Apply to/ }).click();
  await expect(panel.getByText("Nothing to change")).toBeVisible({ timeout: 15000 });
  expect(valueA(gui.directory, SENSOR_HUB).limits).toEqual({ min: 0, max: 60 });
  expect(valueA(gui.directory, CONTROLLER).limits).toEqual({ min: 0, max: 60 });
});

// The refusal's answer reaches the page before the revision of the analysis it asks for, as it
// mostly does, or after it: the Apply carries the key it was pressed for, so either way the
// refusal is that key's, and its row comes back where the revision had moved the panel on.
for (const late of [false, true]) {
  test(`a key the panel opened by itself, refused because a file changed on disk, stays open with its sentence once the analysis makes it agree (the refusal answered ${late ? "after" : "before"} the analysis)`, async ({
    page,
    gui,
  }) => {
    // Controller's own reading of ValueA drifted to rpm: its unit is the one key that disagrees,
    // and the panel, opened from the variable's row rather than from its unit, opens on it by
    // itself, settling on SensorHub's % - a plan that writes Controller alone.
    const before = drift(gui.directory);
    await page.goto(gui.address);
    await page.getByRole("button", { name: "Controller", exact: true }).click();
    await page.getByRole("row", { name: "ValueA", exact: true }).click();
    const panel = page.getByRole("complementary", { name: "ValueA" });
    const unit = panel.getByRole("combobox", { name: "Unit of ValueA" });
    await expect(unit).toHaveValue("%");
    // The drift's own analysis has landed once the panel lists the disagreement it finds: the
    // plan is asked again of that revision, and made over the drifted bytes.
    const disagreement = panel.getByText("is declared differently by component 'Controller'");
    await expect(disagreement).toBeVisible();
    const settle = panel.getByRole("region", { name: "Settle the key" });
    const apply = settle.getByRole("button", { name: "Apply to 1 file" });
    await expect(apply).toBeEnabled();

    // Controller put back as it was from outside as the Apply goes out, before the server reads
    // it: the plan was made over its drifted bytes, so the Apply is refused as stale, and the
    // analysis the refusal asks for finds ValueA's declarations agreeing - no key disagrees any
    // more. Late, the refusal's answer is handed to the page only once that analysis has.
    await page.route(
      "**/api/edit",
      async (route) => {
        writeFileSync(join(gui.directory, CONTROLLER), before);
        if (!late) {
          await route.continue();
          return;
        }
        const response = await route.fetch();
        await expect(disagreement).toHaveCount(0);
        await route.fulfill({ response });
      },
      { times: 1 },
    );
    await apply.click();
    const refused = settle.getByRole("status");
    await expect(refused).toHaveText(STALE);
    // That analysis landed once the panel lists the disagreement no longer.
    await expect(disagreement).toHaveCount(0);
    // The unit's row, which the panel had opened by itself, stays open, and the sentence held of
    // it with it: the panel did not move to the first row that disagrees, which is none.
    await expect(refused).toHaveText(STALE);
    await expect(unit).toBeVisible();
    await expect(panel.getByText("Select a key to settle it on every declaration.")).toHaveCount(0);
  });
}

test("a float variable's range takes any number a double holds, and is written as floats", async ({
  page,
  gui,
}) => {
  // ValueC is a float32, which holds 1e19 as it is: its digits past 2^53 were refused, and a
  // bound past 2^53 the page sent was written as a whole number (task 1's n3 and n2).
  const panel = await openPanel(page, gui.address, "ValueC", "SensorHub");
  await panel.getByRole("row", { name: /^limits/ }).click();
  await expect(panel.getByLabel("Max")).toHaveValue("90");
  await panel.getByLabel("Max").fill("10000000000000000000");
  const settling = panel.getByRole("region", { name: "Settle the key" });
  await settling.getByRole("button", { name: "Show changes" }).click();
  const added = settling.locator(".hunk .added");
  await expect(added.filter({ hasText: '"max": 10000000000000000000.0' }).first()).toBeVisible();
  await expect(added.filter({ hasText: '"min": -50.0' }).first()).toBeVisible();
  await expect(panel.getByRole("button", { name: "Apply to 2 files" })).toBeVisible();
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

  // The sentence names the one field it is about (15:M9).
  await panel.getByLabel("Max").fill("");
  await expect(panel.getByText("Max is empty", { exact: true })).toBeVisible();
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
  // Text typed past the unit refused is no longer about it: the refusal goes, the way out is said.
  await field.clear();
  await field.pressSequentially("Hz");
  await expect(panel.getByText(UNSETTLED)).toBeVisible();
  await expect(panel.getByText("which fixes its unit")).toHaveCount(0);
});

test("a value that would leave a file unable to load is previewed with why, and applied all the same", async ({
  page,
  copiedGui,
}) => {
  // SensorHub now produces ValueA as a uint16, and Controller reads it as text, which only a byte
  // can hold: the datatype the producer states is a value in play on the panel's own row, and
  // settling it on Controller is a change the loader refuses ("a string conversion needs a byte
  // datatype"). The reader chose it, so the panel previews it - and says so.
  const gui = await copiedGui("demo", (directory) => {
    driftDatatypeIn(directory, SENSOR_HUB, "ValueA", "uint16");
    readAsText(directory, CONTROLLER, "ValueA");
  });
  const panel = await openPanel(page, gui.address, "ValueA");
  await panel.getByRole("row", { name: /^datatype/ }).click();
  await expect(panel.getByRole("combobox", { name: "Datatype of ValueA" })).toHaveValue("uint16");
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
  // The server's own sentence, drawn beside the plan before anything is written.
  await expect(
    panel.getByText(
      "the declaration of 'ValueA' in controller.ddd.json would not load with that datatype: a string conversion needs a byte datatype, uint8 or sint8, got 'uint16'",
    ),
  ).toBeVisible();
  // It stands in no one's way: the value is the reader's to apply.
  const apply = panel.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeEnabled();
  await apply.click();
  await expect.poll(() => valueA(gui.directory, CONTROLLER).datatype).toBe("uint16");
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

const datatypeOf = (directory: string, file: string): unknown => valueA(directory, file).datatype;

/** Controller's ValueA drifted to a wider datatype and another unit, so that two keys disagree
 * and the datatype is the first: the panel opens by itself on it. */
async function openOnDatatype(page: Page, gui: { address: string; directory: string }) {
  driftDatatypeIn(gui.directory, CONTROLLER, "ValueA", "uint16");
  driftIn(gui.directory, CONTROLLER, "ValueA", "rpm");
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("rowheader", { name: "ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  await expect(
    panel.getByRole("listitem").filter({ hasText: "definition-mismatch" }).first(),
  ).toBeVisible();
  return panel;
}

test("a datatype picked on one row is not carried to the unit row the panel moves to", async ({
  page,
  gui,
}) => {
  const panel = await openOnDatatype(page, gui);
  const datatype = panel.getByRole("combobox", { name: "Datatype of ValueA" });
  await datatype.clear();
  await datatype.pressSequentially("uint16");
  await datatype.press("Enter");
  // The datatype's own diff is open when it is applied.
  const settle = panel.getByRole("region", { name: "Settle the key" });
  await settle.getByRole("button", { name: "Show changes" }).click();
  await expect(panel.locator(".hunk .added")).toContainText('"datatype": "uint16"');
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  // The datatype settled, the panel moves by itself to the unit, the one row still disagreeing:
  // it starts on the producer's unit, not on the datatype that was picked for the last row, and
  // what it would write is the producer's unit over Controller's.
  await expect(panel.getByRole("combobox", { name: "Unit of ValueA" })).toHaveValue("%");
  await expect(panel.getByText("Changes 1 file: controller.ddd.json")).toBeVisible();
  // ... with its diff closed, not left open from the row before.
  await expect(panel.locator(".hunk")).toHaveCount(0);
  await settle.getByRole("button", { name: "Show changes" }).click();
  await expect(panel.locator(".hunk .removed")).toContainText('"unit": "rpm"');
  await expect(panel.locator(".hunk .added")).toContainText('"unit": "%"');
});

test("a datatype undone comes back on the producer's value, not on the pick that was undone", async ({
  page,
  gui,
}) => {
  const panel = await openOnDatatype(page, gui);
  const datatype = panel.getByRole("combobox", { name: "Datatype of ValueA" });
  await datatype.clear();
  await datatype.pressSequentially("uint16");
  await datatype.press("Enter");
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(panel.getByRole("combobox", { name: "Unit of ValueA" })).toHaveValue("%");
  await expect.poll(() => datatypeOf(gui.directory, SENSOR_HUB)).toBe("uint16");
  await page.getByRole("button", { name: "Undo the datatype of ValueA" }).click();
  await page
    .getByRole("region", { name: "Undo" })
    .getByRole("button", { name: "Put back 1 file" })
    .click();
  await expect.poll(() => datatypeOf(gui.directory, SENSOR_HUB)).toBe("uint8");
  // The datatype disagrees again and is the first row that does: the panel goes back to it, on
  // SensorHub's value, which is not what was picked before the undo.
  await expect(panel.getByRole("combobox", { name: "Datatype of ValueA" })).toHaveValue("uint8");
});

test("a datatype settled, then widened from outside, comes back on the producer's value", async ({
  page,
  gui,
}) => {
  driftDatatypeIn(gui.directory, CONTROLLER, "ValueA", "uint16");
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("rowheader", { name: "ValueA" }).click();
  const panel = page.getByRole("complementary", { name: "ValueA" });
  const datatype = panel.getByRole("combobox", { name: "Datatype of ValueA" });
  await expect(datatype).toBeVisible();
  await datatype.clear();
  await datatype.pressSequentially("uint16");
  await datatype.press("Enter");
  await panel.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect.poll(() => datatypeOf(gui.directory, SENSOR_HUB)).toBe("uint16");
  // Nothing disagrees any more: the chooser closes.
  await expect(panel.getByText("Select a key to settle it on every declaration.")).toBeVisible();
  driftDatatypeIn(gui.directory, SENSOR_HUB, "ValueA", "uint32");
  // The panel reopens by itself on the datatype, on the producer's uint32, not on the uint16
  // that was settled before the chooser closed.
  await expect(panel.getByRole("combobox", { name: "Datatype of ValueA" })).toHaveValue("uint32");
});

test("text typed on one row is not carried to the row the panel moves to", async ({
  page,
  gui,
}) => {
  const panel = await openOnDatatype(page, gui);
  const datatype = panel.getByRole("combobox", { name: "Datatype of ValueA" });
  await datatype.clear();
  await datatype.pressSequentially("uint");
  await expect(datatype).toHaveValue("uint");
  // The datatype is settled from outside: the panel moves by itself to the unit.
  driftDatatypeIn(gui.directory, CONTROLLER, "ValueA", "uint8");
  await expect(panel.getByRole("combobox", { name: "Unit of ValueA" })).toHaveValue("%");
});

/** What Controller's file states for ValueA's unit. */
function unitOfValueA(directory: string): string {
  return JSON.parse(readFileSync(join(directory, CONTROLLER), "utf8")).component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === "ValueA",
  ).definition.unit;
}

test("text typed past the chosen unit offers no Apply for the earlier unit, and says what to do", async ({
  page,
  gui,
}) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  await chooseUnit(page, "rpm");
  await expect(panel.getByRole("button", { name: "Apply to 2 files" })).toBeEnabled();
  const field = panel.getByRole("combobox", { name: "Unit of ValueA" });
  await field.clear();
  // Blank text is taken by nothing: the sentence does not say Enter takes it.
  await expect(panel.getByText(/^Pick one from the list, or press Escape/)).toBeVisible();
  await expect(panel.getByText(UNSETTLED)).toHaveCount(0);
  await field.pressSequentially("km/h");
  await expect(field).toHaveValue("km/h");
  // The open list hides the rest of the page from the accessibility tree: looked for there too.
  await expect(
    panel.getByRole("button", { name: /^Apply to/, disabled: false, includeHidden: true }),
  ).toHaveCount(0);
  // Nor does a sentence plan the earlier unit as if it were the one now written.
  await expect(panel.getByText("Changes 2 files")).toHaveCount(0);
  await expect(panel.getByText(UNSETTLED)).toBeVisible();
  // Taken with Enter, the text is the unit, and what is planned is for it.
  await field.press("Enter");
  await expect(field).toHaveValue("km/h");
  await expect(panel.getByText(UNSETTLED)).toHaveCount(0);
  await expect(panel.getByRole("button", { name: "Apply to 2 files" })).toBeEnabled();
});

test("what Apply writes is not a unit the reader typed past", async ({ page, gui }) => {
  const before = unitOfValueA(gui.directory);
  const panel = await openPanel(page, gui.address, "ValueA");
  await chooseUnit(page, "rpm");
  // The diff is open, which keeps the open list off the button.
  await panel
    .getByRole("region", { name: "Settle the key" })
    .getByRole("button", { name: "Show changes" })
    .click();
  const field = panel.getByRole("combobox", { name: "Unit of ValueA" });
  await field.clear();
  await field.pressSequentially("km/h");
  await expect(field).toHaveValue("km/h");
  // Nothing to press while the text is not the unit settled on, so nothing can be written.
  await expect(panel.getByRole("button", { name: /^Apply to/, includeHidden: true })).toHaveCount(
    0,
  );
  expect(unitOfValueA(gui.directory)).toBe(before);
  // Left, the field goes back to the unit chosen, and Apply writes exactly what it reads.
  await field.press("Tab");
  await expect(field).toHaveValue("rpm");
  await panel.getByRole("button", { name: "Apply to 2 files" }).click();
  await expect.poll(() => unitOfValueA(gui.directory)).toBe("rpm");
});

test("a value chooser says Enter takes the text only once it spells an entry", async ({
  page,
  gui,
}) => {
  const panel = await openOnDatatype(page, gui);
  const datatype = panel.getByRole("combobox", { name: "Datatype of ValueA" });
  await datatype.clear();
  await datatype.pressSequentially("uint");
  // Part of an entry's spelling, so Enter would take nothing: the list is the way out.
  await expect(panel.getByText(/^Pick one from the list, or press Escape/)).toBeVisible();
  await expect(panel.getByText(UNSETTLED)).toHaveCount(0);
  await datatype.pressSequentially("16");
  await expect(panel.getByText(UNSETTLED)).toBeVisible();
  await expect(panel.getByText(/^Pick one from the list, or press Escape/)).toHaveCount(0);
  await datatype.press("Enter");
  await expect(panel.getByText(UNSETTLED)).toHaveCount(0);
  await expect(panel.getByText(/^Pick one from the list, or press Escape/)).toHaveCount(0);
});

/** Whether the note under a field is what a reader would hit at its centre, rather than the open
 * list or anything else drawn over it. */
async function notCovered(field: Locator): Promise<boolean> {
  return field.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
    return hit !== null && element.contains(hit);
  });
}

test("the arrow closing the list keeps the text typed, withholds Apply and says what to do", async ({
  page,
  gui,
}) => {
  const panel = await openPanel(page, gui.address, "ValueA");
  await chooseUnit(page, "rpm");
  const field = panel.getByRole("combobox", { name: "Unit of ValueA" });
  await field.clear();
  await field.pressSequentially("km");
  await expect(page.getByRole("listbox")).toBeVisible();
  // By its label: an open list hides the page's roles from the accessibility tree.
  await panel.locator('button[aria-label="Show the choices for Unit of ValueA"]').click();
  await expect(page.getByRole("listbox")).toHaveCount(0);
  await expect(field).toHaveValue("km");
  await expect(
    panel.getByRole("button", { name: /^Apply to/, disabled: false, includeHidden: true }),
  ).toHaveCount(0);
  // The sentence is the field's description, and on screen with the list closed.
  await expect(field).toHaveAccessibleDescription(UNSETTLED);
  const note = panel.getByText(UNSETTLED);
  await expect(note).toBeVisible();
  expect(await notCovered(note)).toBe(true);
  // Escape ends the text, the earlier unit is back and so is Apply; so does leaving the field.
  await field.press("Escape");
  await expect(field).toHaveValue("rpm");
  await expect(panel.getByRole("button", { name: "Apply to 2 files" })).toBeEnabled();
  await field.pressSequentially("k");
  await expect(field).toHaveValue("rpmk");
  await field.press("Tab");
  await expect(field).toHaveValue("rpm");
});

test("an Enter that takes nothing keeps the text, and so does text that spells no entry", async ({
  page,
  gui,
}) => {
  const panel = await openOnDatatype(page, gui);
  const datatype = panel.getByRole("combobox", { name: "Datatype of ValueA" });
  await datatype.clear();
  await datatype.pressSequentially("uint");
  await expect(panel.getByText(/^Pick one from the list, or press Escape/)).toBeVisible();
  await datatype.press("Enter");
  await expect(datatype).toHaveValue("uint");
  await expect(
    panel.getByRole("button", { name: /^Apply to/, disabled: false, includeHidden: true }),
  ).toHaveCount(0);
  await expect(page.getByRole("listbox")).toHaveCount(0);
  const note = panel.getByText(/^Pick one from the list, or press Escape/);
  await expect(note).toBeVisible();
  expect(await notCovered(note)).toBe(true);

  // Text no entry spells empties the list; it stays, and the sentence names the way out.
  await datatype.clear();
  await datatype.pressSequentially("zzz");
  await expect(datatype).toHaveValue("zzz");
  const nothing = panel.getByText(/^Nothing in the list matches what you typed/);
  await expect(nothing).toBeVisible();
  await expect(nothing).toContainText("Escape");
  await datatype.press("Escape");
  await expect(datatype).toHaveValue("uint8");
  await expect(nothing).toHaveCount(0);
});

test("a key row says that it will change in words of their own, and its chooser's button is named once", async ({
  page,
  gui,
}) => {
  // A screen reader reads the cell's text as it stands, and the button's name as the field and the
  // button's own words make it (16:M22): `kHzwill change` and a field's label said twice before.
  const panel = await openPanel(page, gui.address, "ValueA");
  await chooseUnit(page, "rpm");
  const changing = page.getByRole("gridcell").filter({ has: page.locator(".tag") });
  await expect(changing.first()).toHaveText(/\S will change$/);
  await expect(
    panel.getByRole("button", { name: /^Show the choices for Unit of ValueA/ }),
  ).toHaveAccessibleName("Show the choices for Unit of ValueA");
});
