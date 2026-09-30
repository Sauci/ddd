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
  // refusal the Task 9 journey reads too"), read here rather than restated - a second spelling
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
