import { describe, expect, test } from "vitest";
import type { DeclarableReply } from "../api/types";
import {
  chosenName,
  declareSentence,
  definitionOf,
  dimensionsRaw,
  keysOf,
  modeOf,
  removalSentence,
  scopesOf,
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

describe("which scopes a name may take", () => {
  test("a listed name's are the server's answer for it", () => {
    expect(scopesOf("ValueC", REPLY)).toEqual(["input"]);
    expect(scopesOf("Orphan", REPLY)).toEqual(["output", "input"]);
  });

  test("a new name may take all three", () => {
    expect(scopesOf("Pressure", REPLY)).toEqual(["output", "input", "local"]);
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

  test("a new name names the kind and the scope", () => {
    expect(declareSentence("Pressure", "measurement", "output", REPLY)).toBe(
      "Declares Pressure, a measurement this component produces.",
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
