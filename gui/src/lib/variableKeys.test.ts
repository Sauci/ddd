import { describe, expect, test } from "vitest";
import type { SettleReply, VariableKeyOffer, VariableReply } from "../api/types";
import {
  chooserNote,
  chooserSections,
  describeVariable,
  enteredValue,
  FRESH,
  heldFor,
  holdOn,
  keyColumns,
  keyRows,
  labelOfRaw,
  limitsNote,
  limitsOf,
  limitsRaw,
  offerOf,
  rangeChars,
  rangeDatatype,
  settledLabel,
  settledRaw,
  settleNote,
  shortValue,
  staleHold,
  startingRaw,
  typeDatatype,
  variableDatatype,
  willChangeKey,
} from "./variableKeys";

const SENSOR_HUB = "C:/work/demo/components/sensor_hub.ddd.json";
const CONTROLLER = "C:/work/demo/components/controller.ddd.json";

/** One key's offer, with everything it does not say left at its emptiest. */
function offer(key: string, fields: Partial<VariableKeyOffer> = {}): VariableKeyOffer {
  return {
    key,
    carried: [
      { allowed: true, required: false },
      { allowed: true, required: false },
    ],
    values: [],
    disagrees: false,
    editor: "none",
    choices: [],
    ...fields,
  };
}

function value(raw: string, components: string[], producer: boolean) {
  return { raw, components, producer };
}

/** ValueA produced by SensorHub and read by Controller, with the offers a test cares about. */
function variable(keys: VariableKeyOffer[], stated: Record<string, string>[] = []): VariableReply {
  return {
    revision: 7,
    name: "ValueA",
    declarations: [
      {
        path: SENSOR_HUB,
        pointer: "component.interface[2].definition",
        component: "SensorHub",
        role: "produces",
        stated: { kind: '"measurement"', ...stated[0] },
        type: null,
        fixed: {},
      },
      {
        path: CONTROLLER,
        pointer: "component.interface[0].definition",
        component: "Controller",
        role: "reads",
        stated: { kind: '"measurement"', ...stated[1] },
        type: null,
        fixed: {},
      },
    ],
    keys,
    findings: [],
  };
}

describe("the rows of the table", () => {
  test("kind comes first and opens nothing", () => {
    const rows = keyRows(variable([offer("unit")]), null);
    expect(rows[0]).toMatchObject({ key: "kind", disagrees: false, settleable: false });
    expect(rows[0]?.cells.map((cell) => cell.text)).toEqual(["measurement", "measurement"]);
  });

  test("declarations of two kinds are a row that says so", () => {
    const of = variable([offer("unit")], [{}, { kind: '"parameter"' }]);
    expect(keyRows(of, null)[0]?.disagrees).toBe(true);
  });

  test("what disagrees comes first, then what is stated, then the rest", () => {
    const rows = keyRows(
      variable(
        [
          offer("datatype", { values: [value('"uint8"', ["SensorHub", "Controller"], true)] }),
          offer("unit", { disagrees: true, values: [value('"%"', ["SensorHub"], true)] }),
          offer("limits"),
          offer("volatile", { values: [value("false", ["SensorHub", "Controller"], true)] }),
        ],
        [
          { datatype: '"uint8"', volatile: "false" },
          { datatype: '"uint8"', volatile: "false" },
        ],
      ),
      null,
    );
    expect(rows.map((row) => row.key)).toEqual(["kind", "unit", "datatype", "volatile", "limits"]);
  });

  test("a key no declaration's kind holds is not a row at all", () => {
    const rows = keyRows(
      variable([
        offer("size", {
          carried: [
            { allowed: false, required: false },
            { allowed: false, required: false },
          ],
        }),
      ]),
      null,
    );
    expect(rows.map((row) => row.key)).toEqual(["kind"]);
  });

  test("a cell whose kind cannot hold the key says so rather than sitting empty", () => {
    const rows = keyRows(
      variable(
        [
          offer("dimensions", {
            carried: [
              { allowed: true, required: false },
              { allowed: false, required: false },
            ],
            values: [value("[4]", ["SensorHub"], true)],
          }),
        ],
        [{}, { kind: '"parameter"' }],
      ),
      null,
    );
    expect(rows[1]?.cells[1]).toMatchObject({ text: "not on a parameter", quiet: true });
  });

  test("a declaration that states no kind reads none there too, kind row included", () => {
    const rows = keyRows(variable([offer("unit")], [{ kind: '""' }]), null);
    expect(rows[0]?.cells[0]).toMatchObject({ text: "none", quiet: true });
  });

  test("a cell whose own kind cannot be read still says it carries nothing", () => {
    const rows = keyRows(
      variable(
        [
          offer("dimensions", {
            carried: [
              { allowed: false, required: false },
              { allowed: true, required: false },
            ],
          }),
        ],
        [{ kind: '""' }],
      ),
      null,
    );
    expect(rows[1]?.cells[0]).toMatchObject({ text: "not on a declaration", quiet: true });
  });

  test("a cell of a declaration stating nothing reads none", () => {
    const rows = keyRows(
      variable([offer("unit", { values: [value('"%"', ["SensorHub"], true)] })], [{ unit: '"%"' }]),
      null,
    );
    expect(rows[1]?.cells.map((cell) => [cell.text, cell.quiet])).toEqual([
      ["%", false],
      ["none", true],
    ]);
  });

  test("a value a type fixes names the type, linked to its panel", () => {
    const of = variable([offer("unit", { values: [value('"rpm"', ["SensorHub"], true)] })]);
    const sensorHub = of.declarations[0];
    if (sensorHub === undefined) throw new Error("fixture must have a first declaration");
    of.declarations[0] = { ...sensorHub, type: "Speed_t", fixed: { unit: '"rpm"' } };
    expect(keyRows(of, null)[1]?.cells[0]).toMatchObject({
      text: "rpm",
      from: "Speed_t",
      href: "/project?view=types&type=Speed_t",
    });
  });

  test("a value stated outright carries no such link", () => {
    // SensorHub's own declaration states its unit directly and names no type - `from` and
    // `href` stay `null` together, the way `label` and `href` do in `FindingPanelView`.
    const of = variable(
      [offer("unit", { values: [value('"%"', ["SensorHub"], true)] })],
      [{ unit: '"%"' }],
    );
    expect(keyRows(of, null)[1]?.cells[0]).toMatchObject({ text: "%", from: null, href: null });
  });

  test("the declarations a preview writes into are marked on that key's row alone", () => {
    const preview: SettleReply = {
      revision: 7,
      changes: [
        {
          file: CONTROLLER,
          fingerprint: "abc",
          operations: [
            { op: "set", pointer: "component.interface[0].definition.unit", raw: '"%"' },
          ],
          hunks: [],
        },
      ],
      unloadable: [],
    };
    const rows = keyRows(variable([offer("unit"), offer("datatype")]), preview);
    expect(rows.find((row) => row.key === "unit")?.cells.map((cell) => cell.changing)).toEqual([
      false,
      true,
    ]);
    expect(rows.find((row) => row.key === "datatype")?.cells.map((cell) => cell.changing)).toEqual([
      false,
      false,
    ]);
  });

  test("willChangeKey reads a preview's own operations, one key at a time", () => {
    const controller = variable([offer("unit")]).declarations[1];
    if (controller === undefined) throw new Error("fixture must have a second declaration");
    const preview: SettleReply = {
      revision: 7,
      changes: [
        {
          file: CONTROLLER,
          fingerprint: "abc",
          operations: [
            { op: "set", pointer: "component.interface[0].definition.unit", raw: '"%"' },
          ],
          hunks: [],
        },
      ],
      unloadable: [],
    };
    expect(willChangeKey(preview, controller, "unit")).toBe(true);
    expect(willChangeKey(preview, controller, "datatype")).toBe(false);
  });
});

