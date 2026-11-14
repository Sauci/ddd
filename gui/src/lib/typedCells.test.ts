import { describe, expect, test } from "vitest";
import type { ValuesReply } from "../api/types";
import type { TypedCell } from "./objectValues";
import {
  changesSentence,
  offerName,
  offerSentence,
  typedOffer,
  typedPlan,
  withTyped,
} from "./typedCells";

/** CurveA: one row of six against AxisA, 0.01 ms a count - 12, 9, 8, 7.5, 7 and 6.5 ms. */
const CURVE_A: ValuesReply = {
  revision: 1,
  name: "CurveA",
  kind: "curve",
  datatype: "uint16",
  unit: "ms",
  conversion: { kind: "linear", factor: 0.01, offset: 0 },
  minimum: 0,
  maximum: 655.35,
  shape: [6],
  rows: [[1200, 900, 800, 750, 700, 650]],
  stated: "array",
  axes: [
    {
      position: "axis",
      name: "AxisA",
      unit: "Hz",
      breakpoints: [0, 3200, 6400, 12800, 19200, 32000],
      conversion: { kind: "linear", factor: 0.25, offset: 0 },
    },
  ],
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "Controller",
  file: "/repo/examples/demo/components/controller.ddd.json",
  findings: [],
};

/** MapA: four rows of six, 0.5 % a count. */
const MAP_A: ValuesReply = {
  ...CURVE_A,
  name: "MapA",
  kind: "map",
  datatype: "sint8",
  unit: "%",
  conversion: { kind: "linear", factor: 0.5, offset: 0 },
  minimum: -64,
  maximum: 63.5,
  shape: [4, 6],
  rows: [
    [20, 24, 28, 30, 32, 30],
    [18, 22, 26, 28, 30, 28],
    [12, 16, 20, 22, 24, 22],
    [6, 10, 14, 16, 18, 16],
  ],
};

/** A cell typed into, in physical unless said. */
function typed(row: number, column: number, text: string, physical = true): TypedCell {
  return { row, column, typed: text, physical };
}

/** CurveA's first three elements typed 13, 14 and 15 ms. */
const THREE = [typed(0, 0, "13"), typed(0, 1, "14"), typed(0, 2, "15")];

describe("withTyped", () => {
  test("a cell typed for the first time is held beside the others", () => {
    expect(withTyped([typed(0, 0, "13")], typed(0, 1, "14"))).toEqual([
      typed(0, 0, "13"),
      typed(0, 1, "14"),
    ]);
  });

  test("a cell typed again holds its last text, in the reading it was last typed in", () => {
    const held = [typed(0, 0, "13"), typed(0, 1, "14")];
    expect(withTyped(held, typed(0, 0, "1300", false))).toEqual([
      typed(0, 0, "1300", false),
      typed(0, 1, "14"),
    ]);
  });

  test("the cells are held in the grid's order, row by row, whatever order they were typed in", () => {
    let held: TypedCell[] = [];
    for (const cell of [typed(2, 1, "a"), typed(0, 5, "b"), typed(2, 0, "c"), typed(1, 3, "d")]) {
      held = withTyped(held, cell);
    }
    expect(held.map(({ row, column }) => [row, column])).toEqual([
      [0, 5],
      [1, 3],
      [2, 0],
      [2, 1],
    ]);
  });
});

