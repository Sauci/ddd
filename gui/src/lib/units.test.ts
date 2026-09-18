import { expect, describe as group, test } from "vitest";
import type { SettleReply, UnitsReply, VariableDeclaration } from "../api/types";
import {
  baseName,
  consequence,
  describe,
  editOf,
  hunkLines,
  outsideVocabulary,
  pickerSections,
  rawOf,
  startingUnit,
  textOf,
  unitOfDeclaration,
  willChange,
} from "./units";

const HUB = "C:/w/components/sensor_hub.ddd.json";
const CONTROLLER = "C:/w/components/controller.ddd.json";
const UI = "C:/w/components/user_interface.ddd.json";
const PATHS: Record<string, string> = { SensorHub: HUB, Controller: CONTROLLER, UserInterface: UI };
const AT = "component.interface[0].definition";

function declared(
  component: string,
  role: VariableDeclaration["role"],
  unit: string | null,
  extra: Partial<VariableDeclaration> = {},
): VariableDeclaration {
  const path = PATHS[component] ?? CONTROLLER;
  return {
    path,
    pointer: AT,
    component,
    role,
    stated: {
      kind: '"measurement"',
      datatype: '"uint8"',
      ...(unit === null ? {} : { unit: JSON.stringify(unit) }),
    },
    type: null,
    fixed: {},
    ...extra,
  };
}

const VALUE_A = [
  declared("Controller", "reads", "rpm"),
  declared("SensorHub", "produces", "%"),
  declared("UserInterface", "reads", "%"),
];
const FREE: UnitsReply = {
  revision: 1,
  vocabulary: null,
  used: [
    { unit: "Hz", variables: 4 },
    { unit: "%", variables: 3 },
    { unit: "rpm", variables: 1 },
  ],
};
const VOCABULARY: UnitsReply = {
  revision: 1,
  vocabulary: [
    { unit: "rpm", description: "rotational speed" },
    { unit: "Nm", description: null },
  ],
  used: [{ unit: "rpm", variables: 1 }],
};
const ONE_FILE: SettleReply = {
  revision: 1,
  changes: [
    {
      file: CONTROLLER,
      fingerprint: "f",
      operations: [{ op: "set", pointer: `${AT}.unit`, raw: '"%"' }],
      hunks: [{ line: 14, before: ['  "unit": "rpm",'], after: ['  "unit": "%",'] }],
    },
  ],
};
const ONE_FILE_CHANGE = ONE_FILE.changes[0];
if (ONE_FILE_CHANGE === undefined) throw new Error("ONE_FILE must have one change");

group("reading what a declaration states", () => {
  test.each([
    [undefined, null],
    ['"rpm"', "rpm"],
    ['""', null],
    ["3", null],
    ["not json", null],
  ])("the json text %s reads as %s", (raw, text) => {
    expect(textOf(raw)).toBe(text);
  });

  test("a unit is the one stated, or the one the declared type fixes", () => {
    expect(unitOfDeclaration(declared("SensorHub", "produces", "%"))).toBe("%");
    const typed = declared("SensorHub", "produces", null, {
      type: "Speed_t",
      fixed: { unit: '"rpm"' },
    });
    expect(unitOfDeclaration(typed)).toBe("rpm");
  });

  test("the picker starts on the producer's unit, else the first declaration's", () => {
    expect(startingUnit(VALUE_A)).toBe("%");
    expect(startingUnit([declared("Controller", "reads", "rpm")])).toBe("rpm");
    expect(startingUnit([])).toBeNull();
  });

  test("a variable is described by its kind, its datatype or type, and who owns it", () => {
    expect(describe(VALUE_A)).toBe("measurement · uint8 · produced by SensorHub");
    expect(describe([declared("Controller", "local", "ms")])).toBe(
      "measurement · uint8 · local to Controller",
    );
    expect(describe([declared("Controller", "reads", "rpm", { type: "Speed_t" })])).toBe(
      "measurement · Speed_t · no producer",
    );
    expect(describe([declared("Controller", "reads", "rpm", { stated: {} })])).toBe(
      "declaration · no datatype · no producer",
    );
    expect(describe([])).toBe("");
  });
});