describe("a dimension's own entries, split so a name can link to its constant", () => {
  test("a literal number stays text; a name becomes a link to the Shared files tab", () => {
    const of = variable(
      [offer("dimensions", { values: [value('[3, "TREND_SAMPLES"]', ["SensorHub"], true)] })],
      [{ dimensions: '[3, "TREND_SAMPLES"]' }],
    );
    const cell = keyRows(of, null).find((row) => row.key === "dimensions")?.cells[0];
    expect(cell?.parts).toEqual([
      { text: "3", constant: null, href: null },
      {
        text: "TREND_SAMPLES",
        constant: "TREND_SAMPLES",
        href: "/project?view=shared&kind=constant&name=TREND_SAMPLES",
      },
    ]);
  });

  test("every other key carries no such split", () => {
    const of = variable(
      [offer("unit", { values: [value('"%"', ["SensorHub"], true)] })],
      [{ unit: '"%"' }],
    );
    expect(keyRows(of, null).find((row) => row.key === "unit")?.cells[0]).toMatchObject({
      parts: null,
    });
  });

  test("a value that is not a json array is not split - the text alone still shows it", () => {
    const of = variable(
      [offer("dimensions", { values: [value("4", ["SensorHub"], true)] })],
      [{ dimensions: "4" }],
    );
    expect(keyRows(of, null).find((row) => row.key === "dimensions")?.cells[0]).toMatchObject({
      text: "4",
      parts: null,
    });
  });

  test("a value that is not json at all is not split either", () => {
    const of = variable(
      [offer("dimensions", { values: [value("[", ["SensorHub"], true)] })],
      [{ dimensions: "[" }],
    );
    expect(keyRows(of, null).find((row) => row.key === "dimensions")?.cells[0]).toMatchObject({
      text: "[",
      parts: null,
    });
  });
});

