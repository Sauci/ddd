import { readFileSync } from "node:fs";
import { join } from "node:path";
import { CONTROLLER } from "./demo";
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
