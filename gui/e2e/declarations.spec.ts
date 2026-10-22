import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import {
  CONTROLLER,
  chooseUnit,
  drift,
  driftIn,
  driftMaxUnseen,
  failing,
  held,
  openPanel,
  PUMP,
  restamp,
  SENSOR_HUB,
  SERVER_FAILED,
} from "./demo";
import { expect, test } from "./fixtures";

/** One variable's definition in a file of the copy, read back from disk - the same shape
 * keys.spec.ts's own `valueA()` reads, generalised to whichever name a journey just wrote. */
function declarationOf(directory: string, file: string, name: string): Record<string, unknown> {
  const data = JSON.parse(readFileSync(join(directory, file), "utf8"));
  const entry = data.component.interface.find(
    (declaration: { definition: { name: string } }) => declaration.definition.name === name,
  );
  return entry.definition;
}

/** ValueA's own `"name"` line taken out of Controller's file, and nothing else: the file still
 * parses, and breaks the component schema, which a definition with no name does (`schema`, filed
 * at `component.interface[0].definition.name`). The first `"name": "ValueA",` of the file is that
 * definition's. */
function namelessValueA(directory: string): void {
  const path = join(directory, CONTROLLER);
  const text = readFileSync(path, "utf8");
  const changed = text.replace(/\n\s*"name": "ValueA",/, "");
  if (changed === text) throw new Error(`${CONTROLLER} names no ValueA`);
  writeFileSync(path, changed, "utf8");
}

test("a variable another component produces is read, keys and all", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  const name = adding.getByRole("combobox", { name: "Name" });
  await name.fill("ValueC");
  await name.press("Enter");
  await expect(adding.getByText("Reads ValueC as SensorHub declares it.")).toBeVisible();
  await adding.getByRole("button", { name: "Show changes" }).click();
  await expect(adding.locator(".hunk")).toHaveCount(1);

  await adding.getByRole("button", { name: "Apply to 1 file" }).click();
  // The panel that opens on success is ValueC's own (`DeclarePanel.onDeclared`), which only
  // happens once the edit's queries - `file` among them - have been invalidated and re-read: a
  // page state that itself proves the write landed, not a response the test waited on directly.
  await expect(page.getByRole("complementary", { name: "ValueC" })).toBeVisible();

  // The rule journey 1 exists to pin: read into Controller, ValueC carries the producer's unit
  // but neither an id (Controller does not produce it) nor an init (nothing here states one).
  const definition = declarationOf(gui.directory, CONTROLLER, "ValueC");
  expect(definition.unit).toBe("degC");
  expect(definition.id).toBeUndefined();
  expect(definition.init).toBeUndefined();
});

test("a new measurement is declared and stamped", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  const name = adding.getByRole("combobox", { name: "Name" });
  await name.fill("Pressure");
  await name.press("Enter");
  const scope = adding.getByRole("combobox", { name: "Scope" });
  await scope.fill("produces");
  await scope.press("Enter");
  const kind = adding.getByRole("combobox", { name: "Kind" });
  await kind.fill("measurement");
  await kind.press("Enter");
  // Every kind requires volatile; a measurement's storage is otherwise free, but the project
  // still requires exactly one of datatype or typename (global constraints), so a datatype is
  // stated too - the one the brief's own story (`ANewMeasurement`) reaches for.
  const volatile = adding.getByRole("combobox", { name: "Volatile of Pressure" });
  await volatile.fill("false");
  await volatile.press("Enter");
  const datatype = adding.getByRole("combobox", { name: "Datatype of Pressure" });
  await datatype.fill("uint8");
  await datatype.press("Enter");
  await expect(
    adding.getByText("Declares Pressure, a measurement this component produces."),
  ).toBeVisible();

  await adding.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByRole("complementary", { name: "Pressure" })).toBeVisible();

  const text = readFileSync(join(gui.directory, CONTROLLER), "utf8");
  expect(text).toMatch(/"name": "Pressure",\s*"id": "[0-9a-z]{12}"/);
});

