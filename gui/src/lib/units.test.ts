import { expect, describe as group, test } from "vitest";
import type { PlannedChange, SettleReply, UnitsReply, VariableDeclaration } from "../api/types";
import {
  baseName,
  changedNames,
  consequence,
  declaredUnits,
  editOf,
  enteredUnit,
  FILES_NAMED,
  hunkLines,
  outsideVocabulary,
  PLANNING,
  pickerSections,
  planning,
  rawOf,
  sentenceKeys,
  settleConsequence,
  shownChanges,
  textOf,
  unitLabel,
  unitOfDeclaration,
  unitRefusal,
  unloadableOf,
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
/** A row of the Units tab, which nothing here reads: a unit stated by variables alone. */
function row(
  unit: string,
  variables: number,
  description: string | null = null,
  files: string[] = [],
): UnitsReply["units"][number] {
  return { unit, description, files, variables, types: 0, members: 0, findings: 0 };
}

const FREE: UnitsReply = {
  revision: 1,
  vocabulary: null,
  used: [
    { unit: "Hz", variables: 4 },
    { unit: "%", variables: 3 },
    { unit: "rpm", variables: 1 },
  ],
  units: [row("%", 3), row("Hz", 4), row("rpm", 1)],
  adoptable: 3,
};
const UNITS_FILE = "C:/w/units.ddd.json";
const VOCABULARY: UnitsReply = {
  revision: 1,
  vocabulary: [
    { unit: "rpm", description: "rotational speed" },
    { unit: "Nm", description: null },
  ],
  used: [{ unit: "rpm", variables: 1 }],
  units: [row("Nm", 0, null, [UNITS_FILE]), row("rpm", 1, "rotational speed", [UNITS_FILE])],
  adoptable: null,
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
  unloadable: [],
};
const ONE_FILE_CHANGE = ONE_FILE.changes[0];

if (ONE_FILE_CHANGE === undefined) throw new Error("ONE_FILE must have one change");

/** Four changes, to a.ddd.json, b.ddd.json, c.ddd.json and d.ddd.json in that order. */
const files4 = (): PlannedChange[] =>
  ["a", "b", "c", "d"].map((name) => ({ ...ONE_FILE_CHANGE, file: `/p/${name}.ddd.json` }));

const CREATED_FILE_CHANGE: PlannedChange = {
  file: UNITS_FILE,
  fingerprint: null,
  operations: [{ op: "set", pointer: "", raw: '{"units": [{"unit": "%", "description": ""}]}' }],
  hunks: [{ line: 1, before: [], after: ["{", '  "units": ['] }],
};

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
});

