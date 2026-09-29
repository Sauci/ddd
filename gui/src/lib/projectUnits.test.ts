import { expect, describe as group, test } from "vitest";
import type {
  PlannedChange,
  PlanReply,
  ProjectUnit,
  UnitPlace,
  UnitReply,
  UnitsReply,
} from "../api/types";
import {
  adoptionAsked,
  adoptionOffered,
  adoptionSentence,
  descriptionOf,
  findingCheck,
  hasUnitsFile,
  offers,
  placeRole,
  planEdit,
  renameConsequence,
  renameSections,
  statedBy,
  tabTitle,
  unitMeta,
  unitRows,
} from "./projectUnits";

const UNITS_FILE = "C:/w/units.ddd.json";
const MORE_UNITS = "C:/w/more_units.ddd.json";
const CONTROLLER = "C:/w/components/controller.ddd.json";
const PUMP = "C:/w/components/pump.ddd.json";
const TYPES = "C:/w/types.ddd.json";

/** A row of the Units tab: outside the vocabulary and stated by nothing, unless told otherwise. */
function row(unit: string, extra: Partial<ProjectUnit> = {}): ProjectUnit {
  return {
    unit,
    description: null,
    files: [],
    variables: 0,
    types: 0,
    members: 0,
    findings: 0,
    ...extra,
  };
}

// The vocabulary example with one declaration drifted to RPM from outside, and a type file
// stating RPM too: the mockups' project, cut down.
const RPM = row("RPM", { variables: 1, types: 1, findings: 2 });
const RPM_LISTED = row("rpm", {
  description: "rotational speed",
  files: [UNITS_FILE],
  variables: 2,
});
const KPA = row("kPa", { description: "pressure", files: [UNITS_FILE], variables: 2 });
const NM = row("Nm", { description: null, files: [UNITS_FILE], types: 1 });
const DEGC = row("degC", { description: "temperature", files: [UNITS_FILE] });
const MS = row("ms", { variables: 1, findings: 1 });
const ROWS = [DEGC, KPA, MS, NM, RPM, RPM_LISTED];
const VOCABULARY: UnitsReply = {
  revision: 3,
  vocabulary: [
    { unit: "rpm", description: "rotational speed" },
    { unit: "Nm", description: null },
    { unit: "degC", description: "temperature" },
    { unit: "kPa", description: "pressure" },
  ],
  used: [
    { unit: "kPa", variables: 2 },
    { unit: "rpm", variables: 2 },
    { unit: "RPM", variables: 1 },
    { unit: "ms", variables: 1 },
  ],
  units: ROWS,
  adoptable: null,
};
// The same project without its units file: every unit is free, and adoption would list them.
const FREE: UnitsReply = {
  revision: 3,
  vocabulary: null,
  used: VOCABULARY.used,
  units: [
    row("Hz", { variables: 3 }),
    row("%", { variables: 4 }),
    row("RPM", { variables: 1, types: 1 }),
    row("rpm", { variables: 2 }),
    row("V", { variables: 2 }),
  ],
  adoptable: 5,
};
// The same project with its units file emptied: the file still opts it in, so every unit it
// states is outside the vocabulary with a finding, and adopting would list them in a units file.
const EMPTIED: UnitsReply = {
  ...FREE,
  vocabulary: [],
  units: FREE.units.map((unit) => ({ ...unit, findings: 1 })),
};

function place(kind: UnitPlace["kind"], path: string, extra: Partial<UnitPlace> = {}): UnitPlace {
  return {
    path,
    pointer: "component.interface[0].definition.unit",
    kind,
    name: "EngineSpeed",
    component: kind === "variable" ? "Controller" : null,
    role: kind === "variable" ? "reads" : null,
    ...extra,
  };
}

function reply(unit: string, sites: UnitPlace[]): UnitReply {
  return { revision: 3, unit, description: null, entries: [], sites, findings: [] };
}

// RPM renamed onto rpm: Controller's declaration and the scalar type stating it.
const IN_CONTROLLER: PlannedChange = {
  file: CONTROLLER,
  fingerprint: "c0",
  operations: [{ op: "set", pointer: "component.interface[0].definition.unit", raw: '"rpm"' }],
  hunks: [{ line: 14, before: ['  "unit": "RPM",'], after: ['  "unit": "rpm",'] }],
};
const IN_TYPES: PlannedChange = {
  file: TYPES,
  fingerprint: "t0",
  operations: [{ op: "set", pointer: "types[0].unit", raw: '"rpm"' }],
  hunks: [{ line: 6, before: ['  "unit": "RPM",'], after: ['  "unit": "rpm",'] }],
};
const MERGE: PlanReply = { revision: 3, changes: [IN_CONTROLLER, IN_TYPES] };
const ONE_FILE: PlanReply = { revision: 3, changes: [IN_CONTROLLER] };
// rpm renamed onto RPM, which no entry lists: its own entry is renamed with it.
const RENAMED_ENTRY: PlanReply = {
  revision: 3,
  changes: [
    { ...IN_CONTROLLER, file: PUMP },
    {
      file: UNITS_FILE,
      fingerprint: "u0",
      operations: [{ op: "set", pointer: "units[0].unit", raw: '"RPM"' }],
      hunks: [{ line: 3, before: ['  { "unit": "rpm",'], after: ['  { "unit": "RPM",'] }],
    },
  ],
};

