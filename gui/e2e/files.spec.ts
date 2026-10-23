import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { CONTROLLER, failing, held, restamp, SERVER_FAILED, UNITS, writeUnseen } from "./demo";
import { expect, type Gui, test } from "./fixtures";

/** A component the project does not include yet, declaring nothing - written into the copy
 * `vocabularyGui` hands this journey before the page opens, the way `sections.spec.ts`'s own
 * `misplacePumpSpeed` writes into its copy: reading nothing and writing nothing, adding it brings
 * no error to preview, so the journey's Add a file step is about the row it leaves rather than
 * about what the server lists beside it. */
const EXTRA = "extra.ddd.json";

test("a component is created, an existing file is added, and one removal is refused where another goes through", async ({
  page,
  vocabularyGui,
}) => {
  writeFileSync(
    join(vocabularyGui.directory, EXTRA),
    JSON.stringify({ component: { name: "Extra", interface: [] } }),
    "utf8",
  );

  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  // New file: a component, created beside the description and appended to its includes in the
  // same edit (design §3) - the plan named here is the one CREATE_COMPONENT pins in
  // gui/src/stories/fixtures.ts, "project.ddd.json" first since "project" sorts before "valve".
  await page.getByRole("button", { name: "New file" }).click();
  const creating = page.getByRole("complementary", { name: "New file" });
  const kind = creating.getByRole("combobox", { name: "Kind" });
  await kind.fill("component");
  await kind.press("Enter");
  await creating.getByRole("textbox", { name: "File name" }).fill("valve");
  await creating.getByRole("textbox", { name: "Component name" }).fill("Valve");
  await expect(
    creating.getByText("Changes 2 files: project.ddd.json, valve.ddd.json"),
  ).toBeVisible();
  await creating.getByRole("button", { name: "Apply to 2 files" }).click();

  // Created: the panel closes and the table gains the row, its own kind read off the file once
  // the next analysis has read it.
  const valveRow = page.getByRole("row", { name: "valve.ddd.json" });
  await expect(valveRow).toBeVisible();
  await expect(valveRow).toContainText("component");

  // Add a file: extra.ddd.json, written outside the page above, appended to the includes as
  // typed - previewed with nothing it would bring, since it reads and writes nothing, and
  // applied the same way as every other panel here (design §3, "informs rather than refuses").
  await page.getByRole("button", { name: "Add a file" }).click();
  const adding = page.getByRole("complementary", { name: "Add a file" });
  await adding.getByRole("textbox", { name: "Path" }).fill(EXTRA);
  await expect(adding.getByText("Changes 1 file: project.ddd.json")).toBeVisible();
  await adding.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByRole("row", { name: EXTRA })).toBeVisible();

  // Remove, refused: constants.ddd.json declares TREND_SAMPLES, which pump.ddd.json's own
  // PressureTrend is dimensioned by - the sentence pinned whole in tests/test_gui_api.py's
  // TestRemovingAFile (and by REMOVE_LEAVES_AN_ERROR in gui/src/stories/fixtures.ts, "the
  // refusal `gui/e2e/files.spec.ts` reads too"), read here rather than restated - a second spelling
  // could drift from the server's with nothing to catch it. No plan follows the refusal, so
  // there is no button to press.
  await page.getByRole("row", { name: "constants.ddd.json" }).click();
  const constantsPanel = page.getByRole("complementary", { name: "constants.ddd.json" });
  const constantsRemoving = constantsPanel.getByRole("region", {
    name: "Remove from the includes",
  });
  await expect(constantsRemoving.getByRole("status")).toHaveText(
    "removing constants.ddd.json would leave one error more than the project has now at its " +
      "place, in pump.ddd.json: 'PressureTrend' is dimensioned by 'TREND_SAMPLES', which is not " +
      "a constant any file of this project declares",
  );
  await expect(constantsRemoving.getByRole("button")).toHaveCount(0);

  // Remove, allowed: pump.ddd.json states units units.ddd.json declares, but a units file is what
  // opts a project into checking its units (`_check_units`, src/ddd/analysis.py), so with none
  // left no unit is checked and nothing fails - the plan changes the project description alone,
  // and applying it takes the row away.
  await page.getByRole("row", { name: UNITS }).click();
  const unitsPanel = page.getByRole("complementary", { name: UNITS });
  const unitsRemoving = unitsPanel.getByRole("region", { name: "Remove from the includes" });
  await expect(unitsRemoving.getByText("Changes 1 file: project.ddd.json")).toBeVisible();
  await unitsRemoving.getByRole("button", { name: "Remove from the includes" }).click();
  await expect(page.getByRole("row", { name: UNITS })).toHaveCount(0);

  // And the project reports exactly these three edits, nothing else: a component declaring no
  // variable is `empty-component`, at info, and both of the bare ones this journey made carry
  // it - removing the units file leaves nothing behind, since no unit is checked without one.
  await page.getByRole("link", { name: "Findings" }).click();
  await expect(page.getByText("2 findings · 2 notes")).toBeVisible();
  await expect(page.getByRole("row", { name: "empty-component" })).toHaveCount(2);
});

/**
 * The row the tab's own Apply makes shows at once (spec §3, Ruling F2): drawn from the plan the
 * page applied, before the tab's next list of its entries answers - held back here, from the
 * moment the tab has drawn its first, for as long as the row takes to show. At 100,000
 * declarations that list waits on the edit's own analysis, and the row with it, until the tab
 * held what it applied. What the row says is the state's to say: on a project this small the
 * edit's analysis can land before the row is first looked at, and the held row then reads the
 * file as that analysis read it. Released, the list carries the row, and it stays.
 */