test("a value block is declared with the shape it is given", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  const name = adding.getByRole("combobox", { name: "Name" });
  await name.fill("BlockB");
  await name.press("Enter");
  const kind = adding.getByRole("combobox", { name: "Kind" });
  await kind.fill("value_block");
  await kind.press("Enter");

  // Task 5's own field: a row commits as it is typed, with no chooser of its own to pick from -
  // the demo declares no constants, so a dimension is a plain whole number.
  await adding.getByRole("combobox", { name: "Dimension 1 of BlockB" }).fill("4");
  await adding.getByRole("button", { name: "Add a dimension" }).click();
  await adding.getByRole("combobox", { name: "Dimension 2 of BlockB" }).fill("8");
  // dimensions and volatile are both required for a value_block, and storage still needs naming
  // exactly once - the same two facts journey 2 states, carried over rather than repeated.
  const volatile = adding.getByRole("combobox", { name: "Volatile of BlockB" });
  await volatile.fill("false");
  await volatile.press("Enter");
  const datatype = adding.getByRole("combobox", { name: "Datatype of BlockB" });
  await datatype.fill("uint8");
  await datatype.press("Enter");

  await adding.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByRole("complementary", { name: "BlockB" })).toBeVisible();

  const text = readFileSync(join(gui.directory, CONTROLLER), "utf8");
  expect(text).toContain('"dimensions": [4, 8]');
});

test("a dimension removed leaves the next one in its place, and a shape keeps one", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  const name = adding.getByRole("combobox", { name: "Name" });
  await name.fill("BlockC");
  await name.press("Enter");
  const kind = adding.getByRole("combobox", { name: "Kind" });
  await kind.fill("value_block");
  await kind.press("Enter");

  // Two dimensions, 4 and 8, typed as the journey above types them; then the first is removed.
  await adding.getByRole("combobox", { name: "Dimension 1 of BlockC" }).fill("4");
  await adding.getByRole("button", { name: "Add a dimension" }).click();
  await adding.getByRole("combobox", { name: "Dimension 2 of BlockC" }).fill("8");
  await adding.getByRole("button", { name: "Remove dimension 1 of BlockC" }).click();

  // The row left is the second one, 8, now the first; and a shape keeps one dimension at least, so
  // the one left cannot be removed.
  await expect(adding.getByRole("combobox", { name: "Dimension 1 of BlockC" })).toHaveValue("8");
  await expect(adding.getByRole("combobox", { name: "Dimension 2 of BlockC" })).toHaveCount(0);
  await expect(adding.getByRole("button", { name: "Remove dimension 1 of BlockC" })).toBeDisabled();
});

test("a curve is declared against an axis the project has", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  const name = adding.getByRole("combobox", { name: "Name" });
  await name.fill("CurveC");
  await name.press("Enter");
  const kind = adding.getByRole("combobox", { name: "Kind" });
  await kind.fill("curve");
  await kind.press("Enter");
  const volatile = adding.getByRole("combobox", { name: "Volatile of CurveC" });
  await volatile.fill("false");
  await volatile.press("Enter");

  // The object-reference chooser (`EDITORS`' axis, editor "name"): its list is the project's own
  // axis objects, AxisA and AxisB, not free text - the one part of the form nothing else covers.
  await adding.getByRole("button", { name: "Show the choices for Axis of CurveC" }).click();
  // The list is a popover at the root of the page, not inside the panel (units.spec.ts's picker
  // journey notes the same of the unit list).
  await expect(page.getByRole("option", { name: "AxisA", exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: "AxisB", exact: true })).toBeVisible();
  await page.getByRole("option", { name: "AxisA", exact: true }).click();
  const datatype = adding.getByRole("combobox", { name: "Datatype of CurveC" });
  await datatype.fill("uint8");
  await datatype.press("Enter");

  await adding.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByRole("complementary", { name: "CurveC" })).toBeVisible();

  const text = readFileSync(join(gui.directory, CONTROLLER), "utf8");
  expect(text).toContain('"axis": "AxisA"');
});