group("what the picker lists", () => {
  test("its own units first, the producer's first, then the other units in use", () => {
    const sections = pickerSections("ValueA", declaredUnits(VALUE_A), FREE, "");
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
      declaredUnits([
        declared("SensorHub", "produces", "%"),
        declared("Controller", "reads", null),
      ]),
      FREE,
      "",
    );
    expect(sections[0]?.choices.map((c) => [c.id, c.unit, c.detail])).toEqual([
      ["declared:%", "%", "SensorHub"],
      ["declared:", null, "Controller"],
    ]);
  });

  test("a variable with no declarations lists no declared section", () => {
    const sections = pickerSections("ValueA", declaredUnits([]), FREE, "");
    expect(sections.map((section) => section.id)).toEqual(["used", "none"]);
  });

  test("with a vocabulary, the project's units follow, described and counted", () => {
    const sections = pickerSections("ValueA", declaredUnits(VALUE_A), VOCABULARY, "");
    expect(sections[1]?.title).toBe("This project's units");
    expect(sections[1]?.choices.map((c) => [c.label, c.detail])).toEqual([
      ["rpm", "rotational speed · 1 variable"],
      ["Nm", ""],
    ]);
  });

  test("typing narrows every section, regardless of case", () => {
    const sections = pickerSections("ValueA", declaredUnits(VALUE_A), FREE, "H");
    expect(sections.map((section) => section.id)).toEqual(["used", "typed"]);
    expect(sections[0]?.choices.map((c) => c.label)).toEqual(["Hz"]);
  });

  test("what was typed is offered as typed unless it is listed exactly", () => {
    const typed = pickerSections("ValueA", declaredUnits(VALUE_A), VOCABULARY, "RPM");
    expect(typed.at(-1)).toEqual({
      id: "typed",
      title: "As typed",
      choices: [
        { id: "typed:RPM", unit: "RPM", label: "RPM", detail: "not one of this project's units" },
      ],
    });
    expect(
      pickerSections("ValueA", declaredUnits(VALUE_A), FREE, "kPa").at(-1)?.choices[0]?.detail,
    ).toBe("");
    expect(
      pickerSections("ValueA", declaredUnits(VALUE_A), FREE, "rpm").some((s) => s.id === "typed"),
    ).toBe(false);
  });

  test("typing the no-unit label matches it exactly, so nothing is offered as typed", () => {
    const sections = pickerSections("ValueA", declaredUnits(VALUE_A), FREE, "no unit");
    expect(sections.map((section) => section.id)).toEqual(["none"]);
    expect(sections[0]?.choices).toEqual([
      { id: "none:", unit: null, label: "no unit", detail: "" },
    ]);
  });

  test("a unit outside the vocabulary is only flagged when there is one", () => {
    expect(outsideVocabulary(VOCABULARY, "RPM")).toBe(true);
    expect(outsideVocabulary(VOCABULARY, "rpm")).toBe(false);
    expect(outsideVocabulary(VOCABULARY, null)).toBe(false);
    expect(outsideVocabulary(FREE, "RPM")).toBe(false);
  });

  test("the field reads a unit as it is spelled, and no unit as its entry's label", () => {
    expect(unitLabel("rpm")).toBe("rpm");
    expect(unitLabel(null)).toBe("no unit");
    expect(unitLabel(null)).toBe(
      pickerSections("ValueA", declaredUnits(VALUE_A), FREE, "").at(-1)?.choices[0]?.label,
    );
  });
});

group("what Enter chooses with no entry of the list focused", () => {
  /** The picker as it stands while `text` is typed into it, and what Enter makes of that text. */
  const entered = (text: string, units: UnitsReply = FREE) =>
    enteredUnit(pickerSections("ValueA", declaredUnits(VALUE_A), units, text), text);

  test("a unit an entry states exactly is that entry's unit", () => {
    expect(entered("rpm")).toBe("rpm");
    expect(entered("Hz")).toBe("Hz");
    expect(entered("Nm", VOCABULARY)).toBe("Nm");
  });

  test("the no-unit entry's label is no unit", () => {
    expect(entered("no unit")).toBeNull();
  });

  test("a unit an entry states wins over the no-unit label, when a project spells one so", () => {
    const spelled: UnitsReply = { ...FREE, used: [{ unit: "no unit", variables: 1 }] };
    expect(entered("no unit", spelled)).toBe("no unit");
  });

  test("anything else is the text as typed, exactly as its As typed entry would take it", () => {
    expect(entered("RPM")).toBe("RPM");
    expect(entered("kPa", VOCABULARY)).toBe("kPa");
    expect(entered(" rpm")).toBe(" rpm");
    expect(entered("No Unit")).toBe("No Unit");
    const typed = pickerSections("ValueA", declaredUnits(VALUE_A), FREE, "RPM").at(-1)?.choices[0];
    expect(entered("RPM")).toBe(typed?.unit);
  });

  test("an empty field, or one holding only spaces, chooses nothing", () => {
    expect(entered("")).toBeUndefined();
    expect(entered("   ")).toBeUndefined();
  });

  test("the text is read against the entries, not against what they were narrowed by", () => {
    // Before anything is typed, the field shows the chosen unit and the list is not narrowed.
    const unnarrowed = pickerSections("ValueA", declaredUnits(VALUE_A), FREE, "");
    expect(enteredUnit(unnarrowed, "%")).toBe("%");
    expect(enteredUnit(unnarrowed, "no unit")).toBeNull();
    expect(enteredUnit(unnarrowed, "kPa")).toBe("kPa");
  });
});