describe("the columns of the table", () => {
  /** ValueA as a project that lists Controller before SensorHub answers it: the reader first,
   * the producer second, which is the order every other reader of the api is given. */
  function readerFirst(keys: VariableKeyOffer[]): VariableReply {
    return {
      revision: 7,
      name: "ValueA",
      declarations: [
        {
          path: CONTROLLER,
          pointer: "component.interface[0].definition",
          component: "Controller",
          role: "reads",
          stated: { kind: '"parameter"', unit: '"rpm"' },
          type: null,
          fixed: {},
        },
        {
          path: SENSOR_HUB,
          pointer: "component.interface[2].definition",
          component: "SensorHub",
          role: "produces",
          stated: { kind: '"measurement"', unit: '"%"', dimensions: "[4]" },
          type: null,
          fixed: {},
        },
      ],
      keys,
      findings: [],
    };
  }

  test("the producer comes first, and the rest keep the answer's order", () => {
    const columns = keyColumns(
      readerFirst([offer("unit", { values: [value('"%"', ["SensorHub"], true)] })]),
    );
    expect(columns.map((column) => [column.declaration.component, column.at])).toEqual([
      ["SensorHub", 1],
      ["Controller", 0],
    ]);
  });

  test("every row's cells follow that order, carried read where the answer put it", () => {
    const rows = keyRows(
      readerFirst([
        offer("unit", { values: [value('"%"', ["SensorHub"], true)] }),
        offer("dimensions", {
          // Controller's parameter carries no dimensions; it is the answer's first
          // declaration and the table's second, and the cell has to follow the declaration.
          carried: [
            { allowed: false, required: false },
            { allowed: true, required: false },
          ],
          values: [value("[4]", ["SensorHub"], true)],
        }),
      ]),
      null,
    );
    expect(rows[0]?.cells.map((cell) => cell.text)).toEqual(["measurement", "parameter"]);
    const textOfRow = (key: string) =>
      rows.find((row) => row.key === key)?.cells.map((cell) => cell.text);
    expect(textOfRow("unit")).toEqual(["%", "rpm"]);
    expect(textOfRow("dimensions")).toEqual(["4", "not on a parameter"]);
  });

  test("a variable no declaration produces is drawn in the answer's own order", () => {
    const of = readerFirst([offer("unit")]);
    const producer = of.declarations[1];
    if (producer === undefined) throw new Error("fixture must have a second declaration");
    of.declarations[1] = { ...producer, role: "reads" };
    expect(keyColumns(of).map((column) => column.declaration.component)).toEqual([
      "Controller",
      "SensorHub",
    ]);
  });
});

describe("a value as a reader reads it", () => {
  test.each([
    ["unit", '"%"', "%"],
    ["volatile", "true", "true"],
    ["size", "4", "4"],
    ["size", '"CELLS"', "CELLS"],
    ["dimensions", "[3, 4]", "3 × 4"],
    ["limits", '{ "min": 0, "max": 100 }', "0 … 100"],
    ["limits", '{ "max": 100 }', "? … 100"],
    ["conversion", '{ "kind": "identity" }', "identity"],
    ["conversion", "{}", "identity"],
    ["conversion", '{ "factor": 0.5 }', "linear ×0.5"],
    ["conversion", '{ "kind": "linear", "factor": 0.5, "offset": 2 }', "linear ×0.5 +2"],
    ["conversion", '{ "kind": "linear", "factor": 1, "offset": -2 }', "linear ×1 -2"],
    ["conversion", '{ "kind": "linear", "offset": 5 }', "linear ×1 +5"],
    ["conversion", '{ "name": "Gear_e", "enumerators": [] }', "enum Gear_e"],
    ["conversion", '{ "enumerators": [{ "name": "OFF", "value": 0 }] }', "enum, 1 enumerator"],
    ["conversion", '{ "kind": "enum" }', "enum, 0 enumerators"],
    ["conversion", '{ "kind": "string" }', "string"],
    ["unit", "{", "{"],
    ["unit", "null", "null"],
    ["axis", '{  "a":  1  }', '{ "a": 1 }'],
  ])("%s %s reads %s", (key, raw, reads) => {
    expect(shortValue(key, raw)).toBe(reads);
  });
});

describe("the panel's line under the name", () => {
  test("it says what the variable is, who owns it and what disagrees", () => {
    const of = variable(
      [offer("unit", { disagrees: true }), offer("datatype", { disagrees: true })],
      [{ datatype: '"uint8"' }, {}],
    );
    expect(describeVariable(of)).toBe(
      "measurement · uint8 · produced by SensorHub · 2 declarations · 2 keys disagree",
    );
  });

  test("one disagreement is one key, and none is said plainly", () => {
    const one = variable([offer("unit", { disagrees: true })], [{ datatype: '"uint8"' }]);
    expect(describeVariable(one)).toContain("1 key disagrees");
    const agreed = variable([offer("unit")], [{ datatype: '"uint8"' }]);
    expect(describeVariable(agreed)).toContain("2 declarations · all agreed");
  });

  test("two kinds disagreeing is a key too, though kind is not one of variable.keys", () => {
    const twoKinds = variable(
      [offer("unit")],
      [{ kind: '"measurement"' }, { kind: '"parameter"' }],
    );
    expect(describeVariable(twoKinds)).toContain("1 key disagrees");
  });

  test("no declarations at all names nothing", () => {
    expect(
      describeVariable({ revision: 1, name: "Nothing", declarations: [], keys: [], findings: [] }),
    ).toBe("");
  });

  test("a variable local to its only declaration, with nothing else stated, names what it can", () => {
    const solo = describeVariable({
      revision: 1,
      name: "Solo",
      declarations: [
        {
          path: SENSOR_HUB,
          pointer: "component.interface[0].definition",
          component: "SensorHub",
          role: "local",
          stated: { kind: '""' },
          type: null,
          fixed: {},
        },
      ],
      keys: [],
      findings: [],
    });
    expect(solo).toBe(
      "declaration · no datatype · local to SensorHub · 1 declaration · all agreed",
    );
  });

  test("a variable no declaration produces says so", () => {
    const orphan = describeVariable({
      revision: 1,
      name: "Orphan",
      declarations: [
        {
          path: SENSOR_HUB,
          pointer: "component.interface[0].definition",
          component: "SensorHub",
          role: "reads",
          stated: { kind: '"measurement"' },
          type: null,
          fixed: {},
        },
        {
          path: CONTROLLER,
          pointer: "component.interface[0].definition",
          component: "Controller",
          role: "reads",
          stated: { kind: '"measurement"' },
          type: null,
          fixed: {},
        },
      ],
      keys: [],
      findings: [],
    });
    expect(orphan).toContain("no producer");
  });
});