test("a name the project already has is refused in its own words", async ({ page, gui }) => {
  const before = readFileSync(join(gui.directory, CONTROLLER));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  const name = adding.getByRole("combobox", { name: "Name" });
  await name.fill("ValueA");
  await name.press("Enter");
  // ValueA is not among the names Controller could read (it already declares it itself), so the
  // form treats it as a new one - the hazard spec 5.2 states rather than hides, and what actually
  // reaches the server for a refusal: a name alone asks for nothing until a kind and volatile
  // make a definition worth sending.
  const kind = adding.getByRole("combobox", { name: "Kind" });
  await kind.fill("measurement");
  await kind.press("Enter");
  const volatile = adding.getByRole("combobox", { name: "Volatile of ValueA" });
  await volatile.fill("true");
  await volatile.press("Enter");

  await expect(adding.getByText("'ValueA' is already declared by this project")).toBeVisible();
  await expect(adding.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
});

test("a declaration is removed and put back", async ({ page, gui }) => {
  const before = readFileSync(join(gui.directory, CONTROLLER));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("row", { name: /ValueB/ }).click();
  const panel = page.getByRole("complementary", { name: "ValueB" });

  // Controller reads ValueB (scope "input"); SensorHub produces it and UserInterface also reads
  // it. removalSentence names only the readers left behind once at least one remains rather than
  // every remaining declarer (declarations.test.ts's "the readers left behind are named" and
  // "with no reader left..." cover both halves of the same rule) - so with Controller's own
  // reading gone, UserInterface is the one reader still left, and SensorHub - a producer, not a
  // reader - is not named.
  await expect(
    panel.getByText("Removes ValueB from Controller; UserInterface still reads it."),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Remove from Controller" }).click();

  // The row leaving Controller's own table is the page's proof the write landed: the table is
  // drawn from the `file` query, which the removal's mutation only invalidates once the edit has
  // been applied on the server (VariablePanel's `onSettled`).
  await expect(page.getByRole("rowheader", { name: "ValueB", exact: true })).toHaveCount(0);
  expect(readFileSync(join(gui.directory, CONTROLLER), "utf8")).not.toContain('"ValueB"');

  const undo = page.getByRole("button", { name: "Undo removing ValueB from Controller" });
  await undo.click();
  const strip = page.getByRole("region", { name: "Undo" });
  await expect(strip.getByText("Puts back 1 file: controller.ddd.json")).toBeVisible();
  await strip.getByRole("button", { name: "Put back 1 file" }).click();

  // The point of this journey: put back byte for byte, not merely "ValueB is declared again" -
  // the shape undo.spec.ts's own journeys already use for the same claim.
  await expect.poll(() => readFileSync(join(gui.directory, CONTROLLER)).equals(before)).toBe(true);
});

test("a declaration made from a file that changed on disk is refused, and made once the page has caught up", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration" }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration" });
  const name = adding.getByRole("combobox", { name: "Name" });
  await name.fill("ValueC");
  await name.press("Enter");
  await expect(adding.getByText("Reads ValueC as SensorHub declares it.")).toBeVisible();
  const apply = adding.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeEnabled();

  // Controller changes under the plan the panel holds, unseen by the session's watcher, as
  // keys.spec.ts's own stale journey changes it: only the Apply's own fingerprint check sees it.
  const path = join(gui.directory, CONTROLLER);
  driftMaxUnseen(gui.directory, CONTROLLER, "ValueA", 999);
  const drifted = readFileSync(path);
  await apply.click();
  await expect(adding.getByRole("status")).toHaveText(
    "A file changed on disk, so nothing was written. The page now shows the files as they are.",
  );
  await expect(apply).toHaveCount(0);
  expect(readFileSync(path).equals(drifted)).toBe(true);

  // A stamp moved with no byte touched is what lets the next poll read the drifted file. The
  // analysis landing shows as the disagreement the drift made, in Controller's own findings.
  restamp(gui.directory, CONTROLLER);
  await expect(
    page.getByRole("link", {
      name: "'ValueA' is declared differently by component 'Controller' than by 'SensorHub' (limits: [0, 999] != [0, 100])",
      exact: true,
    }),
  ).toBeVisible({ timeout: 15000 });

  // Asked again, against the files as they are now: the refusal goes with the edit, and the
  // declaration is made.
  await name.fill("ValueC");
  await name.press("Enter");
  await adding.getByRole("button", { name: "Apply to 1 file" }).click();
  await expect(page.getByRole("complementary", { name: "ValueC" })).toBeVisible();
  expect(declarationOf(gui.directory, CONTROLLER, "ValueC").unit).toBe("degC");
});

test("a removal made from a file that changed on disk is refused, and made once the page has caught up", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("row", { name: /ValueB/ }).click();
  const removing = page
    .getByRole("complementary", { name: "ValueB" })
    .getByRole("region", { name: "Remove the declaration" });
  const remove = removing.getByRole("button", { name: "Remove from Controller" });
  await expect(remove).toBeEnabled();

  // Controller changes under the plan the panel holds, unseen by the session's watcher, as the
  // declaration's own stale journey above changes it.
  const path = join(gui.directory, CONTROLLER);
  driftMaxUnseen(gui.directory, CONTROLLER, "ValueA", 999);
  const drifted = readFileSync(path);
  await remove.click();
  await expect(removing.getByRole("status")).toHaveText(
    "A file changed on disk, so nothing was written. The panel now shows the files as they are.",
  );
  await expect(remove).toHaveCount(0);
  expect(readFileSync(path).equals(drifted)).toBe(true);

  // A stamp moved with no byte touched lets the next poll read the drifted file; the refusal is
  // held until the analysis moves on, and goes with it.
  restamp(gui.directory, CONTROLLER);
  await expect(removing.getByRole("status")).toHaveCount(0, { timeout: 15000 });
  await remove.click();
  await expect(page.getByRole("rowheader", { name: "ValueB", exact: true })).toHaveCount(0);
  expect(readFileSync(path, "utf8")).not.toContain('"ValueB"');
});

