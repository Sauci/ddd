import { describe, expect, test } from "vitest";
import type { DeclarableName, DeclarableReply } from "../api/types";
import {
  chosenName,
  declareSentence,
  definitionOf,
  dimensionNote,
  dimensionsRaw,
  followedScope,
  formUnsettled,
  keysOf,
  keyUnsettled,
  labelOf,
  modeOf,
  NAMES_SHOWN,
  nameList,
  removalSentence,
  scopesOf,
  statedValues,
  stillNeeded,
} from "./declarations";

function offer(key: string, required: boolean, editor = "none") {
  return {
    key,
    carried: [{ allowed: true, required }],
    values: [],
    disagrees: false,
    editor,
    choices: [],
  };
}

const REPLY: DeclarableReply = {
  revision: 3,
  file: "/p/components/controller.ddd.json",
  names: [
    { name: "ValueC", kind: "measurement", producer: "SensorHub", scopes: ["input"] },
    { name: "Orphan", kind: "measurement", producer: null, scopes: ["output", "input"] },
  ],
  kinds: [
    {
      kind: "measurement",
      keys: [
        offer("datatype", false, "datatype"),
        offer("typename", false, "typename"),
        offer("unit", false, "unit"),
        offer("volatile", true, "volatile"),
      ],
    },
    {
      kind: "value_block",
      keys: [offer("dimensions", true), offer("volatile", true, "volatile")],
    },
  ],
  scopes: ["output", "input", "local"],
  constants: ["TREND_SAMPLES"],
} as DeclarableReply;

describe("which of the two verbs the name field has landed on", () => {
  test("nothing typed has landed on neither", () => {
    expect(modeOf("", REPLY.names)).toBe("unchosen");
  });

  test("a name the project declares is read", () => {
    expect(modeOf("ValueC", REPLY.names)).toBe("read");
    expect(chosenName("ValueC", REPLY.names)?.producer).toBe("SensorHub");
  });

  test("a name it does not is declared", () => {
    expect(modeOf("Pressure", REPLY.names)).toBe("declare");
    expect(chosenName("Pressure", REPLY.names)).toBeNull();
  });
});

describe("the Name list, narrowed by what is typed and drawn to a cap", () => {
  /** `count` names a generated project could offer, `C00000_O0000` on, a hundred to a component. */
  function generated(count: number): DeclarableName[] {
    return Array.from({ length: count }, (_, index) => ({
      name: `C${String(Math.floor(index / 100)).padStart(5, "0")}_O${String(index % 100).padStart(4, "0")}`,
      kind: "measurement",
      producer: `C${String(Math.floor(index / 100)).padStart(5, "0")}`,
      scopes: ["input"],
    }));
  }
  const labels = (typed: string, names: DeclarableName[]) =>
    nameList(names, typed).sections.flatMap((section) => section.choices.map((c) => c.label));

  test("every name holding the text is listed, whatever its case, as the unit picker narrows", () => {
    const names: DeclarableName[] = [
      ...REPLY.names,
      { name: "valueD", kind: "measurement", producer: null, scopes: ["input"] },
    ];
    expect(labels("VALUE", names)).toEqual(["ValueC", "valueD"]);
    expect(labels("", names)).toEqual(["ValueC", "Orphan", "valueD"]);
  });

  // Pinned by the literal, not by the constant, which a test comparing against it would follow.
  test("fifty at most are drawn, and the line under them says how many more match", () => {
    expect(NAMES_SHOWN).toBe(50);
    const list = nameList(generated(120), "");
    expect(list.sections.flatMap((section) => section.choices)).toHaveLength(50);
    expect(list.footnote).toBe("70 more names match: type to narrow the list.");
  });

  test("the cap holds whatever narrows the list, and the line counts what it narrowed to", () => {
    // `_O0010` to `_O0019` of each of 263 components: 2,630 names, fifty of them drawn.
    const list = nameList(generated(26300), "_o001");
    expect(list.sections.flatMap((section) => section.choices)).toHaveLength(50);
    expect(list.footnote).toBe("2,580 more names match: type to narrow the list.");
  });

  test("one more is said in the singular", () => {
    expect(nameList(generated(51), "").footnote).toBe(
      "1 more name matches: type to narrow the list.",
    );
  });

  test("the name the text spells exactly comes first, so the cap never hides it", () => {
    // Each of the eighty holds "O00", and so does the name spelling it, last in the server's order.
    const names: DeclarableName[] = [
      ...generated(80),
      { name: "O00", kind: "measurement", producer: null, scopes: ["input"] },
    ];
    const listed = labels("O00", names);
    expect(listed).toHaveLength(50);
    expect(listed.slice(0, 3)).toEqual(["O00", "C00000_O0000", "C00000_O0001"]);
  });

  test("a list drawing every name that matches says nothing more", () => {
    expect(nameList(generated(120), "C00001_O001").footnote).toBeUndefined();
    expect(nameList(generated(50), "").footnote).toBeUndefined();
  });

  test("no name holding the text lists nothing, and no section is left empty", () => {
    expect(nameList(generated(120), "Pressure")).toEqual({ sections: [], footnote: undefined });
  });

  test("each entry is the name, under the project's variables, with its kind and its producer", () => {
    expect(nameList(REPLY.names, "").sections).toEqual([
      {
        id: "names",
        title: "This project's variables",
        choices: [
          { id: "ValueC", label: "ValueC", detail: "measurement from SensorHub" },
          { id: "Orphan", label: "Orphan", detail: "measurement from no producer" },
        ],
      },
    ]);
  });
});