test("the row a New file makes shows before the tab's next list of entries answers", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await expect(page.getByRole("row", { name: UNITS })).toBeVisible();

  // Every list the tab asks for until the row shows, not the next alone: the claim is about any
  // of them, and the edit's analysis may ask for more than one.
  const release = await held(page, "/api/files", { every: true });
  try {
    await page.getByRole("button", { name: "New file" }).click();
    const creating = page.getByRole("complementary", { name: "New file" });
    const kind = creating.getByRole("combobox", { name: "Kind" });
    await kind.fill("component");
    await kind.press("Enter");
    await creating.getByRole("textbox", { name: "File name" }).fill("valve");
    await creating.getByRole("textbox", { name: "Component name" }).fill("Valve");
    await creating.getByRole("button", { name: "Apply to 2 files" }).click();

    await expect(page.getByRole("row", { name: "valve.ddd.json" })).toBeVisible();
  } finally {
    release();
  }
  await expect(page.getByRole("row", { name: "valve.ddd.json" })).toContainText("component");
});

/**
 * The row the tab's own Remove takes out goes at once (spec §3, Ruling F6), held as New file's
 * is: the edit answered, the tab leaves out every entry of the key it removed, before its next
 * list of entries answers - held back here, from the press, for as long as the row takes to go.
 * Released, the row stays gone because the server's next list no longer carries the entry: the
 * journey checks that list itself, before the page is handed it, so no look at the row after it
 * would say more. The page's own undo puts the entry back, and its row with it.
 */
test("the row a Remove takes out goes before the tab's next list of entries answers", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  const unitsRow = page.getByRole("row", { name: UNITS });
  await unitsRow.click();
  const removing = page
    .getByRole("complementary", { name: UNITS })
    .getByRole("region", { name: "Remove from the includes" });
  const remove = removing.getByRole("button", { name: "Remove from the includes" });
  await expect(remove).toBeVisible();

  // The server's next list, read here before the page is handed it: the entry Remove took out
  // is not in it, so the row the page drops at once (below) is not drawn again by that answer.
  // Once only (`held`'s `times: 1`): the teardown that follows this journey's last assertion
  // stops the server, and the page then asks GET /api/files once more - a request this route must
  // leave to the browser, as it did before part 19b's Task 1, rather than meet with its own
  // route.fetch() against a server already going away.
  let listed: string[] | null = null;
  const release = await held(page, "/api/files", {
    onAnswer: async (response) => {
      const reply = (await response.json()) as { entries: { entry: string }[] };
      listed = reply.entries.map((each) => each.entry);
    },
  });
  try {
    await remove.click();
    await expect(unitsRow).toHaveCount(0);
  } finally {
    release();
  }
  await expect.poll(() => listed).not.toBeNull();
  expect(listed).not.toContain(UNITS);

  await page.getByRole("button", { name: `Undo '${UNITS}' removed from the includes` }).click();
  await page
    .getByRole("region", { name: "Undo" })
    .getByRole("button", { name: "Put back 1 file" })
    .click();
  await expect(unitsRow).toBeVisible();
});

/** Every plan the Files tab asks (`GET /api/files-plan`) from here on, counted as it is asked,
 * before any answer. */
function plansAsked(page: Page): string[] {
  const planned: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/files-plan") planned.push(request.url());
  });
  return planned;
}

/**
 * The page loaded at `file`'s own row of the Files tab, as a link from elsewhere would load it
 * (P18b-10), and every plan asked from that load on. Signed in first at the address ddd gui
 * printed, whose token the page keeps for the next address this tab opens. The row's key is the
 * file's absolute, posix-separated path (`IncludedEntryReply.key`).
 */
async function openedAtRow(page: Page, gui: Gui, file: string): Promise<string[]> {
  await page.goto(gui.address);
  await expect(page.getByRole("link", { name: "Files", exact: true })).toBeVisible();
  const planned = plansAsked(page);
  const key = `${gui.directory.replaceAll("\\", "/")}/${file}`;
  const origin = new URL(gui.address).origin;
  await page.goto(`${origin}/project?view=files&path=${encodeURIComponent(key)}`);
  return planned;
}

/**
 * The row the page was loaded with waits for the reader (P18b-10, spec §7): a Remove plan
 * re-analyses the project, running its plugins, so the panel of a row an address chose - a link
 * from elsewhere, a bookmark, a typed address, a reload - asks for none until the reader presses
 * for it. A fragment navigation, which another window can make, leaves it waiting (ruling
 * P19a-19); the reader's press asks it, and keeps the keyboard's focus in the panel (ruling
 * P19a-20). A row the reader selects within the page is planned at once, as before.
 */
test("the row the page was opened on waits for the reader before its removal is planned", async ({
  page,
  vocabularyGui,
}) => {
  const planned = await openedAtRow(page, vocabularyGui, UNITS);
  const unitsRemoving = page
    .getByRole("complementary", { name: UNITS })
    .getByRole("region", { name: "Remove from the includes" });
  const ask = unitsRemoving.getByRole("button", { name: "Plan its removal" });
  await expect(ask).toBeVisible();
  expect(planned).toEqual([]);

  // The address set to itself with a fragment, as any window holding a handle on this one can set
  // it - a cross-origin opener among them: a navigation within the page that fires `popstate` and
  // leaves the route as it was, so the row still waits. Waited on by two frames inside the page:
  // whatever that `popstate` changed is drawn by then, so a button still there is one the page
  // kept, not one it has yet to take away.
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        window.location.hash = "x";
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      }),
  );
  await expect(page).toHaveURL(/#x$/);
  await expect(ask).toBeVisible();
  expect(planned).toEqual([]);

  // Pressed from the keyboard: the plan is asked, and the focus stays in the panel, on the region
  // the button was in, rather than falling to the page's body as the button goes.
  await ask.press("Enter");
  await expect(unitsRemoving.getByText("Changes 1 file: project.ddd.json")).toBeVisible();
  await expect(unitsRemoving).toBeFocused();
  // Ringed as app.css rings a focused button (ruling P19a-21): tokens.css's --accent, 2px off.
  await expect(unitsRemoving).toHaveCSS("outline-style", "solid");
  await expect(unitsRemoving).toHaveCSS("outline-width", "2px");
  await expect(unitsRemoving).toHaveCSS("outline-color", "rgb(14, 107, 124)");
  await expect(unitsRemoving).toHaveCSS("outline-offset", "2px");
  expect(planned).toHaveLength(1);

  // A row the reader selects in the table is planned at once, as before.
  await page.getByRole("row", { name: "constants.ddd.json" }).click();
  await expect.poll(() => planned.length).toBe(2);
  await expect(page.getByRole("button", { name: "Plan its removal" })).toHaveCount(0);
});