test("a finding's link to a variable of the same file opens its panel in place, without loading the page again", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const grid = page.getByRole("grid", { name: "Declarations of Controller" });
  await expect(grid).toBeVisible();

  // Controller's reading of ValueA drifted from outside: the one finding of this component is
  // that it disagrees with its producer, and its message is a link to ValueA.
  drift(gui.directory);
  const link = page.getByRole("link", {
    name: "'ValueA' is declared differently by component 'Controller' than by 'SensorHub' (unit: 'rpm' != '%')",
    exact: true,
  });
  await expect(link).toBeVisible();

  // A marker on this document: a link the page follows by loading its address again starts a
  // new document, where it is gone.
  await page.evaluate(() => {
    (window as unknown as { marker: string }).marker = "this document";
  });
  await link.click();
  await expect(page.getByRole("complementary", { name: "ValueA" })).toBeVisible();
  await expect(grid).toBeVisible();
  const kept = await page.evaluate(() => (window as unknown as { marker?: string }).marker);
  expect(kept).toBe("this document");
});

test("a component file that stops parsing is shown by its path and the parser's words, and nothing else", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Controller", level: 1 })).toBeVisible();

  // Saved half-edited, as findings.spec.ts's own journey of a finding that leads nowhere saves
  // it: it no longer parses. Cut on the component's own page: once its file stops parsing, its
  // module leaves the canvas, and there is nothing left there to press.
  const file = join(gui.directory, CONTROLLER);
  const before = readFileSync(file);
  writeFileSync(file, before.subarray(0, Math.floor(before.length / 2)));

  // The path as the server spells it in this sentence: the file's own, in this system's
  // separators (`str()` of its resolved path, so with backslashes on windows). Then json's own
  // words for this cut of this file, read off the page: a string cut in two, at the character
  // they give, the same on python 3.12 and 3.14. The file is checked out with LF endings on every
  // system (.gitattributes), so its bytes, and the cut, are the same on all of them.
  const sentence = `${file} is not json: Unterminated string starting at: line 110 column 27 (char 3427)`;
  await expect(page.getByRole("alert")).toHaveText(sentence);
  await expect(page.getByRole("main")).toHaveText(sentence);
  await expect(page.getByRole("heading")).toHaveCount(0);
  await expect(page.getByRole("grid")).toHaveCount(0);
});

test("a component file failing to load leaves the server's own error, and nothing else", async ({
  page,
  gui,
}) => {
  // Registered before the page loads: Controller's file is asked for when its page opens.
  await failing(page, "/api/file", "http");
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();

  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(page.getByRole("main")).toHaveText(SERVER_FAILED);
  await expect(page.getByRole("heading")).toHaveCount(0);
  await expect(page.getByRole("grid")).toHaveCount(0);
});

test("an address naming a file the project does not include says so, and shows nothing else", async ({
  page,
  gui,
}) => {
  // A component dropped from the project, its file still on disk: beside the project's own, where
  // the include `components/*.ddd.json` does not reach it.
  writeFileSync(
    join(gui.directory, "retired.ddd.json"),
    readFileSync(join(gui.directory, CONTROLLER)),
  );

  // Signed in at the address ddd gui printed, and drawn before the address is left: the page keeps
  // its token in the tab's local storage (part 18b), so the next address this tab opens is signed
  // in already.
  await page.goto(gui.address);
  await expect(page.getByRole("button", { name: "Controller", exact: true })).toBeVisible();

  // A bookmark of that component, spelled in the address as the page spells every file, absolute
  // and posix-separated; the server answers with it spelled that way (`as_posix()`) wherever it
  // runs.
  const retired = `${gui.directory.replaceAll("\\", "/")}/retired.ddd.json`;
  const origin = new URL(gui.address).origin;
  await page.goto(`${origin}/component?file=${encodeURIComponent(retired)}`);

  const sentence = `${retired} is not a description file of the open project`;
  await expect(page.getByRole("alert")).toHaveText(sentence);
  await expect(page.getByRole("main")).toHaveText(sentence);
  await expect(page.getByRole("heading")).toHaveCount(0);
  await expect(page.getByRole("grid")).toHaveCount(0);
});