describe("what a key's chooser lists", () => {
  test("the values in play come first, the producer's marked", () => {
    const sections = chooserSections(
      offer("unit", {
        editor: "unit",
        values: [value('"%"', ["SensorHub"], true), value('"rpm"', ["Controller"], false)],
      }),
      "ValueA",
      "unit",
      "",
    );
    expect(sections[0]?.title).toBe("Declared for ValueA");
    expect(sections[0]?.choices.map((choice) => [choice.label, choice.detail])).toEqual([
      ["%", "SensorHub · the producer"],
      ["rpm", "Controller"],
    ]);
  });

  test("state nothing is offered unless a declaration requires the key", () => {
    const optional = chooserSections(offer("unit", { editor: "unit" }), "ValueA", "unit", "");
    expect(optional.some((section) => section.id === "nothing")).toBe(true);
    const required = chooserSections(
      offer("volatile", {
        editor: "volatile",
        carried: [
          { allowed: true, required: true },
          { allowed: true, required: true },
        ],
      }),
      "ValueA",
      "volatile",
      "",
    );
    expect(required.some((section) => section.id === "nothing")).toBe(false);
  });

  test("an editor that names things lists what the project has, what is in play left out", () => {
    const sections = chooserSections(
      offer("axis", {
        editor: "name",
        choices: ["AxisA", "AxisB"],
        values: [value('"AxisA"', ["SensorHub"], true)],
      }),
      "ValueA",
      "axis",
      "",
    );
    expect(sections.map((section) => [section.title, section.choices.map((c) => c.label)])).toEqual(
      [
        ["Declared for ValueA", ["AxisA"]],
        ["This project's axes", ["AxisB"]],
        ["State nothing", ["state nothing"]],
      ],
    );
  });

  test("each naming editor says what it is naming", () => {
    const titles = (key: string, editor: VariableKeyOffer["editor"], choices: string[]) =>
      chooserSections(offer(key, { editor, choices }), "ValueA", key, "").map((s) => s.title);
    // Nothing is in play in any of these, so "Declared for ValueA" has nothing to list and is
    // left out (spec 5.2's "nothing else"): the naming section itself is the first to survive.
    expect(titles("input", "name", ["ValueE"])[0]).toBe("This project's measurements");
    expect(titles("typename", "typename", ["Speed_t"])[0]).toBe("This project's types");
    expect(titles("datatype", "datatype", ["uint8"])[0]).toBe("Datatypes");
    expect(titles("size", "size", ["CELLS"])[0]).toBe("This project's constants");
    expect(titles("volatile", "volatile", [])[0]).toBe("True or false");
  });

  test("a conversion offers what is in play and nothing else", () => {
    const sections = chooserSections(
      offer("conversion", { values: [value("{}", ["SensorHub"], true)] }),
      "ValueA",
      "conversion",
      "",
    );
    expect(sections.map((section) => section.id)).toEqual(["declared", "nothing"]);
  });

  test("what is typed narrows the list, and a size may be typed outright", () => {
    const narrowed = chooserSections(
      offer("size", { editor: "size", choices: ["CELLS", "ROWS"] }),
      "ValueA",
      "size",
      "RO",
    );
    expect(narrowed.flatMap((section) => section.choices.map((c) => c.label))).toEqual(["ROWS"]);
    const typed = chooserSections(
      offer("size", { editor: "size", choices: ["CELLS"] }),
      "ValueA",
      "size",
      "12",
    );
    expect(typed[typed.length - 1]).toMatchObject({ id: "typed" });
    expect(typed[typed.length - 1]?.choices[0]?.raw).toBe("12");
  });

  test("a name that is no name of this project is not offered as typed", () => {
    const sections = chooserSections(
      offer("axis", { editor: "name", choices: ["AxisA"] }),
      "ValueA",
      "axis",
      "Wheel",
    );
    expect(sections.some((section) => section.id === "typed")).toBe(false);
  });
});

