import { describe, expect, test } from "vitest";
import type { ValuesReply } from "../api/types";
import type { TypedCell } from "./objectValues";
import {
  changesSentence,
  commaAsked,
  offerName,
  offerSentence,
  planOffered,
  typedOffer,
  typedPlan,
  withComma,
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

/** ParameterA: a scalar, one cell of 3200 raw - 800 Hz at 0.25 a count. */
const PARAMETER_A: ValuesReply = {
  ...CURVE_A,
  name: "ParameterA",
  kind: "parameter",
  unit: "Hz",
  conversion: { kind: "linear", factor: 0.25, offset: 0 },
  shape: [],
  rows: [[3200]],
  stated: "scalar",
  axes: [],
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

/** WideCurve: CurveA's six cells counted one to one in a uint32, which holds seven digits. */
const WIDE: ValuesReply = {
  ...CURVE_A,
  name: "WideCurve",
  datatype: "uint32",
  conversion: { kind: "identity" },
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
      ambiguous: null,
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
      ambiguous: null,
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
    expect(typedOffer([typed(0, 1, "1;5")], CURVE_A)).toEqual({
      refusal: "'1;5' is not a number",
      changes: null,
      ambiguous: null,
    });
    const big: ValuesReply = { ...CURVE_A, datatype: "uint64", conversion: { kind: "identity" } };
    expect(typedOffer([typed(0, 0, "9007199254740993", false)], big).refusal).toBe(
      "'9007199254740993' is past 2^53, where the page cannot hold every whole number exactly",
    );
  });

  test("among several cells, the one refused is named, and withholds what the others set", () => {
    expect(typedOffer([typed(0, 0, "13"), typed(0, 1, "1;5")], CURVE_A)).toEqual({
      refusal: "element 2 of 'CurveA' is refused: '1;5' is not a number",
      changes: null,
      ambiguous: null,
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
      ambiguous: null,
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
      ambiguous: null,
    });
  });
});

describe("a comma typed into the cells", () => {
  // 15:M9 and 3:M4: a typed cell refused the decimal comma a paste took, so one rule read `1,5`
  // two ways; and a comma that could be either is asked about, with one press, for either.
  const EITHER = "the comma in '1,500' could be a decimal point or a thousands separator";

  test("one that groups no thousands is a decimal point", () => {
    expect(typedOffer([typed(0, 2, "7,25")], CURVE_A)).toEqual({
      refusal: null,
      changes: [{ row: 0, column: 2, raw: 725 }],
      ambiguous: null,
    });
  });

  test("one that could be either withholds the plan, and is the text whose meaning is asked", () => {
    expect(typedOffer([typed(0, 2, "1,500")], CURVE_A)).toEqual({
      refusal: EITHER,
      changes: null,
      ambiguous: "1,500",
    });
  });

  test("among several cells it is named, and is still the one asked about", () => {
    const offer = typedOffer([typed(0, 1, "7"), typed(0, 2, "1,500")], CURVE_A);
    expect(offer.refusal).toBe(`element 3 of 'CurveA' is refused: ${EITHER}`);
    expect(offer.ambiguous).toBe("1,500");
  });

  test("a cell typed beside it whose comma is a decimal point says what it is", () => {
    expect(typedOffer([typed(0, 1, "0,5"), typed(0, 2, "1,500")], CURVE_A).changes).toEqual([
      { row: 0, column: 1, raw: 50 },
      { row: 0, column: 2, raw: 150 },
    ]);
  });

  test("said with one press, each cell asked about takes the meaning, and no other cell does", () => {
    const held = [typed(0, 1, "7"), typed(0, 2, "1,500")];
    const said = withComma(held, CURVE_A, "grouping");
    expect(said).toEqual([typed(0, 1, "7"), { ...typed(0, 2, "1,500"), comma: "grouping" }]);
    expect(typedOffer(said, CURVE_A).changes).toEqual([
      { row: 0, column: 1, raw: 700 },
      { row: 0, column: 2, raw: 150000 },
    ]);
    expect(typedOffer(withComma(held, CURVE_A, "decimal"), CURVE_A).changes).toEqual([
      { row: 0, column: 1, raw: 700 },
      { row: 0, column: 2, raw: 150 },
    ]);
  });

  test("a cell typed again is asked about afresh", () => {
    const said = withComma([typed(0, 2, "1,500")], CURVE_A, "grouping");
    expect(typedOffer(withTyped(said, typed(0, 2, "2,500")), CURVE_A).ambiguous).toBe("2,500");
  });

  test("beside a cell whose commas group thousands it groups them, and nothing is asked (M1)", () => {
    // Fix round 1, M1: the one-press choice is asked only where no other cell decides.
    expect(typedOffer([typed(0, 1, "1,234,567"), typed(0, 2, "1,500")], WIDE)).toEqual({
      refusal: null,
      changes: [
        { row: 0, column: 1, raw: 1234567 },
        { row: 0, column: 2, raw: 1500 },
      ],
      ambiguous: null,
    });
  });

  test("beside cells showing both readings it is asked about, and none is refused for mixing", () => {
    const offer = typedOffer(
      [typed(0, 0, "0,5", false), typed(0, 1, "1,234,567", false), typed(0, 2, "1,500", false)],
      WIDE,
    );
    expect(offer.ambiguous).toBe("1,500");
    expect(offer.refusal).toBe(
      "element 3 of 'WideCurve' is refused: the comma in '1,500' could be a decimal point or a " +
        "thousands separator",
    );
  });

  test("an answer given stands: a cell typed later shows a decimal comma, and it still groups", () => {
    const said = withComma([typed(0, 2, "1,500", false)], WIDE, "grouping");
    expect(typedOffer([typed(0, 0, "0,5", false), ...said], WIDE).changes).toEqual([
      { row: 0, column: 0, raw: 0.5 },
      { row: 0, column: 2, raw: 1500 },
    ]);
  });

  test("a number in another notation is refused, and asks nothing about a comma", () => {
    expect(typedOffer([typed(0, 2, "0x10")], CURVE_A)).toEqual({
      refusal: "'0x10' is not a number in decimal notation",
      changes: null,
      ambiguous: null,
    });
  });
});

