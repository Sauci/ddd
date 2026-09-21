import { describe, expect, test } from "vitest";
import type { SettleReply, VariableKeyOffer, VariableReply } from "../api/types";
import {
  chooserSections,
  describeVariable,
  enteredValue,
  keyRows,
  labelOfRaw,
  limitsOf,
  limitsRaw,
  offerOf,
  shortValue,
  startingRaw,
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

  test("a value a type fixes names the type", () => {
    const of = variable([offer("unit", { values: [value('"rpm"', ["SensorHub"], true)] })]);
    const sensorHub = of.declarations[0];
    if (sensorHub === undefined) throw new Error("fixture must have a first declaration");
    of.declarations[0] = { ...sensorHub, type: "Speed_t", fixed: { unit: '"rpm"' } };
    expect(keyRows(of, null)[1]?.cells[0]).toMatchObject({ text: "rpm", from: "Speed_t" });
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
    };
    expect(willChangeKey(preview, controller, "unit")).toBe(true);
    expect(willChangeKey(preview, controller, "datatype")).toBe(false);
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
      variable([
        offer("unit", {
          editor: "unit",
          values: [value('"%"', ["SensorHub"], true), value('"rpm"', ["Controller"], false)],
        }),
      ]),
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
    const optional = chooserSections(variable([offer("unit", { editor: "unit" })]), "unit", "");
    expect(optional.some((section) => section.id === "nothing")).toBe(true);
    const required = chooserSections(
      variable([
        offer("volatile", {
          editor: "volatile",
          carried: [
            { allowed: true, required: true },
            { allowed: true, required: true },
          ],
        }),
      ]),
      "volatile",
      "",
    );
    expect(required.some((section) => section.id === "nothing")).toBe(false);
  });

  test("an editor that names things lists what the project has, what is in play left out", () => {
    const sections = chooserSections(
      variable([
        offer("axis", {
          editor: "name",
          choices: ["AxisA", "AxisB"],
          values: [value('"AxisA"', ["SensorHub"], true)],
        }),
      ]),
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
      chooserSections(variable([offer(key, { editor, choices })]), key, "").map((s) => s.title);
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
      variable([offer("conversion", { values: [value("{}", ["SensorHub"], true)] })]),
      "conversion",
      "",
    );
    expect(sections.map((section) => section.id)).toEqual(["declared", "nothing"]);
  });

  test("what is typed narrows the list, and a size may be typed outright", () => {
    const narrowed = chooserSections(
      variable([offer("size", { editor: "size", choices: ["CELLS", "ROWS"] })]),
      "size",
      "RO",
    );
    expect(narrowed.flatMap((section) => section.choices.map((c) => c.label))).toEqual(["ROWS"]);
    const typed = chooserSections(
      variable([offer("size", { editor: "size", choices: ["CELLS"] })]),
      "size",
      "12",
    );
    expect(typed[typed.length - 1]).toMatchObject({ id: "typed" });
    expect(typed[typed.length - 1]?.choices[0]?.raw).toBe("12");
  });

  test("a name that is no name of this project is not offered as typed", () => {
    const sections = chooserSections(
      variable([offer("axis", { editor: "name", choices: ["AxisA"] })]),
      "axis",
      "Wheel",
    );
    expect(sections.some((section) => section.id === "typed")).toBe(false);
  });
});

describe("what a field's text chooses", () => {
  test("an entry spelling the text exactly", () => {
    const of = variable([offer("datatype", { editor: "datatype", choices: ["uint8", "uint16"] })]);
    expect(enteredValue(chooserSections(of, "datatype", "uint16"), "datatype", "uint16")).toBe(
      '"uint16"',
    );
    // Unnarrowed, so the list still holds uint8 too: this one is found past an entry that
    // does not spell the text, not merely as the list's only choice.
    expect(enteredValue(chooserSections(of, "datatype", ""), "datatype", "uint16")).toBe(
      '"uint16"',
    );
  });

  test("state nothing, by the label the list gives it", () => {
    const of = variable([offer("unit", { editor: "unit" })]);
    expect(enteredValue(chooserSections(of, "unit", ""), "unit", "state nothing")).toBeNull();
  });

  test("a whole number for a size, and nothing at all for a field left empty", () => {
    const of = variable([offer("size", { editor: "size", choices: [] })]);
    expect(enteredValue(chooserSections(of, "size", "12"), "size", "12")).toBe("12");
    expect(enteredValue(chooserSections(of, "size", " "), "size", " ")).toBeUndefined();
  });

  test("a name this project does not declare chooses nothing", () => {
    const of = variable([offer("axis", { editor: "name", choices: ["AxisA"] })]);
    expect(enteredValue(chooserSections(of, "axis", "Wheel"), "axis", "Wheel")).toBeUndefined();
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
    expect(chooserSections(variable([offer("unit")]), "nonsense", "")).toEqual([]);
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
});