describe("what a field's text chooses", () => {
  test("an entry spelling the text exactly", () => {
    const of = offer("datatype", { editor: "datatype", choices: ["uint8", "uint16"] });
    expect(
      enteredValue(chooserSections(of, "ValueA", "datatype", "uint16"), "datatype", "uint16"),
    ).toBe('"uint16"');
    // Unnarrowed, so the list still holds uint8 too: this one is found past an entry that
    // does not spell the text, not merely as the list's only choice.
    expect(enteredValue(chooserSections(of, "ValueA", "datatype", ""), "datatype", "uint16")).toBe(
      '"uint16"',
    );
  });

  test("state nothing, by the label the list gives it", () => {
    const of = offer("unit", { editor: "unit" });
    expect(
      enteredValue(chooserSections(of, "ValueA", "unit", ""), "unit", "state nothing"),
    ).toBeNull();
  });

  test("a whole number for a size, and nothing at all for a field left empty", () => {
    const of = offer("size", { editor: "size", choices: [] });
    expect(enteredValue(chooserSections(of, "ValueA", "size", "12"), "size", "12")).toBe("12");
    expect(enteredValue(chooserSections(of, "ValueA", "size", " "), "size", " ")).toBeUndefined();
  });

  test("a name this project does not declare chooses nothing", () => {
    const of = offer("axis", { editor: "name", choices: ["AxisA"] });
    expect(
      enteredValue(chooserSections(of, "ValueA", "axis", "Wheel"), "axis", "Wheel"),
    ).toBeUndefined();
  });
  test.each([
    // A size typed is read as every field reads a number: in any decimal spelling of a whole
    // number of at least 1, and travelling in its own digits.
    { text: "12", raw: "12" },
    { text: " 12 ", raw: "12" },
    { text: "012", raw: "12" },
    { text: "+12", raw: "12" },
    { text: "1e1", raw: "10" },
    { text: "12.0", raw: "12" },
    { text: "1,234,567", raw: "1234567" },
    // Nothing else is one.
    { text: "0", raw: undefined },
    { text: "-3", raw: undefined },
    { text: "2.5", raw: undefined },
    { text: "0x10", raw: undefined },
    { text: "1,500", raw: undefined },
  ])("a size typed '$text' chooses $raw", ({ text, raw }) => {
    const of = offer("size", { editor: "size", choices: [] });
    expect(enteredValue(chooserSections(of, "ValueA", "size", text), "size", text)).toBe(raw);
  });
});

describe("chooserNote", () => {
  const SIZE = offer("size", { editor: "size", choices: ["CELLS"] });

  test("a size in another notation is refused in the sentence every field refuses it with", () => {
    // 15:M13: `Number` read `0x10` as 16, and the panel offered it as the size typed.
    const sections = chooserSections(SIZE, "ValueA", "size", "0x10");
    expect(sections.some((section) => section.id === "typed")).toBe(false);
    expect(chooserNote(true, "size", "0x10", sections)).toBe(
      "'0x10' is not a number in decimal notation",
    );
    expect(
      chooserNote(true, "size", "1,500", chooserSections(SIZE, "ValueA", "size", "1,500")),
    ).toBe("the comma in '1,500' could be a decimal point or a thousands separator");
  });

  test("a name, or a number that reads, gets the way out of the text", () => {
    expect(chooserNote(true, "size", "ROWS", chooserSections(SIZE, "ValueA", "size", "ROWS"))).toBe(
      "Nothing in the list matches what you typed: change it, or press Escape to put the value back.",
    );
    expect(chooserNote(true, "size", "12", chooserSections(SIZE, "ValueA", "size", "12"))).toBe(
      "Press Enter to take what you typed, or pick it from the list.",
    );
    // `Infinity` may name a constant, so it is a name here and not a number in another notation.
    expect(
      chooserNote(true, "size", "Infinity", chooserSections(SIZE, "ValueA", "size", "Infinity")),
    ).toBe(
      "Nothing in the list matches what you typed: change it, or press Escape to put the value back.",
    );
  });

  test("another key's text gets the way out of it, whatever it spells", () => {
    const of = offer("axis", { editor: "name", choices: ["AxisA"] });
    expect(chooserNote(true, "axis", "0x10", chooserSections(of, "ValueA", "axis", "0x10"))).toBe(
      "Nothing in the list matches what you typed: change it, or press Escape to put the value back.",
    );
  });

  test("nothing while the text is the value settled on", () => {
    expect(chooserNote(false, "size", "0x10", [])).toBeUndefined();
  });
});

describe("the value a chooser starts on", () => {
  test("the producer's, which is the first in play", () => {
    const of = variable([
      offer("unit", {
        values: [value('"%"', ["SensorHub"], true), value('"rpm"', ["Controller"], false)],
      }),
    ]);
    expect(startingRaw(of, "unit")).toBe('"%"');
    expect(labelOfRaw(of, "unit", startingRaw(of, "unit"))).toBe("%");
  });

  test("nothing in play starts on nothing, which the field says in words", () => {
    const of = variable([offer("unit")]);
    expect(startingRaw(of, "unit")).toBeNull();
    expect(labelOfRaw(of, "unit", null)).toBe("state nothing");
  });

  test("a key the answer does not carry offers nothing", () => {
    expect(offerOf(variable([offer("unit")]), "nonsense")).toBeUndefined();
    expect(startingRaw(variable([offer("unit")]), "nonsense")).toBeNull();
    // chooserSections no longer looks a key up itself (Task 6): it now takes the offer
    // directly, and a caller that finds none from offerOf - covered above - does not call it.
  });
});