test("a component's page says it is reading its file until it is read", async ({ page, gui }) => {
  await page.goto(gui.address);
  // The canvas drawn first: nothing on the way to a component's page asks for its file, and only
  // that page does (`getFile`), so the first `/api/file` is the page's own - and held, the read
  // this journey is about.
  const controller = page.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();
  const reading = page.getByText("Reading the file…", { exact: true });
  const release = await held(page, "/api/file");
  try {
    await controller.click();
    // The line stands alone: nothing of the page is drawn until its file is read.
    await expect(reading).toBeVisible();
    await expect(page.getByRole("grid")).toHaveCount(0);
  } finally {
    release();
  }
  await expect(
    page.getByRole("heading", { name: "Controller", level: 1, exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("grid", { name: "Declarations of Controller" })).toBeVisible();
  await expect(reading).toHaveCount(0);
});

test("a component file that breaks its schema is drawn as any file is, its nameless declaration named by its place", async ({
  page,
  copiedGui,
}) => {
  // The file still parses, and `Session.read_file` checks no schema, so its page is the page of
  // any file: unlike a file that stops parsing (above), which shows its parse error alone. The
  // schema's finding is filed on the declaration whose name is gone, and the analysis lists the
  // module as not loaded, so the finding leads nowhere (`route_of`).
  const gui = await copiedGui("demo", namelessValueA);
  await page.goto(gui.address);
  // The canvas draws this module as "Controller (not loaded)" (canvas.spec.ts), so the page is
  // reached through the Table tab, whose button reads the file's own name.
  const table = page.getByRole("link", { name: "Table", exact: true });
  await expect(table).toBeVisible();
  await table.click();
  const controller = page.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();
  await controller.click();

  await expect(
    page.getByRole("heading", { name: "Controller", level: 1, exact: true }),
  ).toBeVisible();
  const grid = page.getByRole("grid", { name: "Declarations of Controller" });
  await expect(grid).toBeVisible();
  // A declaration with no name is named by its place in the file, and keeps its scope and its
  // finding's chip.
  await expect(grid.getByRole("rowheader", { name: "declaration 1", exact: true })).toBeVisible();
  const row = grid.getByRole("row", { name: "declaration 1", exact: true });
  await expect(row.getByRole("gridcell", { name: "input", exact: true })).toBeVisible();
  await expect(row.getByRole("gridcell", { name: "schema", exact: true })).toBeVisible();

  // Pydantic's own words for a missing key; the finding is text, not a link.
  await expect(
    page.getByRole("heading", { name: "Findings in this component", level: 2 }),
  ).toBeVisible();
  const finding = page.getByRole("listitem").filter({ hasText: "schema" });
  await expect(finding).toHaveText("schema Field required");
  await expect(finding.getByRole("link")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("a component's page says it is reading its findings until they are read", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  const controller = page.getByRole("button", { name: "Controller", exact: true });
  await expect(controller).toBeVisible();
  // The findings of this file alone: the Findings tab asks `/api/findings` too, but without a
  // `file`, and this journey never visits it.
  const release = await held(
    page,
    (url) => url.pathname === "/api/findings" && url.searchParams.has("file"),
  );
  const reading = page.getByText("Reading the findings…", { exact: true });
  const none = page.getByText("None.", { exact: true });
  try {
    await controller.click();
    // The file is not held: its page is drawn, and the findings' heading with it.
    await expect(
      page.getByRole("heading", { name: "Controller", level: 1, exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("grid", { name: "Declarations of Controller" })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Findings in this component", level: 2 }),
    ).toBeVisible();
    await expect(reading).toBeVisible();
    await expect(none).toHaveCount(0);
  } finally {
    release();
  }
  // examples/demo has no finding on its own.
  await expect(none).toBeVisible();
  await expect(reading).toHaveCount(0);
});

test("a component's findings failing to load leave the server's own error under its table", async ({
  page,
  gui,
}) => {
  // Registered before the page loads: nothing on the way to a component's page asks for findings.
  const failed = await failing(page, "/api/findings", "http");
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();

  // The file reads, so the table is drawn; the findings' read alone failed.
  await expect(page.getByRole("grid", { name: "Declarations of Controller" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(page.getByText("None.", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Reading the findings…", { exact: true })).toHaveCount(0);
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("a component with no finding says None., until one comes", async ({ page, gui }) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  // Exact: the Unit column's lower case `none` is another word.
  const none = page.getByText("None.", { exact: true });
  await expect(none).toBeVisible();

  // Controller's reading of ValueA drifted from outside and written plainly, so that the watcher
  // sees it: the finding comes with the next revision, and None. goes.
  drift(gui.directory);
  await expect(
    page.getByRole("link", {
      name: "'ValueA' is declared differently by component 'Controller' than by 'SensorHub' (unit: 'rpm' != '%')",
      exact: true,
    }),
  ).toBeVisible();
  await expect(none).toHaveCount(0);
});

test("a variable's panel says it is reading the variable until it is read", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const row = page.getByRole("row", { name: "ValueB", exact: true });
  await expect(row).toBeVisible();
  // The variable's own read alone: `/api/units` and the removal's plan go through. The panel says
  // it is reading until both the variable and the units answer.
  const release = await held(
    page,
    (url) => url.pathname === "/api/variable" && url.searchParams.get("name") === "ValueB",
  );
  const panel = page.getByRole("complementary", { name: "ValueB", exact: true });
  const reading = panel.getByText("Reading ValueB…", { exact: true });
  try {
    await row.click();
    await expect(reading).toBeVisible();
    await expect(panel.getByRole("region", { name: "Remove the declaration" })).toHaveCount(0);
  } finally {
    release();
  }
  // No key of ValueB disagrees, and a row's press asks no focus: the table alone.
  await expect(
    panel.getByText("Select a key to settle it on every declaration.", { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByText("Removes ValueB from Controller; UserInterface still reads it.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(reading).toHaveCount(0);
});

test("a variable's panel whose variable fails to load says why, beside the table", async ({
  page,
  gui,
}) => {
  // The pathname is exact: `/api/declaration-plan`, `/api/settle` and `/api/units` go through.
  const failed = await failing(page, "/api/variable", "http");
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const row = page.getByRole("row", { name: "ValueB", exact: true });
  await expect(row).toBeVisible();
  await row.click();

  const panel = page.getByRole("complementary", { name: "ValueB", exact: true });
  await expect(panel.getByRole("heading", { name: "ValueB" })).toBeVisible();
  await expect(panel.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(panel.getByText("Select a key to settle it on every declaration.")).toHaveCount(0);
  await expect(panel.getByRole("region", { name: "Remove the declaration" })).toHaveCount(0);
  // The table stays beside it, and the failure is not the variable's going: that is `not-found`,
  // and the server's answer here is `internal`.
  await expect(page.getByRole("rowheader", { name: "ValueB", exact: true })).toBeVisible();
  await expect(page.getByText("ValueB is no longer declared in the open project.")).toHaveCount(0);
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("a finding in a variable's panel leads to the unit it names, on the Units tab", async ({
  page,
  copiedGui,
}) => {
  // PumpSpeed states a unit the units file does not list, before the server starts: the first
  // analysis files `unknown-unit` at PumpSpeed's own `unit`.
  const gui = await copiedGui("vocabulary", (directory) => {
    driftIn(directory, PUMP, "PumpSpeed", "RPM");
  });
  const panel = await openPanel(page, gui.address, "PumpSpeed", "Pump");
  // The panel's own link, not the page's list of the component's findings, which carries a second
  // link of that name. The finding is about the unit, not about this variable, so the panel draws
  // an address: following it loads the Units tab.
  const link = panel.getByRole("listitem").filter({ hasText: "unknown-unit" }).getByRole("link", {
    name: "'RPM' is not a unit this project declares - did you mean 'rpm'?",
    exact: true,
  });
  await expect(link).toBeVisible();
  await link.click();

  await expect(page).toHaveURL(/\/project\?view=units&unit=RPM$/);
  const unit = page.getByRole("complementary", { name: "RPM", exact: true });
  await expect(
    unit.getByText("not in the vocabulary · stated in 1 place, 1 file", { exact: true }),
  ).toBeVisible();
  await expect(
    unit
      .getByRole("grid", { name: "Where RPM is stated" })
      .getByRole("rowheader", { name: "PumpSpeed", exact: true }),
  ).toBeVisible();
});

test("a unit outside the project's vocabulary is said to be, and still offered", async ({
  page,
  vocabularyGui,
}) => {
  const project = join(vocabularyGui.directory, PUMP);
  const before = readFileSync(project);
  // The unit cell opens the panel on its Unit row, with the field focused.
  const panel = await openPanel(page, vocabularyGui.address, "PumpSpeed", "Pump");
  const picker = panel.getByRole("combobox", { name: "Unit of PumpSpeed" });
  const note = panel.getByText("Not one of this project's units", { exact: true });
  // units.ddd.json lists rpm, so the unit PumpSpeed states says nothing.
  await expect(picker).toHaveValue("rpm");
  await expect(note).toHaveCount(0);

  // Typed, a unit the list does not hold is still offered, under "As typed", and the entry says
  // so in lower case. The list is a popover at the root of the page, not inside the panel.
  await picker.fill("RPM");
  await expect(page.getByRole("option", { name: "RPM", exact: true })).toHaveText(
    /not one of this project's units/,
  );
  // Enter takes the text no entry holds. The note under the field is said, not refused: the
  // change is previewed all the same.
  await picker.press("Enter");
  await expect(picker).toHaveValue("RPM");
  await expect(note).toBeVisible();
  // It is also the field's description, which a screen reader reads with the field. The note
  // comes after the field first drew, which is when React Aria ties a description to its field.
  await expect(picker).toHaveAccessibleDescription("Not one of this project's units");
  await expect(panel.getByText("Changes 1 file: pump.ddd.json", { exact: true })).toBeVisible();

  // A unit the vocabulary lists: no note. Nothing was applied on the way.
  await picker.fill("kPa");
  await picker.press("Enter");
  await expect(picker).toHaveValue("kPa");
  await expect(note).toHaveCount(0);
  expect(readFileSync(project).equals(before)).toBe(true);
});

test("the add panel says it is reading what may be declared until it is read", async ({
  page,
  gui,
}) => {
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const add = page.getByRole("button", { name: "Add a declaration", exact: true });
  await expect(add).toBeVisible();
  // Only the add panel asks what may be declared (`getDeclarable`).
  const release = await held(page, "/api/declarable");
  const adding = page.getByRole("complementary", { name: "Add a declaration", exact: true });
  // The page's own reading line, gone by now, says the same sentence: this one is the panel's.
  const reading = adding.getByText("Reading the file…", { exact: true });
  const name = adding.getByRole("combobox", { name: "Name" });
  try {
    await add.click();
    await expect(reading).toBeVisible();
    await expect(name).toHaveCount(0);
  } finally {
    release();
  }
  await expect(name).toBeVisible();
  await expect(
    adding.getByText("Choose a variable, or type a new name.", { exact: true }),
  ).toBeVisible();
  await expect(reading).toHaveCount(0);
});

test("the add panel whose choices fail to load says why, and offers nothing to fill", async ({
  page,
  gui,
}) => {
  const failed = await failing(page, "/api/declarable", "http");
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const add = page.getByRole("button", { name: "Add a declaration", exact: true });
  await expect(add).toBeVisible();
  await add.click();

  const adding = page.getByRole("complementary", { name: "Add a declaration", exact: true });
  await expect(adding.getByRole("alert")).toHaveText(SERVER_FAILED);
  await expect(adding.getByRole("combobox", { name: "Name" })).toHaveCount(0);
  await expect(adding.getByRole("button", { name: "Close Add a declaration" })).toBeVisible();
  // The table stays beside it.
  await expect(page.getByRole("grid", { name: "Declarations of Controller" })).toBeVisible();
  expect(failed()).toBeGreaterThanOrEqual(1);
});

test("a value block's dimension is picked from the project's constants", async ({
  page,
  vocabularyGui,
}) => {
  // The one example that declares constants: TREND_SAMPLES in constants.ddd.json, and
  // PRESSURE_CELLS inline in pump.ddd.json. The demo declares none.
  await page.goto(vocabularyGui.address);
  await page.getByRole("button", { name: "Pump", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration", exact: true }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration", exact: true });
  const name = adding.getByRole("combobox", { name: "Name" });
  await name.fill("TrendB");
  await name.press("Enter");
  const kind = adding.getByRole("combobox", { name: "Kind" });
  await kind.fill("value_block");
  await kind.press("Enter");

  await adding.getByRole("button", { name: "Show the choices for Dimension 1 of TrendB" }).click();
  // The list is a popover at the root of the page, not inside the panel (units.spec.ts's picker
  // journey notes the same of the unit list); the constants are the project's, sorted.
  const constants = page.getByRole("group", { name: "This project's constants" });
  await expect(constants.getByRole("option")).toHaveText(["PRESSURE_CELLS", "TREND_SAMPLES"]);
  await page.getByRole("option", { name: "TREND_SAMPLES", exact: true }).click();
  await expect(adding.getByRole("combobox", { name: "Dimension 1 of TrendB" })).toHaveValue(
    "TREND_SAMPLES",
  );

  // dimensions and volatile are both required for a value_block, and storage still needs naming
  // exactly once, as "a value block is declared with the shape it is given" states them.
  const volatile = adding.getByRole("combobox", { name: "Volatile of TrendB" });
  await volatile.fill("false");
  await volatile.press("Enter");
  const datatype = adding.getByRole("combobox", { name: "Datatype of TrendB" });
  await datatype.fill("uint16");
  await datatype.press("Enter");

  const apply = adding.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeVisible();
  await apply.click();
  await expect(page.getByRole("complementary", { name: "TrendB", exact: true })).toBeVisible();
  // A constant's name is written as the name, a string, not as the number it stands for.
  await expect
    .poll(() => readFileSync(join(vocabularyGui.directory, PUMP), "utf8"))
    .toContain('"dimensions": ["TREND_SAMPLES"]');
});

test("a key's apply the server fails on says so in its words, and nothing is written", async ({
  page,
  gui,
}) => {
  const controller = readFileSync(join(gui.directory, CONTROLLER));
  const hub = readFileSync(join(gui.directory, SENSOR_HUB));
  const panel = await openPanel(page, gui.address, "ValueA");
  await chooseUnit(page, "rpm");
  await expect(
    panel.getByText("Changes 2 files: controller.ddd.json, sensor_hub.ddd.json", { exact: true }),
  ).toBeVisible();
  // Registered once the plan is drawn: `/api/settle`, which draws it, goes through either way.
  const failed = await failing(page, "/api/edit", "http");
  const settle = panel.getByRole("region", { name: "Settle the key" });
  const apply = settle.getByRole("button", { name: "Apply to 2 files" });
  await expect(apply).toBeEnabled();
  await apply.click();

  // `VariablePanel` words this refusal itself, as `refusalOf` words the other panels'.
  await expect(settle.getByRole("status")).toHaveText(`The change was refused: ${SERVER_FAILED}`);
  // The panel withdraws its Apply until the reader chooses again (P19b-24); the choice stays.
  await expect(settle.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
  await expect(panel.getByRole("combobox", { name: "Unit of ValueA" })).toHaveValue("rpm");
  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(controller)).toBe(true);
  expect(readFileSync(join(gui.directory, SENSOR_HUB)).equals(hub)).toBe(true);
  // A POST is never sent again.
  expect(failed()).toBe(1);
});

test("a removal the server fails on says so in its words, and the declaration stays", async ({
  page,
  gui,
}) => {
  const controller = readFileSync(join(gui.directory, CONTROLLER));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  const row = page.getByRole("row", { name: "ValueB", exact: true });
  await expect(row).toBeVisible();
  await row.click();
  const removing = page
    .getByRole("complementary", { name: "ValueB", exact: true })
    .getByRole("region", { name: "Remove the declaration" });
  const remove = removing.getByRole("button", { name: "Remove from Controller" });
  await expect(remove).toBeEnabled();
  const failed = await failing(page, "/api/edit", "http");
  await remove.click();

  await expect(removing.getByRole("status")).toHaveText(`The change was refused: ${SERVER_FAILED}`);
  // The removal is withdrawn until the next revision or the reader's next choice (P19b-24), and
  // the declaration is still drawn.
  await expect(removing.getByRole("button", { name: "Remove from Controller" })).toHaveCount(0);
  await expect(page.getByRole("rowheader", { name: "ValueB", exact: true })).toBeVisible();
  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(controller)).toBe(true);
  expect(failed()).toBe(1);
});

test("a declaration the server fails on says so in its words, and nothing is declared", async ({
  page,
  gui,
}) => {
  const controller = readFileSync(join(gui.directory, CONTROLLER));
  await page.goto(gui.address);
  await page.getByRole("button", { name: "Controller", exact: true }).click();
  await page.getByRole("button", { name: "Add a declaration", exact: true }).click();
  const adding = page.getByRole("complementary", { name: "Add a declaration", exact: true });
  const name = adding.getByRole("combobox", { name: "Name" });
  await name.fill("ValueC");
  await name.press("Enter");
  await expect(adding.getByText("Reads ValueC as SensorHub declares it.")).toBeVisible();
  const apply = adding.getByRole("button", { name: "Apply to 1 file" });
  await expect(apply).toBeEnabled();
  const failed = await failing(page, "/api/edit", "http");
  await apply.click();

  // `refusalOf`, through the panel's `onError`.
  await expect(adding.getByRole("status")).toHaveText(`The change was refused: ${SERVER_FAILED}`);
  // Withdrawn until the next edit of the form (P19b-24); what was typed stays, and nothing was
  // declared, so no panel of ValueC opens.
  await expect(adding.getByRole("button", { name: /^Apply to/ })).toHaveCount(0);
  await expect(name).toHaveValue("ValueC");
  await expect(page.getByRole("complementary", { name: "ValueC", exact: true })).toHaveCount(0);
  expect(readFileSync(join(gui.directory, CONTROLLER)).equals(controller)).toBe(true);
  expect(failed()).toBe(1);
});