describe("a cell typed back to the float32 its file states (fix round 1, M4)", () => {
  // BlockS: a float32 the file spells at double precision, 0.10000000149011612 - 0.1f, as float32
  // data written out by a script spells it - counted at a factor of 0.5.
  const DOUBLE_SPELLED: ValuesReply = {
    ...CURVE_A,
    name: "BlockS",
    kind: "value_block",
    datatype: "float32",
    unit: "",
    conversion: { kind: "linear", factor: 0.5, offset: 0 },
    shape: [2],
    rows: [[0.10000000149011612, 3]],
    axes: [],
  };

  test("offers nothing, in physical or in raw, whatever digits it is typed in", () => {
    // 0.05, what the cell reads in physical, planned 0.1: a change of nothing a float32 holds.
    expect(typedOffer([typed(0, 0, "0.05")], DOUBLE_SPELLED).changes).toEqual([]);
    expect(typedOffer([typed(0, 0, "0.1", false)], DOUBLE_SPELLED).changes).toEqual([]);
    expect(typedOffer([typed(0, 0, "0.10000000149011612", false)], DOUBLE_SPELLED).changes).toEqual(
      [],
    );
  });

  test("and another float32 is a change", () => {
    expect(typedOffer([typed(0, 0, "0.2", false)], DOUBLE_SPELLED).changes).toEqual([
      { row: 0, column: 0, raw: 0.2 },
    ]);
  });

  test("and the sentence of several says each float32 as raw reads it", () => {
    expect(
      changesSentence(
        DOUBLE_SPELLED,
        [
          { row: 0, column: 0, raw: 0.10000000149011612 },
          { row: 0, column: 1, raw: 4 },
        ],
        false,
      ),
    ).toBe("Sets 2 elements of BlockS: element 1 to 0.1; element 2 to 4");
  });

  test("a float64 tells the two doubles apart", () => {
    const double = { ...DOUBLE_SPELLED, datatype: "float64" };
    expect(typedOffer([typed(0, 0, "0.1", false)], double).changes).toEqual([
      { row: 0, column: 0, raw: 0.1 },
    ]);
  });
});