describe("typedOffer", () => {
  test("three cells typed into CurveA set three elements, each to the count its text comes to", () => {
    expect(typedOffer(THREE, CURVE_A)).toEqual({
      refusal: null,
      changes: [
        { row: 0, column: 0, raw: 1300 },
        { row: 0, column: 1, raw: 1400 },
        { row: 0, column: 2, raw: 1500 },
      ],
    });
  });

  test("a cell typed back to the value its file holds sets nothing", () => {
    expect(typedOffer([typed(0, 0, "12"), typed(0, 1, "14")], CURVE_A).changes).toEqual([
      { row: 0, column: 1, raw: 1400 },
    ]);
    // 12.004 ms is no count of its own, and the count nearest it is the file's 1200.
    expect(typedOffer([typed(0, 0, "12.004")], CURVE_A).changes).toEqual([]);
  });

  test("an emptied cell sets nothing and refuses nothing: nothing has been typed into it yet", () => {
    expect(typedOffer([typed(0, 0, ""), typed(0, 1, " ")], CURVE_A)).toEqual({
      refusal: null,
      changes: [],
    });
  });

  test("each cell is read in the reading it was typed in, whatever the grid is in now", () => {
    expect(typedOffer([typed(0, 0, "13"), typed(0, 1, "13", false)], CURVE_A).changes).toEqual([
      { row: 0, column: 0, raw: 1300 },
      { row: 0, column: 1, raw: 13 },
    ]);
  });

  test("an object stating nothing holds no value a cell could be typed back to", () => {
    const none: ValuesReply = { ...CURVE_A, stated: "none", rows: [[0, 0, 0, 0, 0, 0]] };
    expect(typedOffer([typed(0, 3, "0")], none).changes).toEqual([{ row: 0, column: 3, raw: 0 }]);
  });

  test("nor does a row too short to reach the cell", () => {
    const short: ValuesReply = { ...CURVE_A, rows: [[1200, 900]] };
    expect(typedOffer([typed(0, 4, "0")], short).changes).toEqual([{ row: 0, column: 4, raw: 0 }]);
  });

  test("an object stated once holds that one value at every cell", () => {
    const once: ValuesReply = {
      ...CURVE_A,
      stated: "scalar",
      rows: [[800, 800, 800, 800, 800, 800]],
    };
    expect(typedOffer([typed(0, 2, "8"), typed(0, 3, "9")], once).changes).toEqual([
      { row: 0, column: 3, raw: 900 },
    ]);
  });

  test("one cell typed alone is refused in its own words", () => {
    expect(typedOffer([typed(0, 1, "1,5")], CURVE_A)).toEqual({
      refusal: "'1,5' is not a number",
      changes: null,
    });
    const big: ValuesReply = { ...CURVE_A, datatype: "uint64", conversion: { kind: "identity" } };
    expect(typedOffer([typed(0, 0, "9007199254740993", false)], big).refusal).toBe(
      "'9007199254740993' is past 2^53, where the page cannot hold every whole number exactly",
    );
  });

  test("among several cells, the one refused is named, and withholds what the others set", () => {
    expect(typedOffer([typed(0, 0, "13"), typed(0, 1, "1,5")], CURVE_A)).toEqual({
      refusal: "element 2 of 'CurveA' is refused: '1,5' is not a number",
      changes: null,
    });
    expect(typedOffer([typed(1, 3, "x"), typed(2, 0, "5")], MAP_A).refusal).toBe(
      "element 2, 4 of 'MapA' is refused: 'x' is not a number",
    );
  });

  test("an emptied cell beside a refused one makes it one of several, and it is named", () => {
    expect(typedOffer([typed(0, 0, ""), typed(0, 1, "x")], CURVE_A).refusal).toBe(
      "element 2 of 'CurveA' is refused: 'x' is not a number",
    );
  });

  test("several refused are each named with their own reason, five of them, then how many more", () => {
    expect(typedOffer([typed(0, 0, "a"), typed(0, 1, "13"), typed(0, 2, "b")], CURVE_A)).toEqual({
      refusal:
        "2 elements of 'CurveA' are refused: element 1 because 'a' is not a number; " +
        "element 3 because 'b' is not a number",
      changes: null,
    });
    const seven = [0, 1, 2, 3, 4, 5].map((column) => typed(1, column, `x${column}`));
    expect(typedOffer([...seven, typed(2, 0, "y")], MAP_A).refusal).toBe(
      "7 elements of 'MapA' are refused: element 2, 1 because 'x0' is not a number; " +
        "element 2, 2 because 'x1' is not a number; element 2, 3 because 'x2' is not a number; " +
        "element 2, 4 because 'x3' is not a number; element 2, 5 because 'x4' is not a number; " +
        "and 2 more",
    );
  });

  test("a cell past the end of the object's shape has no element to set", () => {
    // An axis of seven breakpoints over a curve of six draws a seventh column.
    expect(typedOffer([typed(0, 6, "1")], CURVE_A).refusal).toBe(
      "'[6]' is past the end of this object",
    );
    expect(typedOffer([typed(0, 0, "13"), typed(4, 0, "1")], MAP_A).refusal).toBe(
      "element 5, 1 of 'MapA' is refused: '[4][0]' is past the end of this object",
    );
  });

  test("an emptied cell past the end of the shape is nothing typed either", () => {
    expect(typedOffer([typed(0, 6, ""), typed(0, 0, "13")], CURVE_A)).toEqual({
      refusal: null,
      changes: [{ row: 0, column: 0, raw: 1300 }],
    });
  });
});