describe("which scopes a name may take", () => {
  test("a listed name's are the server's answer for it", () => {
    expect(scopesOf("ValueC", REPLY)).toEqual(["input"]);
    expect(scopesOf("Orphan", REPLY)).toEqual(["output", "input"]);
  });

  test("a new name may take all three", () => {
    expect(scopesOf("Pressure", REPLY)).toEqual(["output", "input", "local"]);
  });
});

// Moved out of DeclarePanel.tsx's own effect (the final review's fix wave, Task 11's parked
// minor): the scope the form keeps as the name it scopes changes.
describe("which scope the form keeps as the name changes", () => {
  test("a scope the name still takes is kept as chosen", () => {
    expect(followedScope("local", scopesOf("Pressure", REPLY))).toBe("local");
  });

  test("a scope the name does not take moves forward onto the first it does", () => {
    expect(followedScope("local", scopesOf("ValueC", REPLY))).toBe("input");
  });

  test("none chosen yet starts on the first the name takes", () => {
    expect(followedScope("", scopesOf("Orphan", REPLY))).toBe("output");
  });

  test("a name taking no scope at all leaves none", () => {
    expect(followedScope("local", [])).toBe("");
  });
});

describe("what a kind asks for", () => {
  test("required keys come first, in the server's order within each group", () => {
    expect(keysOf("value_block", REPLY).map((key) => key.key)).toEqual(["dimensions", "volatile"]);
  });

  test("datatype and typename join the required keys - the storage a declaration names", () => {
    expect(keysOf("measurement", REPLY).map((key) => key.key)).toEqual([
      "volatile",
      "datatype",
      "typename",
    ]);
  });

  test("unit is not storage, so it does not join them", () => {
    expect(keysOf("measurement", REPLY).map((key) => key.key)).not.toContain("unit");
  });

  test("a kind the reply does not carry asks for nothing", () => {
    expect(keysOf("nonsense", REPLY)).toEqual([]);
  });
});

describe("the definition the form has made", () => {
  test("it is json with the name and the kind in it", () => {
    const raw = definitionOf("Pressure", "measurement", { volatile: "false" }, REPLY);
    expect(JSON.parse(raw ?? "")).toEqual({
      name: "Pressure",
      kind: "measurement",
      volatile: false,
    });
  });

  test("a stated optional key joins it", () => {
    const raw = definitionOf(
      "Pressure",
      "measurement",
      { volatile: "false", typename: '"Speed_t"' },
      REPLY,
    );
    expect(JSON.parse(raw ?? "")).toEqual({
      name: "Pressure",
      kind: "measurement",
      volatile: false,
      typename: "Speed_t",
    });
  });

  test("a stated datatype carries the identity conversion with it", () => {
    const raw = definitionOf(
      "Pressure",
      "measurement",
      { volatile: "false", datatype: '"uint8"' },
      REPLY,
    );
    expect(JSON.parse(raw ?? "")).toEqual({
      name: "Pressure",
      kind: "measurement",
      volatile: false,
      datatype: "uint8",
      conversion: { kind: "identity" },
    });
  });

  test("a required key left unstated makes no definition at all", () => {
    expect(definitionOf("Pressure", "measurement", {}, REPLY)).toBeNull();
  });

  test("a value that is not json makes none either", () => {
    expect(definitionOf("Pressure", "measurement", { volatile: "maybe" }, REPLY)).toBeNull();
  });

  test("a name or a kind left empty makes none", () => {
    expect(definitionOf("", "measurement", { volatile: "false" }, REPLY)).toBeNull();
    expect(definitionOf("Pressure", "", { volatile: "false" }, REPLY)).toBeNull();
  });
});