group("what a preview says and sends", () => {
  test("a unit travels as its json text, and no unit as nothing", () => {
    expect(rawOf("%")).toBe('"%"');
    expect(rawOf(null)).toBeNull();
  });

  test("the consequence names the files a change writes", () => {
    expect(consequence([])).toBe("Nothing to change");
    expect(consequence(ONE_FILE.changes)).toBe("Changes 1 file: controller.ddd.json");
    const two = [...ONE_FILE.changes, { ...ONE_FILE_CHANGE, file: HUB }];
    expect(consequence(two)).toBe("Changes 2 files: controller.ddd.json, sensor_hub.ddd.json");
    expect(baseName("a.ddd.json")).toBe("a.ddd.json");
  });

  test("two files of one name are told apart by their paths, among every file the change writes", () => {
    // `left/gauge.ddd.json` and `right/gauge.ddd.json` read `gauge.ddd.json` twice (16:M15).
    const files = (...paths: string[]) => paths.map((file) => ({ ...ONE_FILE_CHANGE, file }));
    expect(consequence(files("/p/left/gauge.ddd.json", "/p/right/gauge.ddd.json"))).toBe(
      "Changes 2 files: left/gauge.ddd.json, right/gauge.ddd.json",
    );
    // Among all of them, not only the three named: the fourth file of the name tells the first
    // two apart too.
    expect(
      consequence(
        files(
          "/p/a/s.ddd.json",
          "/p/b/c.ddd.json",
          "/p/d/e.ddd.json",
          "/p/b/s.ddd.json",
          "/p/f.ddd.json",
        ),
      ),
    ).toBe("Changes 5 files: a/s.ddd.json, c.ddd.json, e.ddd.json and 2 more");
    expect(
      changedNames(files("/p/left/s.ddd.json", "/p/right/s.ddd.json", "/p/t.ddd.json")),
    ).toEqual(["left/s.ddd.json", "right/s.ddd.json", "t.ddd.json"]);
  });

  // Pinned by the literal, not by the constant, which a test comparing against it would follow.
  test("past a few files the consequence names three and counts the rest", () => {
    expect(FILES_NAMED).toBe(3);
    const files = (count: number) =>
      Array.from({ length: count }, (_, index) => ({
        ...ONE_FILE_CHANGE,
        file: `C:/w/components/c${String(index).padStart(5, "0")}.ddd.json`,
      }));
    expect(consequence(files(5))).toBe(
      "Changes 5 files: c00000.ddd.json, c00001.ddd.json, c00002.ddd.json and 2 more",
    );
    // Written as the Apply under it writes its own count, "Apply to 1200 files".
    expect(consequence(files(1200))).toBe(
      "Changes 1200 files: c00000.ddd.json, c00001.ddd.json, c00002.ddd.json and 1197 more",
    );
  });

  test("a file the count would stand for alone is named instead: never one more", () => {
    expect(consequence(files4())).toBe(
      "Changes 4 files: a.ddd.json, b.ddd.json, c.ddd.json, d.ddd.json",
    );
    expect(consequence(files4().slice(0, 3))).toBe(
      "Changes 3 files: a.ddd.json, b.ddd.json, c.ddd.json",
    );
  });

  test("a plan asked for and not come yet says so where its consequence stands", () => {
    expect(PLANNING).toBe("Planning…");
    expect(planning({ plan: null, refusal: null, pending: true })).toBe(true);
  });

  test("a plan come, a refusal said, or nothing asked for is no planning", () => {
    expect(planning({ plan: ONE_FILE, refusal: null, pending: false })).toBe(false);
    expect(
      planning({ plan: null, refusal: "units.ddd.json is there already", pending: true }),
    ).toBe(false);
    expect(planning({ plan: null, refusal: null, pending: false })).toBe(false);
    // A plan drawn is never said to be planning, whatever its offer says of the next.
    expect(planning({ plan: ONE_FILE, refusal: null, pending: true })).toBe(false);
  });

  test("a plan says which files it would leave unable to load, in the server's words and order", () => {
    const said = [
      "the declaration of 'ValueA' in controller.ddd.json would not load with that datatype: a string conversion needs a byte datatype, uint8 or sint8, got 'uint16'",
      "the declaration of 'ValueA' in sensor_hub.ddd.json would not load with that datatype: enum conversion 'Mode_t' requires an integer datatype, got 'uint16'",
    ];
    expect(unloadableOf({ ...ONE_FILE, unloadable: said }, null)).toEqual(said);
  });

  test("a settle's preview says that the readers' code is not touched, as the fix's title does", () => {
    expect(settleConsequence(ONE_FILE.changes)).toBe(
      "Changes 1 file: controller.ddd.json (the code of the readers is not touched)",
    );
    expect(settleConsequence([])).toBe("Nothing to change");
  });

  test("each sentence of a plan has a key of its own, two alike told apart by which they are", () => {
    // Two files of one name would not load for one reason: the same words twice, and a panel
    // keying each sentence by its words alone drew one of them twice under one key.
    const same = "the declaration of 'ValueA' in b.ddd.json would not load with that dimensions";
    const keyed = sentenceKeys([same, "another", same]);
    expect(keyed.map((each) => each.text)).toEqual([same, "another", same]);
    expect(new Set(keyed.map((each) => each.key)).size).toBe(3);
    expect(sentenceKeys([])).toEqual([]);
  });

  test("a plan every file of which still loads says nothing of it, and neither does no plan", () => {
    expect(unloadableOf(ONE_FILE, null)).toEqual([]);
    expect(unloadableOf(null, null)).toEqual([]);
  });

  test("nothing is said of a plan the panel does not draw: it says why it cannot be applied", () => {
    const said = [
      "the declaration of 'ValueA' in controller.ddd.json would not load with that datatype: x",
    ];
    expect(unloadableOf({ ...ONE_FILE, unloadable: said }, "A file changed on disk")).toEqual([]);
  });

  test("names a file a change creates as new, and every other by its line", () => {
    expect(shownChanges([ONE_FILE_CHANGE, CREATED_FILE_CHANGE])).toEqual([
      { file: ONE_FILE_CHANGE.file, hunks: ONE_FILE_CHANGE.hunks, note: null },
      { file: CREATED_FILE_CHANGE.file, hunks: CREATED_FILE_CHANGE.hunks, note: "new" },
    ]);
  });

  test("a hunk reads as its lines taken out, then its lines put in", () => {
    expect(hunkLines({ line: 14, before: ["a", "b"], after: ["c"] })).toEqual([
      { key: "-14", sign: "-", text: "a" },
      { key: "-15", sign: "-", text: "b" },
      { key: "+14", sign: "+", text: "c" },
    ]);
  });

  test("the edit a preview comes to is what POST /api/edit takes, hunks left behind", () => {
    expect(editOf(ONE_FILE, "the unit of ValueA")).toEqual({
      changes: [
        {
          file: CONTROLLER,
          fingerprint: "f",
          operations: [{ op: "set", pointer: `${AT}.unit`, raw: '"%"' }],
        },
      ],
      label: "the unit of ValueA",
    });
    expect(editOf({ revision: 1, changes: [] }, "the unit of ValueA")).toBeNull();
    expect(
      editOf(
        { revision: 1, changes: [{ ...ONE_FILE_CHANGE, operations: [] }] },
        "the unit of ValueA",
      ),
    ).toBeNull();
  });
});