group("what the picker lists", () => {
  test("its own units first, the producer's first, then the other units in use", () => {
    const sections = pickerSections("ValueA", VALUE_A, FREE, "");
    expect(sections.map((section) => section.title)).toEqual([
      "Declared for ValueA",
      "Other units in this project",
      "No unit",
    ]);
    expect(sections[0]?.choices.map((c) => [c.id, c.label, c.detail])).toEqual([
      ["declared:%", "%", "SensorHub, UserInterface"],
      ["declared:rpm", "rpm", "Controller"],
    ]);
    expect(sections[1]?.choices.map((c) => [c.label, c.detail])).toEqual([["Hz", "4 variables"]]);
    expect(sections[2]?.choices).toEqual([
      { id: "none:", unit: null, label: "no unit", detail: "" },
    ]);
  });

  test("a declaration without a unit is listed as no unit among its own", () => {
    const sections = pickerSections(
      "ValueA",
      [declared("SensorHub", "produces", "%"), declared("Controller", "reads", null)],
      FREE,
      "",
    );
    expect(sections[0]?.choices.map((c) => [c.id, c.unit, c.detail])).toEqual([
      ["declared:%", "%", "SensorHub"],
      ["declared:", null, "Controller"],
    ]);
  });

  test("a variable with no declarations lists no declared section", () => {
    const sections = pickerSections("ValueA", [], FREE, "");
    expect(sections.map((section) => section.id)).toEqual(["used", "none"]);
  });

  test("with a vocabulary, the project's units follow, described and counted", () => {
    const sections = pickerSections("ValueA", VALUE_A, VOCABULARY, "");
    expect(sections[1]?.title).toBe("This project's units");
    expect(sections[1]?.choices.map((c) => [c.label, c.detail])).toEqual([
      ["rpm", "rotational speed · 1 variable"],
      ["Nm", ""],
    ]);
  });

  test("typing narrows every section, regardless of case", () => {
    const sections = pickerSections("ValueA", VALUE_A, FREE, "H");
    expect(sections.map((section) => section.id)).toEqual(["used", "typed"]);
    expect(sections[0]?.choices.map((c) => c.label)).toEqual(["Hz"]);
  });

  test("what was typed is offered as typed unless it is listed exactly", () => {
    const typed = pickerSections("ValueA", VALUE_A, VOCABULARY, "RPM");
    expect(typed.at(-1)).toEqual({
      id: "typed",
      title: "As typed",
      choices: [
        { id: "typed:RPM", unit: "RPM", label: "RPM", detail: "not one of this project's units" },
      ],
    });
    expect(pickerSections("ValueA", VALUE_A, FREE, "kPa").at(-1)?.choices[0]?.detail).toBe("");
    expect(pickerSections("ValueA", VALUE_A, FREE, "rpm").some((s) => s.id === "typed")).toBe(
      false,
    );
  });

  test("a unit outside the vocabulary is only flagged when there is one", () => {
    expect(outsideVocabulary(VOCABULARY, "RPM")).toBe(true);
    expect(outsideVocabulary(VOCABULARY, "rpm")).toBe(false);
    expect(outsideVocabulary(VOCABULARY, null)).toBe(false);
    expect(outsideVocabulary(FREE, "RPM")).toBe(false);
  });
});

group("what a preview says and sends", () => {
  test("a unit travels as its json text, and no unit as nothing", () => {
    expect(rawOf("%")).toBe('"%"');
    expect(rawOf(null)).toBeNull();
  });

  test("a declaration will change when an operation lands under it", () => {
    expect(willChange(ONE_FILE, declared("Controller", "reads", "rpm"))).toBe(true);
    expect(willChange(ONE_FILE, declared("SensorHub", "produces", "%"))).toBe(false);
    expect(
      willChange(
        ONE_FILE,
        declared("Controller", "reads", "rpm", { pointer: "component.interface[1].definition" }),
      ),
    ).toBe(false);
  });

  test("the consequence names the files a change writes", () => {
    expect(consequence([])).toBe("Nothing to change");
    expect(consequence(ONE_FILE.changes)).toBe("Changes 1 file: controller.ddd.json");
    const two = [...ONE_FILE.changes, { ...ONE_FILE_CHANGE, file: HUB }];
    expect(consequence(two)).toBe("Changes 2 files: controller.ddd.json, sensor_hub.ddd.json");
    expect(baseName("a.ddd.json")).toBe("a.ddd.json");
  });

  test("a hunk reads as its lines taken out, then its lines put in", () => {
    expect(hunkLines({ line: 14, before: ["a", "b"], after: ["c"] })).toEqual([
      { key: "-14", sign: "-", text: "a" },
      { key: "-15", sign: "-", text: "b" },
      { key: "+14", sign: "+", text: "c" },
    ]);
  });

  test("the edit a preview comes to is what POST /api/edit takes, hunks left behind", () => {
    expect(editOf(ONE_FILE)).toEqual({
      changes: [
        {
          file: CONTROLLER,
          fingerprint: "f",
          operations: [{ op: "set", pointer: `${AT}.unit`, raw: '"%"' }],
        },
      ],
    });
    expect(editOf({ revision: 1, changes: [] })).toBeNull();
    expect(editOf({ revision: 1, changes: [{ ...ONE_FILE_CHANGE, operations: [] }] })).toBeNull();
  });
});