group("the table", () => {
  test("units with findings come first, then the most stated, then by spelling, unused last", () => {
    expect(unitRows(ROWS).map((unit) => unit.unit)).toEqual([
      "RPM",
      "ms",
      "kPa",
      "rpm",
      "Nm",
      "degC",
    ]);
  });

  test("spellings compare code unit by code unit, capitals first, whatever the locale", () => {
    const tied = [
      row("rpm", { variables: 1 }),
      row("°C", { variables: 1 }),
      row("RPM", { variables: 1 }),
    ];
    expect(unitRows(tied).map((unit) => unit.unit)).toEqual(["RPM", "rpm", "°C"]);
  });

  test("an unused vocabulary entry with a finding of its own still comes with the findings", () => {
    const twice = row("bar", { files: [UNITS_FILE, MORE_UNITS], findings: 2 });
    expect(unitRows([KPA, twice]).map((unit) => unit.unit)).toEqual(["bar", "kPa"]);
  });

  test("the table leaves the answer as it came", () => {
    const rows = [...ROWS];
    unitRows(rows);
    expect(rows).toEqual(ROWS);
  });

  test.each([
    [RPM_LISTED, "2 variables"],
    [RPM, "1 variable, 1 type"],
    [NM, "1 type"],
    [row("m/s", { variables: 1, types: 2, members: 3 }), "1 variable, 2 types, 3 members"],
    [row("N", { members: 1 }), "1 member"],
    [DEGC, "unused"],
  ])("%o is stated by %s", (unit, sentence) => {
    expect(statedBy(unit)).toBe(sentence);
  });

  test("the description is the vocabulary's, and says so of a unit outside it", () => {
    expect(descriptionOf(RPM_LISTED, true)).toBe("rotational speed");
    expect(descriptionOf(NM, true)).toBe("");
    expect(descriptionOf(RPM, true)).toBe("not in the vocabulary");
  });

  test("without a units file no unit is described, and none is said to be outside", () => {
    expect(descriptionOf(RPM, false)).toBe("");
  });

  test("a unit's findings are unknown outside the vocabulary, and listed twice inside it", () => {
    expect(findingCheck(RPM)).toBe("unknown-unit");
    expect(findingCheck(row("kPa", { files: [UNITS_FILE, MORE_UNITS], findings: 2 }))).toBe(
      "duplicate-unit",
    );
    expect(findingCheck(RPM_LISTED)).toBeNull();
  });

  test("the title counts the units, and those the vocabulary leaves out", () => {
    expect(tabTitle(ROWS, true)).toBe("6 units · 2 not in the vocabulary");
    expect(tabTitle([RPM_LISTED], true)).toBe("1 unit · all in the vocabulary");
    expect(tabTitle(FREE.units, false)).toBe("5 units · no units file");
    expect(tabTitle([], false)).toBe("0 units · no units file");
  });
});

group("a unit's panel", () => {
  test("the line under the unit says where it is listed and how widely it is stated", () => {
    const sites = [place("variable", CONTROLLER), place("type", TYPES, { name: "Speed_t" })];
    expect(unitMeta(RPM, reply("RPM", sites), true)).toBe(
      "not in the vocabulary · stated in 2 places, 2 files",
    );
    const two = [place("variable", PUMP), place("variable", PUMP, { name: "PumpSpeed" })];
    expect(unitMeta(RPM_LISTED, reply("rpm", two), true)).toBe(
      "in the vocabulary, units.ddd.json · stated in 2 places, 1 file",
    );
    expect(unitMeta(DEGC, reply("degC", []), true)).toBe(
      "in the vocabulary, units.ddd.json · stated nowhere",
    );
    const twice = row("kPa", { files: [UNITS_FILE, MORE_UNITS] });
    expect(unitMeta(twice, reply("kPa", [place("variable", PUMP)]), true)).toBe(
      "in the vocabulary, units.ddd.json, more_units.ddd.json · stated in 1 place, 1 file",
    );
  });

  test("without a units file the line says only where the unit is stated", () => {
    const sites = [place("variable", CONTROLLER), place("type", TYPES, { name: "Speed_t" })];
    expect(unitMeta(RPM, reply("RPM", sites), false)).toBe("stated in 2 places, 2 files");
  });

  test("a place is a variable's role, a scalar type or a structure member", () => {
    expect(placeRole(place("variable", PUMP, { role: "local" }))).toBe("local");
    expect(placeRole(place("type", TYPES))).toBe("scalar type");
    expect(placeRole(place("member", TYPES, { name: "Motor_t.speed" }))).toBe("structure member");
    expect(placeRole(place("variable", PUMP, { role: null }))).toBe("variable");
  });

  test("a unit the vocabulary lists is described, and removed once nothing states it", () => {
    expect(offers(RPM_LISTED, true)).toEqual({ describe: true, add: false, remove: false });
    expect(offers(DEGC, true)).toEqual({ describe: true, add: false, remove: true });
  });

  test("a unit outside the vocabulary is added to it, when the project has one", () => {
    expect(offers(RPM, true)).toEqual({ describe: false, add: true, remove: false });
    expect(offers(RPM, false)).toEqual({ describe: false, add: false, remove: false });
  });
});