/**
 * The row the page was opened on, pressed in the table rather than by its button (ruling
 * P19a-15): the table presses a selected row off, so its panel closes and nothing is asked;
 * pressed again, the row is the reader's own selection, planned at once with no button - though
 * its route is the very one the page was loaded with.
 */
test("the row the page was opened on, pressed off and on again in the table, is planned at once", async ({
  page,
  vocabularyGui,
}) => {
  const planned = await openedAtRow(page, vocabularyGui, UNITS);
  const unitsPanel = page.getByRole("complementary", { name: UNITS });
  const ask = page.getByRole("button", { name: "Plan its removal" });
  await expect(unitsPanel.getByRole("button", { name: "Plan its removal" })).toBeVisible();
  expect(planned).toEqual([]);

  const unitsRow = page.getByRole("row", { name: UNITS });
  await unitsRow.click();
  await expect(unitsPanel).toHaveCount(0);
  await expect(page).toHaveURL(/\/project\?view=files$/);
  await expect(ask).toHaveCount(0);
  expect(planned).toEqual([]);

  await unitsRow.click();
  await expect(
    unitsPanel
      .getByRole("region", { name: "Remove from the includes" })
      .getByText("Changes 1 file: project.ddd.json"),
  ).toBeVisible();
  expect(planned).toHaveLength(1);
  await expect(ask).toHaveCount(0);
});

/**
 * A move back or forward within the page to another route is the reader's own (spec §7,
 * `arrivedAfter` in lib/route.ts), so a row reached by Back is planned at once - even in a page
 * reloaded since. There Back is the first move the reloaded page makes, the address it was loaded
 * with being the Findings tab's: Chrome goes back to the row's entry within that same page, firing
 * `popstate` with no load of its own (a value set on `window` before Back was still there after
 * it, in Chrome 153 on the Linux development PC).
 */