describe("what a panel holds for one key", () => {
  test("a choice is read back only while its key is the one on screen", () => {
    const held = holdOn(undefined, "datatype", { chosen: "uint16" });
    expect(heldFor(held, "datatype").chosen).toBe("uint16");
    expect(heldFor(held, "unit")).toBe(FRESH);
    expect(heldFor(held, undefined)).toBe(FRESH);
    expect(heldFor(undefined, "unit")).toBe(FRESH);
  });

  test("a pick of nothing is held, and is not nothing held", () => {
    expect(heldFor(holdOn(undefined, "unit", { chosen: null }), "unit").chosen).toBeNull();
  });

  test("a patch is laid over what is held for the key, and over nothing for another's", () => {
    const first = holdOn(undefined, "limits", { range: { min: "0", max: "5", typed: true } });
    const second = holdOn(first, "limits", { changesShown: true });
    expect(heldFor(second, "limits")).toEqual({
      ...FRESH,
      range: { min: "0", max: "5", typed: true },
      changesShown: true,
    });
    expect(heldFor(holdOn(first, "unit", { typed: "rp" }), "unit")).toEqual({
      ...FRESH,
      typed: "rp",
    });
  });

  test("nothing is held for no key", () => {
    expect(holdOn(undefined, undefined, { chosen: "rpm" })).toBeUndefined();
  });

  test("what was made for another key, or for none, is stale; nothing held is not", () => {
    const held = holdOn(undefined, "datatype", { chosen: "uint16" });
    expect(staleHold(held, "datatype")).toBe(false);
    expect(staleHold(held, "unit")).toBe(true);
    expect(staleHold(held, undefined)).toBe(true);
    expect(staleHold(undefined, "unit")).toBe(false);
  });
});

describe("the value a chooser settles on", () => {
  test("the value it starts on, until the reader picks one", () => {
    expect(settledRaw(undefined, '"%"')).toBe('"%"');
    expect(settledRaw(undefined, null)).toBeNull();
  });

  test("the value picked, once there is one", () => {
    expect(settledRaw('"rpm"', '"%"')).toBe('"rpm"');
    expect(settledRaw('"rpm"', null)).toBe('"rpm"');
  });

  test("a pick of nothing is a pick, and stays nothing", () => {
    // `chosen ?? starting` read it as no pick at all: a type stating degC, asked for no unit,
    // went on stating degC - the field going back to it, and Apply leaving it in the file.
    expect(settledRaw(null, '"degC"')).toBeNull();
    expect(settledRaw(null, null)).toBeNull();
  });
});

describe("a range typed into two fields", () => {
  test("it travels as one object, and an empty field is no range at all", () => {
    expect(limitsRaw("0", "100")).toBe('{ "min": 0, "max": 100 }');
    expect(limitsRaw("-2.5", "2.5")).toBe('{ "min": -2.5, "max": 2.5 }');
    expect(limitsRaw("", "100")).toBeNull();
    expect(limitsRaw("low", "100")).toBeNull();
  });

  test("the fields read what is stated, and nothing where nothing is", () => {
    expect(limitsOf('{ "min": 0, "max": 100 }')).toEqual({ min: "0", max: "100" });
    expect(limitsOf(null)).toEqual({ min: "", max: "" });
    expect(limitsOf("{")).toEqual({ min: "", max: "" });
    expect(limitsOf("null")).toEqual({ min: "", max: "" });
  });

  test("a maximum below the minimum is no range at all", () => {
    // Limits refuses it, so every file it was written into would stop loading: it never
    // becomes a value to settle on, and the chooser says why instead.
    expect(limitsRaw("100", "0")).toBeNull();
    expect(limitsNote("100", "0")).toBe("The maximum is below the minimum");
    // The two bounds may be the same number, which Limits allows.
    expect(limitsRaw("5", "5")).toBe('{ "min": 5, "max": 5 }');
    expect(limitsNote("5", "5")).toBeNull();
  });

  test("two empty fields state nothing, and anything half typed is nothing to apply", () => {
    expect(limitsNote("", "")).toBeNull();
    expect(limitsNote(" ", " ")).toBeNull();
    expect(limitsNote("0", "100")).toBeNull();
  });

  test.each([
    // 15:M9: each sentence names the one field it is about, where one sentence spoke of both
    // fields whichever of them was wrong, even of one holding a comma locale's decimal.
    { min: "0", max: "", says: "Max is empty" },
    { min: "", max: "100", says: "Min is empty" },
    { min: " ", max: "100", says: "Min is empty" },
    { min: "low", max: "100", says: "Min: 'low' is not a number" },
    { min: "0", max: "high", says: "Max: 'high' is not a number" },
    { min: "0x10", max: "100", says: "Min: '0x10' is not a number in decimal notation" },
    { min: "0", max: "Infinity", says: "Max: 'Infinity' is not a number in decimal notation" },
    {
      min: "0",
      max: "1,500",
      says: "Max: the comma in '1,500' could be a decimal point or a thousands separator",
    },
  ])("'$min' and '$max' say: $says", ({ min, max, says }) => {
    expect(limitsNote(min, max)).toBe(says);
    expect(limitsRaw(min, max)).toBeNull();
  });

  test("a range is read by the one rule for a comma, the two fields together", () => {
    expect(limitsNote("1,5", "2")).toBeNull();
    expect(limitsRaw("1,5", "2,5")).toBe('{ "min": 1.5, "max": 2.5 }');
    // `0,5` says what the comma is, so `1,500` beside it is one and a half.
    expect(limitsRaw("0,5", "1,500")).toBe('{ "min": 0.5, "max": 1.5 }');
    expect(limitsRaw("1,234.5", "1.234.567,5")).toBe('{ "min": 1234.5, "max": 1234567.5 }');
    // Fix round 1, M1: and `1,234,567` says its commas group thousands, so `1,500` is fifteen
    // hundred, where the field was refused for a comma that could be either.
    expect(limitsRaw("1,500", "1,234,567")).toBe('{ "min": 1500, "max": 1234567 }');
  });

  test("a range is spelled as the numbers it holds, whatever their spelling", () => {
    expect(limitsRaw("+1", "1e3")).toBe('{ "min": 1, "max": 1000 }');
    expect(limitsRaw(".5", "5.")).toBe('{ "min": 0.5, "max": 5 }');
  });
});