group("the rename picker", () => {
  test("the vocabulary's units first, then the other units in use, the unit left out", () => {
    const sections = renameSections("RPM", VOCABULARY, "");
    expect(sections.map((section) => [section.id, section.title])).toEqual([
      ["vocabulary", "This project's units"],
      ["used", "Other units in this project"],
    ]);
    expect(sections[0]?.choices.map((c) => [c.id, c.unit, c.label, c.detail])).toEqual([
      ["vocabulary:rpm", "rpm", "rpm", "rotational speed · 2 variables"],
      ["vocabulary:Nm", "Nm", "Nm", "1 type"],
      ["vocabulary:degC", "degC", "degC", "temperature · unused"],
      ["vocabulary:kPa", "kPa", "kPa", "pressure · 2 variables"],
    ]);
    expect(sections[1]?.choices.map((c) => [c.id, c.detail])).toEqual([["used:ms", "1 variable"]]);
  });

  test("without a vocabulary every other unit in use is listed, the most stated first", () => {
    const sections = renameSections("RPM", FREE, "");
    expect(sections.map((section) => section.id)).toEqual(["used"]);
    expect(sections[0]?.choices.map((c) => [c.label, c.detail])).toEqual([
      ["%", "4 variables"],
      ["Hz", "3 variables"],
      ["V", "2 variables"],
      ["rpm", "2 variables"],
    ]);
  });

  test("an adopted vocabulary's empty descriptions leave only what states each unit", () => {
    const adopted: UnitsReply = {
      ...VOCABULARY,
      units: [row("rpm", { description: "", files: [UNITS_FILE], variables: 1 })],
    };
    expect(renameSections("RPM", adopted, "")[0]?.choices[0]?.detail).toBe("1 variable");
  });

  test("typing narrows every section, regardless of case", () => {
    const sections = renameSections("RPM", VOCABULARY, "M");
    expect(sections.map((section) => section.choices.map((c) => c.label))).toEqual([
      ["rpm", "Nm"],
      ["ms"],
      ["M"],
    ]);
  });

  test("what was typed is offered as typed unless it is listed exactly, or is the unit itself", () => {
    expect(renameSections("RPM", VOCABULARY, "rpm/min").at(-1)).toEqual({
      id: "typed",
      title: "As typed",
      choices: [
        {
          id: "typed:rpm/min",
          unit: "rpm/min",
          label: "rpm/min",
          detail: "not one of this project's units",
        },
      ],
    });
    expect(renameSections("RPM", FREE, "rpm/min").at(-1)?.choices[0]?.detail).toBe("");
    expect(renameSections("RPM", VOCABULARY, "rpm").some((s) => s.id === "typed")).toBe(false);
    expect(renameSections("RPM", VOCABULARY, "RPM").some((s) => s.id === "typed")).toBe(false);
  });
});

group("adoption", () => {
  test("is offered exactly where the server says how many units it would list", () => {
    expect(adoptionOffered(FREE)).toBe(true);
    expect(adoptionOffered(EMPTIED)).toBe(true);
    expect(adoptionOffered({ ...FREE, adoptable: 0 })).toBe(true);
    expect(adoptionOffered(VOCABULARY)).toBe(false);
  });

  test("reads the server's decision rather than working it out again from the vocabulary", () => {
    // `vocabulary` is read out of the files as they are written, so a units file that did not
    // load still lists its units there while the analysis - and so `adopt_units` - reads none.
    // The server answers `adoptable` from the one question `adopt_units` refuses by; asked here
    // of `vocabulary` instead, the two could disagree about the very same project.
    expect(adoptionOffered({ ...VOCABULARY, adoptable: 4 })).toBe(true);
    expect(adoptionOffered({ ...EMPTIED, adoptable: null })).toBe(false);
  });

  test("the banner knows a project with a units file from one without, whatever the file lists", () => {
    expect(hasUnitsFile(FREE)).toBe(false);
    expect(hasUnitsFile(EMPTIED)).toBe(true);
    expect(hasUnitsFile(VOCABULARY)).toBe(true);
  });

  test("its plan is asked for only where adopting would list a unit", () => {
    expect(adoptionAsked(FREE)).toBe(true);
    expect(adoptionAsked(EMPTIED)).toBe(true);
    expect(adoptionAsked({ ...FREE, adoptable: 0 })).toBe(false);
    expect(adoptionAsked(VOCABULARY)).toBe(false);
  });
});

