import { describe, expect, it } from "vitest";
import type { ProjectType, TypeReply, TypesReply, VariableKeyOffer } from "../api/types";
import { keyRowsOfType, memberRows, typeRows, typesTitle } from "./projectTypes";

const ROWS: TypesReply = {
  revision: 4,
  types: [
    {
      name: "DriverStatus_t",
      kind: "external",
      description: "The vendor's own",
      uses: 1,
      findings: 0,
    },
    { name: "Sample_t", kind: "struct", description: "One reading", uses: 1, findings: 0 },
    { name: "Temperature_t", kind: "scalar", description: "A temperature", uses: 3, findings: 2 },
  ],
};

describe("the types tab's rows", () => {
  it("says what kind each type is in a word a reader knows", () => {
    expect(typeRows(ROWS).map((row) => row.kindWord)).toEqual(["external", "structure", "scalar"]);
  });

  it("falls back to 'unknown' for a kind the page does not have a word for", () => {
    const drifted: ProjectType = { name: "Old_t", kind: "", description: "", uses: 0, findings: 0 };
    expect(typeRows({ revision: 4, types: [drifted] }).map((row) => row.kindWord)).toEqual([
      "unknown",
    ]);
  });

  it("counts what is there, leaving out the kinds there are none of", () => {
    expect(typesTitle(ROWS)).toBe("3 types · 1 scalar, 1 structure, 1 external");
    expect(typesTitle({ revision: 4, types: [ROWS.types[0] as ProjectType] })).toBe(
      "1 type · 1 external",
    );
    expect(typesTitle({ revision: 4, types: [] })).toBe("This project declares no types");
  });
});

/** One key's offer, with everything it does not say left at its emptiest - a type's own offer
 * carries at most one value and one `carried` (`ddd.variable_keys.offer_for`). */
function offer(key: string, fields: Partial<VariableKeyOffer> = {}): VariableKeyOffer {
  return {
    key,
    carried: [{ allowed: true, required: false }],
    values: [],
    disagrees: false,
    editor: "none",
    choices: [],
    ...fields,
  };
}

function value(raw: string) {
  return { raw, components: [], producer: false };
}

const DATATYPE_OFFER = offer("datatype", { editor: "datatype", values: [value('"float32"')] });
const UNIT_OFFER = offer("unit", { editor: "unit", values: [value('"K"')] });
const CONVERSION_OFFER = offer("conversion");
const LIMITS_OFFER = offer("limits", { editor: "limits" });

const SCALAR: TypeReply = {
  revision: 4,
  name: "Temperature_t",
  kind: "scalar",
  file: "C:/work/demo/types.ddd.json",
  pointer: "types[2]",
  description: "A temperature",
  header: null,
  keys: [DATATYPE_OFFER, UNIT_OFFER, CONVERSION_OFFER, LIMITS_OFFER],
  uses: [],
  members: [],
  findings: [],
};

const STRUCT: TypeReply = {
  revision: 4,
  name: "Sample_t",
  kind: "struct",
  file: "C:/work/demo/types.ddd.json",
  pointer: "types[1]",
  description: "One reading",
  header: null,
  keys: [],
  uses: [],
  members: [
    {
      name: "readings",
      member: "value",
      typename: "Temperature_t",
      datatype: null,
      unit: null,
      bits: null,
      dimensions: ["8", "2"],
    },
    {
      name: "status",
      member: "value",
      typename: null,
      datatype: "uint8_t",
      unit: "K",
      bits: null,
      dimensions: [],
    },
    {
      name: "flags",
      member: "bits",
      typename: null,
      datatype: null,
      unit: null,
      bits: 3,
      dimensions: [],
    },
  ],
  findings: [],
};

describe("a type's panel rows", () => {
  it("answers a row per key a scalar fixes, with its label and the value labelOfRaw spells", () => {
    expect(keyRowsOfType(SCALAR)).toEqual([
      { key: "datatype", label: "Datatype", text: "float32", offer: DATATYPE_OFFER },
      { key: "unit", label: "Unit", text: "K", offer: UNIT_OFFER },
      { key: "conversion", label: "Conversion", text: "state nothing", offer: CONVERSION_OFFER },
      { key: "limits", label: "Limits", text: "state nothing", offer: LIMITS_OFFER },
    ]);
  });

  it("answers no keys for a structure", () => {
    expect(keyRowsOfType(STRUCT)).toEqual([]);
  });

  it("renders a structure's members as the panel's columns read them", () => {
    expect(memberRows(STRUCT)).toEqual([
      {
        id: "readings",
        name: "readings",
        member: "value",
        type: "Temperature_t",
        typename: "Temperature_t",
        unit: "",
        bits: "",
        dimensions: "8 × 2",
      },
      {
        id: "status",
        name: "status",
        member: "value",
        type: "uint8_t",
        typename: null,
        unit: "K",
        bits: "",
        dimensions: "",
      },
      {
        id: "flags",
        name: "flags",
        member: "bits",
        type: "",
        typename: null,
        unit: "",
        bits: "3",
        dimensions: "",
      },
    ]);
  });
});