describe("the dimensions a row of fields makes", () => {
  test("a whole number is a number and anything else is a constant's name", () => {
    expect(dimensionsRaw(["4", "CELLS"])).toBe('[4,"CELLS"]');
  });

  test("no rows at all state nothing", () => {
    expect(dimensionsRaw([])).toBeNull();
  });

  test("a blank row states nothing, because a value block is never a scalar", () => {
    expect(dimensionsRaw(["4", ""])).toBeNull();
  });

  test("a number is read as every field reads one, in its own digits", () => {
    expect(dimensionsRaw(["1e1", " 4 ", "+8", "1,024,000"])).toBe("[10,4,8,1024000]");
    // A number that is no size is one all the same, for the server to refuse in its words,
    // rather than the name of a constant nobody declared.
    expect(dimensionsRaw(["2.5"])).toBe("[2.5]");
    expect(dimensionsRaw(["0"])).toBe("[0]");
  });

  test("one in another notation is refused, and makes no shape to ask a plan for", () => {
    // 15:M13: `0x10` was taken for the name of a constant.
    expect(dimensionsRaw(["4", "0x10"])).toBeNull();
    expect(dimensionNote("0x10")).toBe("'0x10' is not a number in decimal notation");
    expect(dimensionNote("1,000")).toBe(
      "the comma in '1,000' could be a decimal point or a thousands separator",
    );
    expect(dimensionNote("4x")).toBe("'4x' is not a number");
  });

  test("a name, a number or nothing yet says nothing", () => {
    expect(dimensionNote("CELLS")).toBeUndefined();
    expect(dimensionNote("Infinity")).toBeUndefined();
    expect(dimensionNote("4")).toBeUndefined();
    expect(dimensionNote(" ")).toBeUndefined();
  });
});

describe("the sentence that tells reading from declaring", () => {
  test("a listed name names its producer", () => {
    expect(declareSentence("ValueC", "", "input", REPLY)).toBe(
      "Reads ValueC as SensorHub declares it.",
    );
  });

  test("a listed name nothing produces says so", () => {
    expect(declareSentence("Orphan", "", "input", REPLY)).toBe(
      "Reads Orphan as this project declares it.",
    );
  });

  test("a new name with no kind chosen yet asks for one, not a sentence with a blank in it", () => {
    expect(declareSentence("Pressure", "", "input", REPLY)).toBe("Choose a kind for Pressure.");
  });

  test("a new name names the kind and the scope", () => {
    expect(declareSentence("Pressure", "measurement", "output", REPLY)).toBe(
      "Declares Pressure, a measurement this component produces.",
    );
  });

  test("a listed name's sentence follows the scope chosen, not the verb reading it", () => {
    expect(declareSentence("Orphan", "", "output", REPLY)).toBe(
      "Produces Orphan as this project declares it.",
    );
    expect(declareSentence("ValueC", "", "local", REPLY)).toBe(
      "Keeps ValueC to itself as SensorHub declares it.",
    );
  });

  test("nothing typed asks for a name", () => {
    expect(declareSentence("", "", "input", REPLY)).toBe("Choose a variable, or type a new name.");
  });

  test("a scope the roles do not name is spelled as given", () => {
    expect(declareSentence("Pressure", "measurement", "mystery", REPLY)).toBe(
      "Declares Pressure, a measurement this component mystery.",
    );
  });
});

describe("what removing a declaration leaves behind", () => {
  const declaredBy = (...entries: [string, string][]) => ({
    name: "ValueA",
    declarations: entries.map(([component, role]) => ({ component, role })),
  });

  test("the only declaration leaves nothing", () => {
    expect(removalSentence(declaredBy(["Controller", "reads"]), "Controller")).toBe(
      "Removes ValueA, which no other component declares.",
    );
  });

  test("the readers left behind are named", () => {
    const variable = declaredBy(
      ["SensorHub", "produces"],
      ["Controller", "reads"],
      ["UserInterface", "reads"],
    );
    expect(removalSentence(variable, "SensorHub")).toBe(
      "Removes ValueA from SensorHub; Controller and UserInterface still read it.",
    );
  });

  test("with no reader left, the components that remain are named instead", () => {
    const variable = declaredBy(["SensorHub", "produces"], ["Controller", "reads"]);
    expect(removalSentence(variable, "Controller")).toBe(
      "Removes ValueA from Controller; SensorHub still declares it.",
    );
  });

  test("one name is listed without an and", () => {
    const variable = declaredBy(["SensorHub", "produces"], ["Controller", "reads"]);
    expect(removalSentence(variable, "SensorHub")).toBe(
      "Removes ValueA from SensorHub; Controller still reads it.",
    );
  });

  // Not in the brief: with no reader left, its two given tests only ever leave one other
  // declarer behind ("SensorHub still declares it"), which never exercises the plural verb the
  // singular form's own ternary implies exists - left uncovered against the 100% branch gate.
  test("with no reader left, more than one declarer keeps the plural verb", () => {
    const variable = declaredBy(
      ["SensorHub", "produces"],
      ["Pump", "produces"],
      ["Controller", "local"],
    );
    expect(removalSentence(variable, "SensorHub")).toBe(
      "Removes ValueA from SensorHub; Pump and Controller still declare it.",
    );
  });
});

