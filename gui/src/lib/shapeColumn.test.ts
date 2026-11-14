import { describe, expect, test } from "vitest";
import { shapeColumn, typeKinds } from "./shapeColumn";

describe("shapeColumn", () => {
  test("a curve, a map and an axis read their own kind and are offered, whatever they name", () => {
    for (const kind of ["curve", "map", "axis"]) {
      expect(shapeColumn(kind, [], undefined, undefined)).toEqual({ text: kind, offered: true });
      expect(shapeColumn(kind, [], "uint16", [1, 2])).toEqual({ text: kind, offered: true });
    }
  });

  test("dimensions are spelled as the file spells them", () => {
    expect(shapeColumn("value_block", [16], "uint8", undefined)).toEqual({
      text: "16",
      offered: true,
    });
    expect(shapeColumn("measurement", [4, "CELLS"], "uint8", undefined)).toEqual({
      text: "4 × CELLS",
      offered: true,
    });
  });

  test("a scalar stating its own datatype reads scalar and is offered as a grid of one cell", () => {
    expect(shapeColumn("parameter", [], "uint16", 3200)).toEqual({
      text: "scalar",
      offered: true,
    });
    expect(shapeColumn("measurement", [], "uint8", undefined)).toEqual({
      text: "scalar",
      offered: true,
    });
  });

  test("a scalar naming a type may be a structure, which no grid holds: nothing is said", () => {
    expect(shapeColumn("measurement", [], undefined, undefined)).toEqual({
      text: null,
      offered: false,
    });
  });

  test("dimensions beside a type are plain text, a structure being no numeric table", () => {
    expect(shapeColumn("measurement", [2], undefined, undefined)).toEqual({
      text: "2",
      offered: false,
    });
  });

  test("a text init is no grid, in a scalar's declaration or a shaped one", () => {
    expect(shapeColumn("measurement", [], "uint8", "OFF")).toEqual({
      text: "scalar",
      offered: false,
    });
    expect(shapeColumn("value_block", [16], "uint8", "V1.2.3")).toEqual({
      text: "16",
      offered: false,
    });
  });

  test("more than two dimensions is more than a grid draws", () => {
    expect(shapeColumn("value_block", [2, 3, 4], "uint8", undefined)).toEqual({
      text: "2 × 3 × 4",
      offered: false,
    });
  });
});

describe("a declaration naming a type", () => {
  const kinds = typeKinds([
    { name: "Gain_t", kind: "scalar" },
    { name: "Driver_t", kind: "external" },
    { name: "Pair_t", kind: "struct" },
    { name: "Drifted_t", kind: "" },
  ]);
  const named = (name: string | undefined) => ({ name, kinds });

  test("a scalar naming a scalar type reads scalar and is offered", () => {
    expect(shapeColumn("parameter", [], undefined, 10, named("Gain_t"))).toEqual({
      text: "scalar",
      offered: true,
    });
  });

  test("a value block naming a scalar type keeps its dimensions and becomes a button", () => {
    expect(shapeColumn("value_block", [8], undefined, undefined, named("Gain_t"))).toEqual({
      text: "8",
      offered: true,
    });
  });

  test("a curve or a map naming a scalar type is a table whatever it names", () => {
    expect(shapeColumn("curve", [], undefined, undefined, named("Gain_t"))).toEqual({
      text: "curve",
      offered: true,
    });
  });

  test("a struct, an external type and a drifted entry stay as they are, with no button", () => {
    for (const name of ["Pair_t", "Driver_t", "Drifted_t"]) {
      expect(shapeColumn("measurement", [], undefined, undefined, named(name))).toEqual({
        text: null,
        offered: false,
      });
      expect(shapeColumn("measurement", [4], undefined, undefined, named(name))).toEqual({
        text: "4",
        offered: false,
      });
    }
  });

  test("a name no type bears is unknown: nothing is offered", () => {
    expect(shapeColumn("measurement", [], undefined, undefined, named("Nope_t"))).toEqual({
      text: null,
      offered: false,
    });
  });

  test("while the types are not yet known, nothing is offered for such a row", () => {
    const unknown = { name: "Gain_t", kinds: undefined };
    expect(shapeColumn("parameter", [], undefined, 10, unknown)).toEqual({
      text: null,
      offered: false,
    });
    expect(shapeColumn("value_block", [8], undefined, undefined, unknown)).toEqual({
      text: "8",
      offered: false,
    });
  });

  test("a scalar stating its own datatype needs no type", () => {
    expect(
      shapeColumn("parameter", [], "uint16", 3200, { name: undefined, kinds: undefined }),
    ).toEqual({
      text: "scalar",
      offered: true,
    });
  });
});

describe("typeKinds", () => {
  test("maps each type's name to what it is", () => {
    expect(typeKinds([{ name: "A", kind: "scalar" }]).get("A")).toBe("scalar");
    expect(typeKinds([]).size).toBe(0);
  });
});