test("a row reached by going back within the page is planned at once, even after a reload", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("row", { name: "constants.ddd.json" }).click();
  // Refused, as the first journey's own constants.ddd.json is: the refusal is the plan answered.
  const refused = page
    .getByRole("complementary", { name: "constants.ddd.json" })
    .getByRole("region", { name: "Remove from the includes" })
    .getByRole("status");
  await expect(refused).toBeVisible();
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await expect(page).toHaveURL(/\/project\?view=findings$/);
  await page.reload();
  await expect(page.getByRole("link", { name: "Findings", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  const planned = plansAsked(page);

  await page.goBack();
  await expect(refused).toBeVisible();
  expect(planned).toHaveLength(1);
  await expect(page.getByRole("button", { name: "Plan its removal" })).toHaveCount(0);
});

/** The project description of examples/vocabulary, whose includes every Files action changes. */
const PROJECT = "project.ddd.json";

/** What the Files tab says when an Apply is refused because a file changed under its preview. */
const STALE =
  "A file changed on disk, so nothing was written. The page now shows the files as they are.";

/** examples/vocabulary's description as somebody saving it from their editor would change it: a
 * space taken out and a full stop put in, so that it keeps its length and `writeUnseen` can write
 * it where the session's own watcher does not see it - the change "a Remove applied while the
 * description changed on disk…" makes. Throws where the text is not there, so that a journey never
 * writes the file it was given back unchanged and calls that a change. */
function withFullStop(original: string): string {
  const changed = original
    .replace('"name": "PumpDevice"', '"name":"PumpDevice"')
    .replace('names its sizes"', 'names its sizes."');
  if (changed === original) throw new Error(`${PROJECT} no longer reads as this journey expects`);
  return changed;
}

test("a Remove applied while the description changed on disk is refused, and goes through once the analysis has caught up", async ({
  page,
  vocabularyGui,
}) => {
  const project = join(vocabularyGui.directory, PROJECT);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("row", { name: UNITS }).click();
  const removing = page
    .getByRole("complementary", { name: UNITS })
    .getByRole("region", { name: "Remove from the includes" });
  const remove = removing.getByRole("button", { name: "Remove from the includes" });
  await expect(removing.getByText("Changes 1 file: project.ddd.json")).toBeVisible();

  // The description gains its full stop as the Apply goes out, written where the session's own
  // watcher does not see it (`writeUnseen`): seen, it brought a revision of its own, and the tab
  // holds a stale refusal only until the next (`shownRefusal`, lib/refusals.ts) - once gone before
  // skeleton.spec.ts's out-of-date edit read it (CI run 37705627501, windows msedge). A space
  // taken out and a full stop put in keep the file as long as it was. Written once, then the
  // request goes through to the server, which reads the bytes fresh.
  const changed = withFullStop(readFileSync(project, "utf8"));
  await page.route(
    "**/api/edit",
    async (route) => {
      writeUnseen(vocabularyGui.directory, PROJECT, changed);
      await route.continue();
    },
    { times: 1 },
  );
  await remove.click();
  const refused = removing.getByRole("status");
  await expect(refused).toHaveText(STALE);
  // Nothing was written: the file is as the change from outside left it, units.ddd.json still in
  // its includes.
  expect(readFileSync(project, "utf8")).toBe(changed);

  // The refusal is held until the analysis has moved past the revision it was made at: no revision
  // comes of a change the watcher did not see, so the file's stamp is moved, which it does see.
  // The analysis reads the file as it now is, the refusal goes, and the plan asked for that
  // revision carries the file's new fingerprint - which is what lets the same press go through.
  restamp(vocabularyGui.directory, PROJECT);
  await expect(refused).toHaveCount(0, { timeout: 15000 });
  await remove.click();
  await expect(page.getByRole("row", { name: UNITS })).toHaveCount(0);
  const written = JSON.parse(readFileSync(project, "utf8")).project;
  expect(written.includes).toEqual([
    "sections.ddd.json",
    "constants.ddd.json",
    "rasters.ddd.json",
    "pump.ddd.json",
  ]);
  expect(written.description).toMatch(/names its sizes\.$/);
});

/** A component the project does not include yet, reading a variable no component writes: adding
 * it brings an error. Written into the copy `vocabularyGui` hands the journey, before the page
 * opens, as `EXTRA` is - which brings none. */
const READER = "reader.ddd.json";

test("the errors a file would bring are listed in the Add a file preview, which still offers to add it", async ({
  page,
  vocabularyGui,
}) => {
  writeFileSync(
    join(vocabularyGui.directory, READER),
    JSON.stringify({
      component: {
        name: "Reader",
        interface: [
          {
            scope: "input",
            definition: {
              name: "Torque",
              kind: "measurement",
              datatype: "uint16",
              conversion: { kind: "identity" },
              unit: "Nm",
              volatile: false,
            },
          },
        ],
      },
    }),
    "utf8",
  );
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("button", { name: "Add a file" }).click();
  const adding = page.getByRole("complementary", { name: "Add a file" });
  await adding.getByRole("textbox", { name: "Path" }).fill(READER);

  // The one error the file would bring, as the server counts it and words it (`analysis.py`'s
  // own sentence): the check, the file it is filed on, then the message. Informed, not refused:
  // the change is still offered (design §3).
  const brought = adding.getByRole("listitem");
  await expect(brought).toHaveCount(1);
  await expect(brought.locator(".chip")).toHaveText("missing-producer");
  await expect(brought.locator(".quiet")).toHaveText(READER);
  await expect(brought.locator("p")).toHaveText(
    "'Torque' is read by component 'Reader' but no component declares it as output",
  );
  await expect(adding.getByRole("button", { name: "Apply to 1 file" })).toBeEnabled();
});

test("the list failing at first leaves the server's own error, with no table and no way to add a file", async ({
  page,
  vocabularyGui,
}) => {
  await failing(page, "/api/files", "http");
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(page.getByRole("button", { name: "New file" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add a file" })).toHaveCount(0);
  await expect(page.getByRole("grid")).toHaveCount(0);
});

test("the list failing once drawn leaves the table, with the server's own error over it", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  const unitsRow = page.getByRole("row", { name: UNITS });
  await expect(unitsRow).toBeVisible();

  // The tab left, then returned to once the list fails: a tab mounting asks again for an answer it
  // holds (stale from the start), and when that read fails the answer stays drawn, the error said
  // over it. A change the watcher sees reaches the same state another way: the new revision's read
  // has no answer of its own to hold (`placeholderData` serves a read that is pending, not one that
  // failed), and the tab draws the last one it read (`useKept`, P19b-20; kept.spec.ts).
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await expect(page.getByText("Nothing to report")).toBeVisible();
  await failing(page, "/api/files", "http");
  await page.getByRole("link", { name: "Files", exact: true }).click();

  // The alert over the table (`:above()` is Playwright's layout selector: the alert's box lies over
  // the grid's), and the table still drawn under it, with the two actions above it.
  await expect(page.getByRole("alert").and(page.locator(':above([role="grid"])'))).toHaveText(
    SERVER_FAILED,
  );
  await expect(unitsRow).toBeVisible();
  await expect(page.getByRole("button", { name: "New file" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add a file" })).toBeVisible();
});

/**
 * New file's out-of-date refusal, in New file's own panel (ruling P19b-27): the Remove journey
 * above pins `useFilesApply`, which all three actions share, but not where New file and Add draw
 * what it refused. Written before the press (spec 2026-10-21 §3): the description changes once the
 * panel has drawn its plan, where the watcher does not see it, so no revision comes to take the
 * plan away, and the Apply carries a fingerprint the server no longer finds.
 */
test("a New file applied while the description changed on disk is refused in its own panel, and goes through once the analysis has caught up", async ({
  page,
  vocabularyGui,
}) => {
  const project = join(vocabularyGui.directory, PROJECT);
  const spare = join(vocabularyGui.directory, "spare.ddd.json");
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("button", { name: "New file", exact: true }).click();
  const creating = page.getByRole("complementary", { name: "New file" });
  const kind = creating.getByRole("combobox", { name: "Kind" });
  await kind.fill("types");
  await kind.press("Enter");
  await creating.getByRole("textbox", { name: "File name" }).fill("spare");
  // The plan drawn: both files it writes, sorted by path as `create_plan` sorts them.
  await expect(
    creating.getByText("Changes 2 files: project.ddd.json, spare.ddd.json", { exact: true }),
  ).toBeVisible();

  const changed = withFullStop(readFileSync(project, "utf8"));
  writeUnseen(vocabularyGui.directory, PROJECT, changed);
  const apply = creating.getByRole("button", { name: "Apply to 2 files" });
  await apply.click();

  // Refused in the panel the reader pressed in, in the tab's own words (`refusalOf`,
  // UnitPanel.tsx), and nothing written: no new file, and the description as the outside change
  // left it.
  const refused = creating.getByRole("status");
  await expect(refused).toHaveText(STALE);
  expect(existsSync(spare)).toBe(false);
  expect(readFileSync(project, "utf8")).toBe(changed);

  // Held until the analysis has moved past the revision it was refused at (`refusalShown`,
  // lib/refusals.ts). A stamp moved and no byte changed is what the watcher sees: the next
  // revision reads the description as it now is, and in the render it lands the refusal goes and
  // the plan is asked again under it - so the button pressed next is that revision's, carrying the
  // fingerprint that lets the same press go through.
  restamp(vocabularyGui.directory, PROJECT);
  await expect(refused).toHaveCount(0);
  await apply.click();
  await expect(page.getByRole("row", { name: "spare.ddd.json", exact: true })).toBeVisible();
  expect(JSON.parse(readFileSync(spare, "utf8"))).toEqual({ types: [] });
  const written = JSON.parse(readFileSync(project, "utf8")).project;
  expect(written.includes).toEqual([
    "units.ddd.json",
    "sections.ddd.json",
    "constants.ddd.json",
    "rasters.ddd.json",
    "pump.ddd.json",
    "spare.ddd.json",
  ]);
  expect(written.description).toMatch(/names its sizes\.$/);
});

/**
 * Add's out-of-date refusal, in Add's own panel: the same refusal New file's journey above meets,
 * reached the same way. Asked again after it (`onSettled`), Add's plan is itself refused as out
 * of date - it judges the change against the revision (`_judged`, api.py) - so the panel's
 * sentence is the Apply's, which takes precedence (`refusalShown`), and no button is offered.
 */
test("an Add applied while the description changed on disk is refused in its own panel, and nothing is written", async ({
  page,
  vocabularyGui,
}) => {
  // A component the project does not include yet, declaring nothing, so the plan brings no error
  // and its preview is the plain one.
  writeFileSync(
    join(vocabularyGui.directory, EXTRA),
    JSON.stringify({ component: { name: "Extra", interface: [] } }),
    "utf8",
  );
  const project = join(vocabularyGui.directory, PROJECT);
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("button", { name: "Add a file", exact: true }).click();
  const adding = page.getByRole("complementary", { name: "Add a file" });
  await adding.getByRole("textbox", { name: "Path" }).fill(EXTRA);
  await expect(adding.getByText("Changes 1 file: project.ddd.json", { exact: true })).toBeVisible();

  const changed = withFullStop(readFileSync(project, "utf8"));
  writeUnseen(vocabularyGui.directory, PROJECT, changed);
  await adding.getByRole("button", { name: "Apply to 1 file" }).click();

  await expect(adding.getByRole("status")).toHaveText(STALE);
  expect(readFileSync(project, "utf8")).toBe(changed);
  expect(JSON.parse(changed).project.includes).not.toContain(EXTRA);
});

test("the files tab says it is reading the project's files until they are read", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  // The tab not yet pressed: only `FilesPage` asks for the files, so the first `/api/files` is the
  // tab's own, and held, it is the read this journey is about.
  const tab = page.getByRole("link", { name: "Files", exact: true });
  await expect(tab).toBeVisible();
  const reading = page.getByText("Reading the project's files…", { exact: true });
  const release = await held(page, "/api/files");
  try {
    await tab.click();
    // The line stands alone: nothing of the tab is drawn until the files are read, neither the
    // table nor the two ways to add a file.
    await expect(reading).toBeVisible();
    await expect(page.getByRole("button", { name: "New file", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Add a file", exact: true })).toHaveCount(0);
    await expect(page.getByRole("grid", { name: "Files" })).toHaveCount(0);
  } finally {
    release();
  }
  await expect(page.getByRole("row", { name: UNITS, exact: true })).toBeVisible();
  await expect(reading).toHaveCount(0);
});

/** The kinds of vocabulary New file creates empty, one file of each. */
const VOCABULARIES = ["types", "units", "constants", "sections", "rasters"] as const;

test("a New file of each kind of vocabulary is created empty and added to the includes, and only a component asks for a component's name", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  for (const kind of VOCABULARIES) {
    // Named so that each file sorts after the description, whose name the plan lists first.
    const name = `spare_${kind}`;
    const file = `${name}.ddd.json`;
    await page.getByRole("button", { name: "New file", exact: true }).click();
    const creating = page.getByRole("complementary", { name: "New file" });
    await creating.getByRole("button", { name: "Show the choices for Kind" }).click();
    if (kind === VOCABULARIES[0]) {
      // The server's own list, in its own order (`CREATABLE`, file_plans.py).
      await expect(page.getByRole("listbox").getByRole("option")).toHaveText([
        "component",
        "types",
        "units",
        "constants",
        "sections",
        "rasters",
      ]);
    }
    await page.getByRole("option", { name: kind, exact: true }).click();
    await creating.getByRole("textbox", { name: "File name" }).fill(name);

    // Two files change: the description gains the entry, and the new file is written.
    await expect(
      creating.getByText(`Changes 2 files: project.ddd.json, ${file}`, { exact: true }),
    ).toBeVisible();
    await expect(creating.getByRole("textbox", { name: "Component name" })).toHaveCount(0);
    await creating.getByRole("button", { name: "Apply to 2 files" }).click();

    // Created: the panel goes, and the row's Kind is the file's own, read once the analysis
    // behind the edit has read it (`State.files`) - which this waits out before the next kind.
    const row = page.getByRole("row", { name: file, exact: true });
    await expect(row.getByRole("gridcell").nth(0)).toHaveText(kind);
    await expect(creating).toHaveCount(0);
    expect(JSON.parse(readFileSync(join(vocabularyGui.directory, file), "utf8"))).toEqual({
      [kind]: [],
    });
  }
  const written = JSON.parse(readFileSync(join(vocabularyGui.directory, PROJECT), "utf8")).project;
  expect(written.includes.slice(-VOCABULARIES.length)).toEqual(
    VOCABULARIES.map((kind) => `spare_${kind}.ddd.json`),
  );
});

test("a New file the server refuses says why in its own words, with nothing to apply and nothing written", async ({
  page,
  vocabularyGui,
}) => {
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("button", { name: "New file", exact: true }).click();
  const creating = page.getByRole("complementary", { name: "New file" });
  const kind = creating.getByRole("combobox", { name: "Kind" });
  const name = creating.getByRole("textbox", { name: "File name" });
  const refusal = creating.getByRole("status");
  // Each kind is committed as the first journey commits `component`: typed, then Enter, which
  // closes the list - open, it hides the rest of the page, the refusal included, from the
  // accessibility tree.
  const choose = async (text: string) => {
    await kind.fill(text);
    await kind.press("Enter");
  };

  // (a) A kind the server creates no file of.
  await choose("widgets");
  await name.fill("spare");
  await expect(refusal).toHaveText(
    "no file of kind 'widgets' can be created here; the kinds that can are component, types, " +
      "units, constants, sections and rasters",
  );
  await expect(creating.getByRole("button", { name: /^Apply/ })).toHaveCount(0);

  // (b) A name with a dot in it: the suffix is the server's to add.
  await choose("types");
  await name.fill("spare.types");
  await expect(refusal).toHaveText(
    "'spare.types' cannot name a new file: a name is one or more of the letters a to z and A to " +
      "Z, the digits 0 to 9, '_' and '-', and .ddd.json is added to it",
  );
  await expect(creating.getByRole("button", { name: /^Apply/ })).toHaveCount(0);

  // (c) A file of that name beside the description already.
  await name.fill("units");
  await expect(refusal).toHaveText("units.ddd.json is there already, beside project.ddd.json");
  await expect(creating.getByRole("button", { name: /^Apply/ })).toHaveCount(0);

  // (d) A component, whose own name has not been typed: sent empty, which the server reads as none.
  await choose("component");
  await name.fill("spare");
  await expect(refusal).toHaveText("a new component needs a name, besides its file's");
  await expect(creating.getByRole("button", { name: /^Apply/ })).toHaveCount(0);

  // (e) A component's name the project has already: pump.ddd.json's.
  await creating.getByRole("textbox", { name: "Component name" }).fill("Pump");
  await expect(refusal).toHaveText("this project has a component called 'Pump' already");
  await expect(creating.getByRole("button", { name: /^Apply/ })).toHaveCount(0);

  // Nothing was written by any of them.
  expect(existsSync(join(vocabularyGui.directory, "spare.ddd.json"))).toBe(false);
});

/** `path` as the server writes a path into a sentence: with forward slashes. */
function posixOf(path: string): string {
  return path.replaceAll("\\", "/");
}

test("an Add the server refuses says why in its own words, with nothing to apply and nothing written", async ({
  page,
  gui,
}) => {
  const description = readFileSync(join(gui.directory, "demo.ddd.json"));
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("button", { name: "Add a file", exact: true }).click();
  const adding = page.getByRole("complementary", { name: "Add a file" });
  const path = adding.getByRole("textbox", { name: "Path" });
  const refusal = adding.getByRole("status");
  const refused = async (typed: string, sentence: string) => {
    await path.fill(typed);
    await expect(refusal).toHaveText(sentence);
    await expect(adding.getByRole("button", { name: /^Apply/ })).toHaveCount(0);
  };

  // (a) A file that is not there: created, not added (answered 404, and drawn as any refusal).
  await refused(
    "missing.ddd.json",
    "missing.ddd.json names no file; a file not there yet is created, not added",
  );
  // (b) The description itself.
  await refused(
    "demo.ddd.json",
    "demo.ddd.json is this project's own description, which it cannot include",
  );
  // (c) A file the demo's pattern brings in already.
  await refused(
    "components/controller.ddd.json",
    "components/controller.ddd.json is part of this project already: the pattern " +
      "'components/*.ddd.json' brings it in",
  );
  // (d) A file that is no description of any kind: the demo's C header.
  await refused(
    "include/sensor_hub_driver.h",
    "include/sensor_hub_driver.h is no kind of file a project includes: it cannot be read as " +
      "json, or its top level holds none of project, component, types, units, sections, " +
      "constants and rasters",
  );
  // (e) A file outside what ddd gui serves. Confinement is asked first, so the file need not
  // exist; the directory served is spelled with forward slashes on every platform.
  await refused(
    "../outside.ddd.json",
    `../outside.ddd.json lies outside what ddd gui serves, ${posixOf(gui.directory)}; start it ` +
      "in a directory holding this file to add it here",
  );

  expect(readFileSync(join(gui.directory, "demo.ddd.json"))).toEqual(description);
});

/** A copy's description with its `includes` changed before `ddd gui` starts, and written back
 * whole - two spaces of indent and a final newline, as the examples ship it. Throws where the
 * change leaves the list as it was, so that a journey never serves what it believes it changed. */
function changeIncludes(
  directory: string,
  project: string,
  change: (includes: string[]) => void,
): void {
  const path = join(directory, project);
  const data = JSON.parse(readFileSync(path, "utf8"));
  const before = JSON.stringify(data.project.includes);
  change(data.project.includes);
  if (JSON.stringify(data.project.includes) === before) {
    throw new Error(`${project} still lists what it listed`);
  }
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

test("an entry whose file did not load is listed as not loaded, its kind still read", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("vocabulary", (directory) => {
    // .calib aligned to three bytes, as shared.spec.ts breaks it: still json and plainly a
    // sections file, but no power of two, so the file fails its own model and does not load.
    const path = join(directory, "sections.ddd.json");
    const before = readFileSync(path, "utf8");
    const broken = before.replace(
      /("section": "\.calib"[^}]*?"alignment": )4/,
      (_, head: string) => `${head}3`,
    );
    if (broken === before) throw new Error(`.calib states no alignment 4 in ${path}`);
    writeFileSync(path, broken);
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  // The kind is read off the file's top level, which still parses; its model does not, and the
  // analysis files that on the file.
  const sections = page.getByRole("row", { name: "sections.ddd.json", exact: true });
  await expect(sections.getByRole("gridcell")).toHaveText(["sections", "did not load", "1"]);
  // Against a file that loaded, whose State says nothing.
  const units = page.getByRole("row", { name: UNITS, exact: true });
  await expect(units.getByRole("gridcell")).toHaveText(["units", "", ""]);
});

test("an entry naming no file, and a pattern matching none, are listed as naming no file, with nothing beneath them", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("vocabulary", (directory) => {
    changeIncludes(directory, PROJECT, (includes) => {
      includes.push("missing.ddd.json", "drafts/*.ddd.json");
    });
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  // The loader files `file-not-found` at the plain path and `include-empty` at the pattern, each
  // at its entry, so each row counts the one finding. Neither has a file, so neither has a kind.
  const missing = page.getByRole("row", { name: "missing.ddd.json", exact: true });
  const drafts = page.getByRole("row", { name: "drafts/*.ddd.json", exact: true });
  await expect(missing.getByRole("gridcell")).toHaveText(["", "names no file", "1"]);
  await expect(drafts.getByRole("gridcell")).toHaveText(["", "names no file", "1"]);
  // They are the last two rows, and the pattern has no child row under it.
  await expect(page.getByRole("rowheader")).toHaveText([
    "units.ddd.json",
    "sections.ddd.json",
    "constants.ddd.json",
    "rasters.ddd.json",
    "pump.ddd.json",
    "missing.ddd.json",
    "drafts/*.ddd.json",
  ]);
});

test("a file a pattern matches that the last analysis did not read is listed as not read, until the next analysis reads it", async ({
  page,
  gui,
}) => {
  // Written after the analysis the fixture waited for: a file appearing where a pattern matches
  // starts none (`_files`, api.py, "answered anew each time"), so the list names a file the
  // revision never read.
  writeFileSync(
    join(gui.directory, "components", "extra.ddd.json"),
    JSON.stringify({ component: { name: "Extra", interface: [] } }),
    "utf8",
  );
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  const extra = page.getByRole("row", { name: "components/extra.ddd.json", exact: true });
  await expect(extra.getByRole("gridcell")).toHaveText(["", "not read by the last analysis", ""]);
  const read = page.getByRole("row", { name: "components/controller.ddd.json", exact: true });
  await expect(read.getByRole("gridcell")).toHaveText(["component", "", ""]);

  // A stamp moved: the next analysis expands the pattern again, and reads the file it matches.
  restamp(gui.directory, CONTROLLER);
  await expect(extra.getByRole("gridcell")).toHaveText(["component", "", "1"]);
});

test("a pattern's row is listed with the files it matches beneath it, each one a component, and a sub-project's row is one of kind project", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  // The pattern's own row, then its matches in the loader's order (`expand_include` sorts them by
  // their posix spelling), each named by its path from the description; then the sub-project.
  const table = page.getByRole("grid", { name: "Files" });
  await expect(table.getByRole("rowheader")).toHaveText([
    "components/*.ddd.json",
    "components/controller.ddd.json",
    "components/sensor_hub.ddd.json",
    "components/user_interface.ddd.json",
    "subsystems/logging/logging.ddd.json",
  ]);
  const pattern = table.getByRole("row", { name: "components/*.ddd.json", exact: true });
  await expect(pattern).not.toHaveClass(/\bchild\b/);
  await expect(pattern.getByRole("gridcell")).toHaveText(["", "", ""]);
  for (const component of ["controller", "sensor_hub", "user_interface"]) {
    const child = table.getByRole("row", { name: `components/${component}.ddd.json`, exact: true });
    await expect(child).toHaveClass(/\bchild\b/);
    await expect(child.getByRole("gridcell").nth(0)).toHaveText("component");
  }
  // The sub-project is one entry of its own kind, and nothing is listed under it.
  const logging = table.getByRole("row", {
    name: "subsystems/logging/logging.ddd.json",
    exact: true,
  });
  await expect(logging).not.toHaveClass(/\bchild\b/);
  await expect(logging.getByRole("gridcell").nth(0)).toHaveText("project");
});

test("a removal of a file only a pattern brings in is refused, naming the pattern, with nothing to press", async ({
  page,
  gui,
}) => {
  const description = readFileSync(join(gui.directory, "demo.ddd.json"));
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("row", { name: "components/controller.ddd.json", exact: true }).click();

  // The panel is titled by the row's own entry, and its Remove region holds the server's refusal,
  // which names the file by its base name and the pattern as written (`remove_plan`).
  const removing = page
    .getByRole("complementary", { name: "components/controller.ddd.json", exact: true })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(removing.getByRole("status")).toHaveText(
    "controller.ddd.json has no entry of its own: the pattern 'components/*.ddd.json' brings it " +
      "in, and only the whole pattern can be removed",
  );
  await expect(removing.getByRole("button")).toHaveCount(0);
  expect(readFileSync(join(gui.directory, "demo.ddd.json"))).toEqual(description);
});

test("an Apply the server fails on is sent once, and refused in the Remove panel in its words, which still offers the removal", async ({
  page,
  vocabularyGui,
}) => {
  const description = readFileSync(join(vocabularyGui.directory, PROJECT));
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  await page.getByRole("row", { name: UNITS, exact: true }).click();
  const removing = page
    .getByRole("complementary", { name: UNITS, exact: true })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(
    removing.getByText("Changes 1 file: project.ddd.json", { exact: true }),
  ).toBeVisible();

  // Registered once the plan is drawn: nothing GETs the edit's path, and a POST is never sent
  // again, so the one Apply is the one failed. The Remove journeys stand for New file and Add as
  // well, since all three share `useFilesApply`.
  const failed = await failing(page, "/api/edit", "http");
  const remove = removing.getByRole("button", { name: "Remove from the includes" });
  await remove.click();

  // Not a refusal of a file changed on disk, so it stays until the reader chooses again; and the
  // plan, asked again once the Apply was answered, is drawn under it with its button.
  await expect(removing.getByRole("status")).toHaveText(`The change was refused: ${SERVER_FAILED}`);
  await expect(page.getByRole("row", { name: UNITS, exact: true })).toBeVisible();
  await expect(remove).toBeEnabled();
  expect(failed()).toBe(1);
  // A guard against a write by another path: the POST is answered by `failing`, not the server.
  expect(readFileSync(join(vocabularyGui.directory, PROJECT))).toEqual(description);
});

test("a removal or an add the server could not judge says so in its words, and is still offered", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("vocabulary", (directory) => {
    writeFileSync(
      join(directory, EXTRA),
      JSON.stringify({ component: { name: "Extra", interface: [] } }),
      "utf8",
    );
    // An entry naming no file is an error no build lowers (`file-not-found`), so the project is
    // never analysed to its end, and there is no whole analysis to judge a change against.
    changeIncludes(directory, PROJECT, (includes) => {
      includes.push("missing.ddd.json");
    });
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  await page.getByRole("row", { name: "missing.ddd.json", exact: true }).click();
  const removing = page
    .getByRole("complementary", { name: "missing.ddd.json", exact: true })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(
    removing.getByText(
      "not every analysis of this project ran to its end, so what removing missing.ddd.json " +
        "leaves cannot be judged",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    removing.getByText("Changes 1 file: project.ddd.json", { exact: true }),
  ).toBeVisible();
  await expect(removing.getByRole("button", { name: "Remove from the includes" })).toBeEnabled();

  await page.getByRole("button", { name: "Add a file", exact: true }).click();
  const adding = page.getByRole("complementary", { name: "Add a file" });
  await adding.getByRole("textbox", { name: "Path" }).fill(EXTRA);
  await expect(
    adding.getByText(
      "not every analysis of this project ran to its end, so what adding extra.ddd.json " +
        "brings cannot be judged",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(adding.getByRole("button", { name: "Apply to 1 file" })).toBeEnabled();
});

test("a removal a pattern keeps in says so, and takes the entry out alone, the file staying", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("demo", (directory) => {
    // The controller named beside the pattern that already matches it: New file appends an
    // entry the same way (`create_plan`), and the loader reads the file once.
    changeIncludes(directory, "demo.ddd.json", (includes) => {
      includes.splice(1, 0, "components/controller.ddd.json");
    });
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();

  // Two rows name the file, the pattern's child and the entry, and one key stands for both: the
  // removal is of every entry that has it.
  const rows = page.getByRole("row", { name: "components/controller.ddd.json", exact: true });
  await expect(rows).toHaveCount(2);
  await rows.last().click();
  const removing = page
    .getByRole("complementary", { name: "components/controller.ddd.json", exact: true })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(
    removing.getByText(
      "components/controller.ddd.json stays in the project all the same: the pattern " +
        "'components/*.ddd.json' brings it in.",
      { exact: true },
    ),
  ).toBeVisible();
  await removing.getByRole("button", { name: "Remove from the includes" }).click();

  // The entry went and the file stayed: the pattern's child is the one row left.
  await expect(rows).toHaveCount(1);
  await expect(rows).toHaveClass(/\bchild\b/);
  const written = JSON.parse(readFileSync(join(gui.directory, "demo.ddd.json"), "utf8")).project;
  expect(written.includes).toEqual([
    "components/*.ddd.json",
    "subsystems/logging/logging.ddd.json",
  ]);
});

test("a plan asked after a file changed on disk is refused as out of date in its own panel, for an Add and for a Remove, with nothing to press", async ({
  page,
  vocabularyGui,
}) => {
  writeFileSync(
    join(vocabularyGui.directory, EXTRA),
    JSON.stringify({ component: { name: "Extra", interface: [] } }),
    "utf8",
  );
  // Before any plan is asked, and unseen by the watcher: the revision the page holds is the one
  // before, and a plan that judges a change reads the files afresh (`_judged`, api.py), so the
  // server refuses the plan itself, not an Apply.
  writeUnseen(
    vocabularyGui.directory,
    PROJECT,
    withFullStop(readFileSync(join(vocabularyGui.directory, PROJECT), "utf8")),
  );
  await page.goto(vocabularyGui.address);
  await page.getByRole("link", { name: "Files", exact: true }).click();
  const outOfDate =
    "project.ddd.json changed since the project was analysed, so the change cannot be judged " +
    "until the project is analysed again";

  await page.getByRole("button", { name: "Add a file", exact: true }).click();
  const adding = page.getByRole("complementary", { name: "Add a file" });
  await adding.getByRole("textbox", { name: "Path" }).fill(EXTRA);
  await expect(adding.getByRole("status")).toHaveText(outOfDate);
  await expect(adding.getByRole("button", { name: /^Apply/ })).toHaveCount(0);

  await page.getByRole("row", { name: UNITS, exact: true }).click();
  const removing = page
    .getByRole("complementary", { name: UNITS, exact: true })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(removing.getByRole("status")).toHaveText(outOfDate);
  await expect(removing.getByRole("button")).toHaveCount(0);
});

test("a finding about an empty vocabulary leads to its row of the Files tab, whose removal is planned at once", async ({
  page,
  copiedGui,
}) => {
  const gui = await copiedGui("vocabulary", (directory) => {
    writeFileSync(join(directory, "extra_types.ddd.json"), JSON.stringify({ types: [] }), "utf8");
    changeIncludes(directory, PROJECT, (includes) => {
      includes.push("extra_types.ddd.json");
    });
  });
  await page.goto(gui.address);
  await page.getByRole("link", { name: "Findings", exact: true }).click();
  await page.getByRole("row", { name: /empty-vocabulary/ }).click();
  await page
    .getByRole("complementary", { name: "empty-vocabulary" })
    .getByRole("link", { name: "Open extra_types.ddd.json", exact: true })
    .click();

  // The Files tab, on the row the finding is filed on: its key is the file's own path, which the
  // address carries as `path`.
  await expect(page).toHaveURL(
    (url) =>
      url.searchParams.get("view") === "files" &&
      posixOf(url.searchParams.get("path") ?? "").endsWith("/extra_types.ddd.json"),
  );
  await expect(page.getByRole("link", { name: "Files", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  const row = page.getByRole("row", { name: "extra_types.ddd.json", exact: true });
  await expect(row).toHaveAttribute("aria-selected", "true");
  // A move within the page is not an arrival (`arrived`, FilesPage): the removal is planned at
  // once, with no press of "Plan its removal" asked of the reader first.
  const removing = page
    .getByRole("complementary", { name: "extra_types.ddd.json", exact: true })
    .getByRole("region", { name: "Remove from the includes" });
  await expect(
    removing.getByText("Changes 1 file: project.ddd.json", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Plan its removal" })).toHaveCount(0);
});