group("a unit with spaces around it (15:M10)", () => {
  test("is refused in the words the Units tab refuses the spelling with", () => {
    expect(unitRefusal("V ")).toBe("'V ' has spaces around it");
    expect(unitRefusal(" V")).toBe("' V' has spaces around it");
  });

  test.each(
    // White space as python's `str.strip` takes it off, which the server judges by: the four
    // separators and the next-line among it, which JavaScript's `trim` keeps.
    [0x09, 0x0a, 0x0d, 0x1c, 0x1f, 0x85, 0xa0, 0x2000, 0x3000].map((code) => ({
      code,
      hex: code.toString(16).toUpperCase().padStart(4, "0"),
    })),
  )("U+$hex around a unit is space around it", ({ code }) => {
    const space = String.fromCodePoint(code);
    expect(unitRefusal(`V${space}`)).toBe(`'V${space}' has spaces around it`);
    expect(unitRefusal(`${space}V`)).not.toBeNull();
  });

  test("a byte order mark, which python keeps, is no space around it, nor is one inside", () => {
    expect(unitRefusal(`V${String.fromCodePoint(0xfeff)}`)).toBeNull();
    expect(unitRefusal("m s")).toBeNull();
    expect(unitRefusal("V")).toBeNull();
    expect(unitRefusal("")).toBeNull();
    expect(unitRefusal(null)).toBeNull();
  });
});