describe("a range read by its datatype, as a cell of it reads a number (task 1's n3)", () => {
  const INEXACT = "where the page cannot hold every whole number exactly";

  test("a whole datatype's bound past 2^53 is refused in any spelling, an exponent's too", () => {
    expect(limitsNote("0", "1e19", "uint64")).toBe(`Max: '1e19' is past 2^53, ${INEXACT}`);
    expect(limitsNote("-9.1e15", "0", "sint64")).toBe(`Min: '-9.1e15' is past -2^53, ${INEXACT}`);
    // No datatype stated reads as a whole one's, the stricter.
    expect(limitsNote("0", "1e19")).toBe(`Max: '1e19' is past 2^53, ${INEXACT}`);
  });

  test("and so is a bound the double would send as another number, a fraction from 2^51 on", () => {
    expect(limitsNote("2251799813685248.25", "2251799813685249", "uint64")).toBe(
      "Min: '2251799813685248.25' has a fraction the page cannot hold exactly",
    );
    expect(limitsNote("0", "2251799813685248.3", "uint64")).toBe(
      "Max: '2251799813685248.3' has a fraction the page cannot hold exactly",
    );
    expect(limitsNote("0", "0.1", "uint8")).toBeNull();
  });

  test("a float's bound is the double it is, digits past 2^53 among them", () => {
    expect(limitsNote("0", "10000000000000000000", "float64")).toBeNull();
    expect(limitsNote("0", "1e400", "float64")).toBe("Max: '1e400' is past what a float64 holds");
    expect(limitsNote("1e-400", "1", "float32")).toBe("Min: '1e-400' rounds to zero in float32");
    // Fix round 1, M2: an exponent past 1e21 in size made the double NaN, said to be past it.
    expect(limitsNote("1e-1000000000000000000000", "1", "float32")).toBe(
      "Min: '1e-1000000000000000000000' rounds to zero in float32",
    );
    expect(limitsNote("0", "1e-1000000000000000000000", "uint8")).toBe(
      "Max: '1e-1000000000000000000000' has a fraction the page cannot hold exactly",
    );
  });

  test("a float's bound is written as a float (task 1's n2), any other's as typed", () => {
    // 1e19 was written 10000000000000000000, a whole number past 2^53.
    expect(limitsRaw("0", "1e19", "float64")).toBe('{ "min": 0.0, "max": 10000000000000000000.0 }');
    expect(limitsRaw("-50", "90", "float32")).toBe('{ "min": -50.0, "max": 90.0 }');
    expect(limitsRaw("0.5", "1e21", "float64")).toBe('{ "min": 0.5, "max": 1e+21 }');
    expect(limitsRaw("-50", "90", "sint16")).toBe('{ "min": -50, "max": 90 }');
  });
});

describe("the datatype a range is read by", () => {
  test("a whole one where any declaration states one, else a float, else a whole one's rule", () => {
    expect(rangeDatatype(["float32", "uint8"])).toBe("uint8");
    expect(rangeDatatype(["float32", "float64"])).toBe("float32");
    expect(rangeDatatype([null, "float64"])).toBe("float64");
    expect(rangeDatatype([null, null])).toBe("");
    expect(rangeDatatype([])).toBe("");
  });

  test("a variable's, from what each declaration states or its type fixes", () => {
    const floats = variable([], [{ datatype: '"float32"' }, {}]);
    expect(variableDatatype(floats)).toBe("float32");
    const fixed = variable([]);
    const declarations = fixed.declarations.map((declaration) => ({
      ...declaration,
      fixed: { datatype: '"uint16"' },
    }));
    expect(variableDatatype({ ...fixed, declarations })).toBe("uint16");
  });

  test("a type's, the one it fixes", () => {
    expect(
      typeDatatype([offer("unit"), offer("datatype", { values: [value('"float64"', [], false)] })]),
    ).toBe("float64");
    expect(typeDatatype([offer("unit")])).toBe("");
  });
});