describe("changesSentence", () => {
  test("one element set is said as one cell's own change", () => {
    expect(changesSentence(CURVE_A, [{ row: 0, column: 1, raw: 1450 }], true)).toBe(
      "Sets element 2 of CurveA to 14.5 ms",
    );
  });

  test("several are each named with what they are set to, in physical with the unit", () => {
    const changes = typedOffer(THREE, CURVE_A).changes ?? [];
    expect(changesSentence(CURVE_A, changes, true)).toBe(
      "Sets 3 elements of CurveA: element 1 to 13 ms; element 2 to 14 ms; element 3 to 15 ms",
    );
  });

  test("in raw, as the counts", () => {
    const changes = typedOffer(THREE, CURVE_A).changes ?? [];
    expect(changesSentence(CURVE_A, changes, false)).toBe(
      "Sets 3 elements of CurveA: element 1 to 1300; element 2 to 1400; element 3 to 1500",
    );
  });

  test("a map's elements, named with a comma of their own, are parted by semicolons", () => {
    const changes = [
      { row: 0, column: 1, raw: 30 },
      { row: 2, column: 3, raw: -4 },
    ];
    expect(changesSentence(MAP_A, changes, true)).toBe(
      "Sets 2 elements of MapA: element 1, 2 to 15 %; element 3, 4 to -2 %",
    );
  });

  test("five are named, then how many more", () => {
    const changes = [0, 1, 2, 3, 4, 5].map((column) => ({ row: 0, column, raw: 100 * column }));
    expect(changesSentence(CURVE_A, changes, false)).toBe(
      "Sets 6 elements of CurveA: element 1 to 0; element 2 to 100; element 3 to 200; " +
        "element 4 to 300; element 5 to 400; and 1 more",
    );
  });
});

describe("offerSentence", () => {
  test("where no cell is typed into, the sentence is a pasted table's", () => {
    expect(offerSentence(CURVE_A, null, true)).toBe("Replaces every value of CurveA");
  });

  test("else what the typed cells set", () => {
    expect(offerSentence(CURVE_A, typedOffer(THREE, CURVE_A), true)).toBe(
      "Sets 3 elements of CurveA: element 1 to 13 ms; element 2 to 14 ms; element 3 to 15 ms",
    );
  });

  test("and none while they set nothing, or one of them is refused", () => {
    expect(offerSentence(CURVE_A, typedOffer([typed(0, 0, "12")], CURVE_A), true)).toBeNull();
    expect(offerSentence(CURVE_A, typedOffer([typed(0, 0, "x")], CURVE_A), true)).toBeNull();
  });
});

describe("typedPlan", () => {
  test("nothing to set asks for nothing", () => {
    expect(typedPlan(CURVE_A, [])).toBeNull();
  });

  test("one element set is asked for as that cell, at its own pointer", () => {
    expect(typedPlan(MAP_A, [{ row: 1, column: 3, raw: 99 }])).toEqual({
      cell: { row: 1, column: 3, at: "[1][3]", raw: 99 },
    });
  });

  test("several are asked for as those cells alone, each at its own pointer", () => {
    const changes = typedOffer(THREE, CURVE_A).changes ?? [];
    expect(typedPlan(CURVE_A, changes)).toEqual({
      cells: [
        { row: 0, column: 0, at: "[0]", raw: 1300 },
        { row: 0, column: 1, at: "[1]", raw: 1400 },
        { row: 0, column: 2, at: "[2]", raw: 1500 },
      ],
    });
    expect(
      typedPlan(MAP_A, [
        { row: 0, column: 1, raw: 30 },
        { row: 3, column: 5, raw: -4 },
      ]),
    ).toEqual({
      cells: [
        { row: 0, column: 1, at: "[0][1]", raw: 30 },
        { row: 3, column: 5, at: "[3][5]", raw: -4 },
      ],
    });
  });

  test("two cells of a block of more than ten thousand counts are those two cells alone", () => {
    // Its whole table needs more characters than one address holds: 10240 counts of four
    // digits, each with the three of the comma before it.
    const long: ValuesReply = {
      ...CURVE_A,
      name: "Long",
      conversion: { kind: "identity" },
      shape: [10240],
      rows: [Array.from({ length: 10240 }, () => 1000)],
      axes: [],
    };
    expect(
      typedPlan(long, [
        { row: 0, column: 3, raw: 7 },
        { row: 0, column: 9000, raw: 8 },
      ]),
    ).toEqual({
      cells: [
        { row: 0, column: 3, at: "[3]", raw: 7 },
        { row: 0, column: 9000, at: "[9000]", raw: 8 },
      ],
    });
  });
});

describe("offerName", () => {
  test("the one cell, the cells, or a pasted table's values", () => {
    expect(offerName(1)).toBe("Set the cell");
    expect(offerName(3)).toBe("Set the cells");
    expect(offerName(0)).toBe("Replace the values");
  });
});