describe("text left in a key's field", () => {
  test("a field with no text typed reads its value, and typed text equal to that reads as taken", () => {
    expect(labelOf("unit", undefined)).toBe("state nothing");
    expect(labelOf("unit", "")).toBe("state nothing");
    expect(labelOf("volatile", "false")).toBe("false");
    expect(keyUnsettled("volatile", {}, { volatile: "false" })).toBe(false);
    expect(keyUnsettled("volatile", { volatile: "false" }, { volatile: "false" })).toBe(false);
  });

  test("typed text that is not what the form states is not taken", () => {
    expect(keyUnsettled("volatile", { volatile: "fal" }, { volatile: "false" })).toBe(true);
    expect(keyUnsettled("unit", { unit: "" }, {})).toBe(true);
  });

  test("a required key nothing states reads empty, not a choice the list never held", () => {
    expect(labelOf("volatile", undefined, true)).toBe("");
    expect(labelOf("volatile", "", true)).toBe("");
    expect(labelOf("volatile", "false", true)).toBe("false");
    expect(keyUnsettled("volatile", { volatile: "" }, {}, true)).toBe(false);
    expect(keyUnsettled("volatile", { volatile: "fal" }, {}, true)).toBe(true);
  });

  test("the form is unsettled while a key it asks for holds such text, and only then", () => {
    expect(formUnsettled("measurement", REPLY, {}, {})).toBe(false);
    expect(formUnsettled("measurement", REPLY, { volatile: "fal" }, {})).toBe(true);
    expect(formUnsettled("measurement", REPLY, { volatile: undefined }, {})).toBe(false);
    // A key this kind does not ask for is not in the form.
    expect(formUnsettled("value_block", REPLY, { datatype: "uin" }, {})).toBe(false);
  });
});

describe("what the form still needs before it can add", () => {
  test("a required key left unstated is named, and the storage as the one choice it is", () => {
    expect(stillNeeded("Pressure", "measurement", {}, {}, REPLY)).toBe(
      "Still needs volatile and datatype or typename.",
    );
  });

  test("a key stated is no longer named", () => {
    expect(stillNeeded("Pressure", "measurement", { volatile: "false" }, {}, REPLY)).toBe(
      "Still needs datatype or typename.",
    );
    expect(
      stillNeeded("Pressure", "measurement", { volatile: "false", typename: '"T"' }, {}, REPLY),
    ).toBeNull();
    expect(
      stillNeeded("Pressure", "measurement", { volatile: "false", datatype: '"uint8"' }, {}, REPLY),
    ).toBeNull();
  });

  test("a kind with no storage key names only its required keys", () => {
    expect(stillNeeded("Block", "value_block", {}, {}, REPLY)).toBe(
      "Still needs dimensions and volatile.",
    );
    expect(
      stillNeeded("Block", "value_block", { dimensions: "[3]", volatile: "true" }, {}, REPLY),
    ).toBeNull();
  });

  test("text left in a field is named too, the form holding Add back for it", () => {
    const stated = { volatile: "false", datatype: '"uint8"' };
    expect(stillNeeded("Pressure", "measurement", stated, { datatype: "uin" }, REPLY)).toBe(
      "Text left in datatype is not taken yet.",
    );
    expect(
      stillNeeded("Pressure", "measurement", {}, { volatile: "tr", datatype: "uin" }, REPLY),
    ).toBe(
      "Still needs volatile and datatype or typename. Text left in volatile and datatype is not taken yet.",
    );
  });

  test("a name read, or no name or kind yet, needs nothing named", () => {
    expect(stillNeeded("ValueC", "", {}, {}, REPLY)).toBeNull();
    expect(stillNeeded("ValueC", "measurement", {}, {}, REPLY)).toBeNull();
    expect(stillNeeded("", "measurement", {}, {}, REPLY)).toBeNull();
    expect(stillNeeded("Pressure", "", {}, {}, REPLY)).toBeNull();
    expect(stillNeeded("Pressure", "mystery", {}, {}, REPLY)).toBeNull();
  });

  test("a value block's rows state its dimensions once every row does", () => {
    expect(statedValues({ volatile: "true" }, ["3", "N"])).toEqual({
      volatile: "true",
      dimensions: '[3,"N"]',
    });
    expect(statedValues({ volatile: "true" }, ["3", ""])).toEqual({ volatile: "true" });
  });
});