describe("commaAsked", () => {
  test("the typed cells' own text where they hold one, else a pasted block's", () => {
    expect(commaAsked(typedOffer([typed(0, 2, "1,500")], CURVE_A), "9,999")).toBe("1,500");
    expect(commaAsked(typedOffer([typed(0, 2, "7")], CURVE_A), "9,999")).toBeNull();
    expect(commaAsked(null, "1,200")).toBe("1,200");
    expect(commaAsked(null, null)).toBeNull();
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
    expect(offerSentence(CURVE_A, null, true, false)).toBe("Replaces every value of CurveA");
  });

  test("which says where its first row and column were taken for a header (decision 15.1)", () => {
    expect(offerSentence(CURVE_A, null, true, true)).toBe(
      "Replaces every value of CurveA; the first row and column pasted are taken for a header " +
        "and not written",
    );
  });

  test("else what the typed cells set, whatever a table pasted before them held", () => {
    expect(offerSentence(CURVE_A, typedOffer(THREE, CURVE_A), true, true)).toBe(
      "Sets 3 elements of CurveA: element 1 to 13 ms; element 2 to 14 ms; element 3 to 15 ms",
    );
  });

  test("and none while they set nothing, or one of them is refused", () => {
    expect(
      offerSentence(CURVE_A, typedOffer([typed(0, 0, "12")], CURVE_A), true, false),
    ).toBeNull();
    expect(offerSentence(CURVE_A, typedOffer([typed(0, 0, "x")], CURVE_A), true, false)).toBeNull();
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

describe("planOffered", () => {
  test("a plan that changes nothing is no offer", () => {
    // 15:M4: the server answers a plan whose edit leaves its file as it was with no change.
    expect(planOffered({ revision: 1, changes: [] })).toBeNull();
    expect(planOffered(null)).toBeNull();
  });

  test("a plan that changes a file is the offer", () => {
    const plan = {
      revision: 1,
      changes: [{ file: "/a.ddd.json", fingerprint: "f", operations: [], hunks: [] }],
    };
    expect(planOffered(plan)).toBe(plan);
  });
});

describe("a cell the file does not state", () => {
  test("holds no value a cell could be typed back to, as an object stating nothing does not", () => {
    const short: ValuesReply = { ...CURVE_A, rows: [[1200, 900]] };
    expect(typedOffer([typed(0, 4, "0", false)], short).changes).toEqual([
      { row: 0, column: 4, raw: 0 },
    ]);
    expect(typedOffer([typed(0, 1, "900", false)], short).changes).toEqual([]);
  });
});

describe("offerName", () => {
  test("the one cell, the cells, or a pasted table's values", () => {
    expect(offerName(1)).toBe("Set the cell");
    expect(offerName(3)).toBe("Set the cells");
    expect(offerName(0)).toBe("Replace the values");
  });
});

describe("a scalar's one cell", () => {
  const typed = (text: string, physical: boolean): TypedCell => ({
    row: 0,
    column: 0,
    typed: text,
    physical,
  });

  test("typed in physical, it sets the count that reads so", () => {
    expect(typedOffer([typed("1000", true)], PARAMETER_A)).toEqual({
      refusal: null,
      changes: [{ row: 0, column: 0, raw: 4000 }],
      ambiguous: null,
    });
  });

  test("typed back to the file's value it drops out", () => {
    expect(typedOffer([typed("800", true)], PARAMETER_A)).toEqual({
      refusal: null,
      changes: [],
      ambiguous: null,
    });
  });

  test("typed into a scalar stating none, it sets a value the file does not state", () => {
    const none: ValuesReply = { ...PARAMETER_A, stated: "none", rows: [[0]] };
    expect(typedOffer([typed("0", false)], none)).toEqual({
      refusal: null,
      changes: [{ row: 0, column: 0, raw: 0 }],
      ambiguous: null,
    });
  });

  test("text that is no number is refused in the cell's own words", () => {
    expect(typedOffer([typed("lots", true)], PARAMETER_A)).toEqual({
      refusal: "'lots' is not a number",
      changes: null,
      ambiguous: null,
    });
  });

  test("it is planned as one cell at no element, the object's own pointer", () => {
    expect(typedPlan(PARAMETER_A, [{ row: 0, column: 0, raw: 4000 }])).toEqual({
      cell: { row: 0, column: 0, at: "", raw: 4000 },
    });
  });

  test("its sentence names the value, with its unit", () => {
    expect(changesSentence(PARAMETER_A, [{ row: 0, column: 0, raw: 4000 }], true)).toBe(
      "Sets the value of ParameterA to 1000 Hz",
    );
  });
});