describe("a limit a double cannot hold", () => {
  // A uint64's limits as its file states them, read off `GET /api/variable` for a declaration
  // whose maximum is the most a uint64 holds. `JSON.parse` reads 18446744073709551615 as
  // 18446744073709551616: the Max field was filled with 18446744073709552000, a number no uint64
  // holds, and an edit of Min alone sent it back - a file that would not load, over a bound
  // nobody typed.
  const STATED = '{\n            "min": 0,\n            "max": 18446744073709551615\n          }';
  const INEXACT = "where the page cannot hold every whole number exactly";

  test("the field shows the file's own digits, not the double they read as", () => {
    expect(limitsOf(STATED)).toEqual({ min: "0", max: "18446744073709551615" });
  });

  test("and so do the key's row and its chooser", () => {
    expect(shortValue("limits", STATED)).toBe("0 … 18446744073709551615");
  });

  test("each field is as wide as its own text, so the twenty digits read whole", () => {
    // Both fields were 6em wide, whatever they held: Max read 1844674 of its twenty digits.
    expect(rangeChars(limitsOf(STATED))).toEqual({ min: 1, max: 20 });
    expect(rangeChars({ min: "-9223372036854775808", max: "" })).toEqual({ min: 20, max: 0 });
  });

  test("on either side", () => {
    const signed = '{ "min": -9223372036854775808, "max": 0 }';
    expect(limitsOf(signed)).toEqual({ min: "-9223372036854775808", max: "0" });
  });

  test("a bound whose own text is not found is the double read", () => {
    // `JSON.parse` reads a key spelled with an escape, which no file of the page's writes; its
    // bound is then shown as the double it reads, as every bound was.
    expect(limitsOf('{ "min": 0, "m\\u0061x": 100 }')).toEqual({ min: "0", max: "100" });
  });

  test("a range holding one says why it cannot be applied, in the grid's words", () => {
    expect(limitsNote("1", "18446744073709551615")).toBe(
      `Max: '18446744073709551615' is past 2^53, ${INEXACT}`,
    );
    expect(limitsRaw("1", "18446744073709551615")).toBeNull();
  });

  test("so does one typed past 2^53, either side", () => {
    expect(limitsNote("-9007199254740993", "0")).toBe(
      `Min: '-9007199254740993' is past -2^53, ${INEXACT}`,
    );
    expect(limitsRaw("0", "9007199254740993")).toBeNull();
  });

  test("the 64 bit mask in hexadecimal stays refused, as a number in another notation", () => {
    // Ruling B3-1: refused past 2^53 once; refused now before it is weighed, as every field
    // refuses a spelling `Number` read and decimal notation does not.
    expect(limitsNote("0", "0x8000000000000001")).toBe(
      "Max: '0x8000000000000001' is not a number in decimal notation",
    );
    expect(limitsRaw("0", "0x8000000000000001")).toBeNull();
  });

  test("up to 2^53 a bound is written as it is typed", () => {
    expect(limitsRaw("-9007199254740992", "9007199254740991")).toBe(
      '{ "min": -9007199254740992, "max": 9007199254740991 }',
    );
    expect(limitsNote("-9007199254740992", "9007199254740991")).toBeNull();
  });

  test("a float's bound past 2^53, spelled as a float, is the double it is", () => {
    // FLT_MAX is a whole number past 2^53 too; a limit spelled with an exponent is read, and
    // written, as the double it spells, which a float holds as it is.
    const range = '{ "min": -3.4028234663852886e+38, "max": 3.4028234663852886e+38 }';
    expect(limitsOf(range)).toEqual({
      min: "-3.4028234663852886e+38",
      max: "3.4028234663852886e+38",
    });
    expect(limitsNote("-3.4028234663852886e38", "3.4028234663852886e38", "float32")).toBeNull();
  });
});

describe("settledLabel (fix round 1, M8)", () => {
  // What a chooser's field reads while nothing is typed: one rule for the variable's panel and the
  // type's, where each spelled it out for itself, outside the Vitest gate.
  const label = (key: string, raw: string | null) => `${key}=${raw ?? "nothing"}`;

  test("a range the fields do not make reads as nothing, the fields showing it themselves", () => {
    expect(settledLabel("limits", "Max is empty", null, null, label)).toBe("");
  });

  test("a range they make reads as it, from what it comes to", () => {
    expect(settledLabel("limits", null, '{ "min": 0, "max": 5 }', null, label)).toBe(
      'limits={ "min": 0, "max": 5 }',
    );
  });

  test("a unit refused reads as the spelling chosen, the note under it saying why", () => {
    expect(settledLabel("unit", "'V ' has spaces around it", null, '"V "', label)).toBe(
      'unit="V "',
    );
    expect(settledLabel("unit", null, '"V"', '"V"', label)).toBe('unit="V"');
  });

  test("no key selected reads as nothing", () => {
    expect(settledLabel(undefined, null, null, null, label)).toBe("");
  });
});

describe("settleNote", () => {
  const EMPTY = { min: "", max: "" };

  test("a range the two fields do not make, read by the datatype", () => {
    expect(settleNote("limits", { min: "0", max: "" }, "", null)).toBe("Max is empty");
    expect(settleNote("limits", { min: "0", max: "1e19" }, "float64", null)).toBeNull();
  });

  test("a unit with spaces around it, in the Units tab's words (15:M10)", () => {
    expect(settleNote("unit", EMPTY, "", '"V "')).toBe("'V ' has spaces around it");
    expect(settleNote("unit", EMPTY, "", '"V"')).toBeNull();
    expect(settleNote("unit", EMPTY, "", null)).toBeNull();
  });

  test("nothing for any other key, nor for none", () => {
    expect(settleNote("datatype", EMPTY, "", '" uint8"')).toBeNull();
    expect(settleNote(undefined, EMPTY, "", null)).toBeNull();
  });
});