group("what a plan says and sends", () => {
  test("renaming onto a spelling the vocabulary lists merges the two", () => {
    expect(renameConsequence(MERGE, RPM, "rpm", VOCABULARY)).toBe(
      "Changes 2 files: controller.ddd.json, types.ddd.json. " +
        "rpm is in the vocabulary already, so RPM merges into it.",
    );
  });

  test("renaming a listed unit onto a new spelling renames its entry too", () => {
    expect(renameConsequence(RENAMED_ENTRY, RPM_LISTED, "RPM", VOCABULARY)).toBe(
      "Changes 2 files: pump.ddd.json, units.ddd.json. rpm is renamed in units.ddd.json too.",
    );
  });

  test("renaming onto a spelling no vocabulary lists says so, as part 1's picker does", () => {
    expect(renameConsequence(ONE_FILE, MS, "s", VOCABULARY)).toBe(
      "Changes 1 file: controller.ddd.json. Not one of this project's units.",
    );
  });

  test("without a units file a rename says only what it changes", () => {
    expect(renameConsequence(MERGE, RPM, "rpm", FREE)).toBe(
      "Changes 2 files: controller.ddd.json, types.ddd.json",
    );
  });

  test("the banner says what adopting writes, and that nothing more will be reported", () => {
    expect(adoptionSentence(8, false)).toBe(
      "This project has no units file, so no unit is checked against a vocabulary. " +
        "Adopting writes units.ddd.json with the 8 units in use and includes it in the " +
        "project: nothing is reported that is not reported today.",
    );
    expect(adoptionSentence(1, false)).toContain("with the 1 unit in use");
  });

  test("a project stating no unit has nothing to adopt, and the banner says so", () => {
    expect(adoptionSentence(0, false)).toBe(
      "This project has no units file, so no unit is checked against a vocabulary. " +
        "It states no unit, so there is nothing to adopt.",
    );
  });

  test("with a units file listing no unit, the banner says none is in it and adopting lists them", () => {
    // Not "writes units.ddd.json": a units file declaring nothing still opts the project in, and
    // adopting fills the first the description includes rather than writing a second. Nor does
    // it name that file: the page reads units files out of every file the project read, and the
    // server out of the description's own includes, so only "a units file" is true of both.
    expect(adoptionSentence(5, true)).toBe(
      "No unit this project states is in its vocabulary. Adopting lists the 5 units in use " +
        "in a units file: nothing is reported that is not reported today.",
    );
    expect(adoptionSentence(1, true)).toContain("lists the 1 unit in use");
    expect(adoptionSentence(0, true)).toBe(
      "This project states no unit, so there is nothing to adopt.",
    );
  });

  test("a plan comes to the edit POST /api/edit takes, a created file's null fingerprint kept", () => {
    const adoption: PlanReply = {
      revision: 3,
      changes: [
        {
          file: "C:/w/demo.ddd.json",
          fingerprint: "d0",
          operations: [{ op: "insert", pointer: "project.includes[2]", raw: '"units.ddd.json"' }],
          hunks: [{ line: 7, before: [], after: ['      "units.ddd.json"'] }],
        },
        {
          file: UNITS_FILE,
          fingerprint: null,
          operations: [
            { op: "set", pointer: "", raw: '{"units": [{"unit": "%", "description": ""}]}' },
          ],
          hunks: [{ line: 1, before: [], after: ["{", '  "units": ['] }],
        },
      ],
    };
    expect(planEdit(adoption, "the vocabulary adopted")).toEqual({
      changes: [
        {
          file: "C:/w/demo.ddd.json",
          fingerprint: "d0",
          operations: [{ op: "insert", pointer: "project.includes[2]", raw: '"units.ddd.json"' }],
        },
        {
          file: UNITS_FILE,
          fingerprint: null,
          operations: [
            { op: "set", pointer: "", raw: '{"units": [{"unit": "%", "description": ""}]}' },
          ],
        },
      ],
      label: "the vocabulary adopted",
    });
  });

  test("a plan with nothing to change comes to no edit", () => {
    expect(planEdit({ revision: 3, changes: [] }, "the vocabulary adopted")).toBeNull();
  });
});
