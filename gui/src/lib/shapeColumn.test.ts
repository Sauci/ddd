import { describe, expect, test } from "vitest";
import { shapeColumn } from "./shapeColumn";

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
