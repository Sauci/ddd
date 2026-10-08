import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { UNITS } from "./demo";
import { expect, test } from "./fixtures";

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

  let release = (): void => undefined;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/files", async (route) => {
    await released;
    await route.continue();
  });
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
 * Released, the list no longer carries the entry, and the row stays gone; the page's own undo
 * puts the entry back, and its row with it.
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

  let release = (): void => undefined;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/files", async (route) => {
    await released;
    await route.continue();
  });
  const listed = page.waitForResponse((response) => response.url().endsWith("/api/files"));
  try {
    await remove.click();
    await expect(unitsRow).toHaveCount(0);
  } finally {
    release();
  }
  await listed;
  await expect(unitsRow).toHaveCount(0);

  await page.getByRole("button", { name: `Undo '${UNITS}' removed from the includes` }).click();
  await page
    .getByRole("region", { name: "Undo" })
    .getByRole("button", { name: "Put back 1 file" })
    .click();
  await expect(unitsRow).toBeVisible();
});

/**
 * The row the page was loaded with waits for the reader (P18b-10, spec §7): a Remove plan
 * re-analyses the project, running its plugins, so the panel of a row an address chose - a link
 * from elsewhere, a bookmark, a typed address, a reload - asks for none until the reader presses
 * for it. A row the reader selects within the page is planned at once, as before.
 */
test("the row the page was opened on waits for the reader before its removal is planned", async ({
  page,
  vocabularyGui,
}) => {
  // Signed in at the address ddd gui printed, whose token the page keeps for the next address
  // this tab opens.
  await page.goto(vocabularyGui.address);
  await expect(page.getByRole("button", { name: "Pump", exact: true })).toBeVisible();
  const planned: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/files-plan") planned.push(request.url());
  });

  // Loaded at the row's own address, as a link from elsewhere would load it: nothing that runs
  // a plugin is asked until the reader asks (P18b-10). The row's key is the file's absolute,
  // posix-separated path (`IncludedEntryReply.key`).
  const key = `${vocabularyGui.directory.replaceAll("\\", "/")}/${UNITS}`;
  const origin = new URL(vocabularyGui.address).origin;
  await page.goto(`${origin}/project?view=files&path=${encodeURIComponent(key)}`);
  const unitsRemoving = page
    .getByRole("complementary", { name: UNITS })
    .getByRole("region", { name: "Remove from the includes" });
  const ask = unitsRemoving.getByRole("button", { name: "Plan its removal" });
  await expect(ask).toBeVisible();
  expect(planned).toEqual([]);

  await ask.click();
  await expect(unitsRemoving.getByText("Changes 1 file: project.ddd.json")).toBeVisible();
  expect(planned).toHaveLength(1);

  // A row the reader selects in the table is planned at once, as before.
  await page.getByRole("row", { name: "constants.ddd.json" }).click();
  await expect.poll(() => planned.length).toBe(2);
  await expect(page.getByRole("button", { name: "Plan its removal" })).toHaveCount(0);
});

/**
 * Back and forward within the page are the reader's own moves (spec §7), so a row reached by Back
 * is planned at once - even in a page reloaded since. There Back is the first move the reloaded
 * page makes, the address it was loaded with being the Findings tab's: Chrome goes back to the
 * row's entry within that same page, firing `popstate` with no load of its own (a value set on
 * `window` before Back was still there after it, in Chrome 153 on the Linux development PC).
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
  const planned: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/files-plan") planned.push(request.url());
  });

  await page.goBack();
  await expect(refused).toBeVisible();
  expect(planned).toHaveLength(1);
  await expect(page.getByRole("button", { name: "Plan its removal" })).toHaveCount(0);
});
