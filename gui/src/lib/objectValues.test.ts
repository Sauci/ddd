import { describe, expect, test, vi } from "vitest";
import type { ValuesReply } from "../api/types";
import {
  cellAt,
  cellSentence,
  cellText,
  columnAxisLabel,
  columnChars,
  columnHeader,
  cornerLabel,
  drawable,
  elementLabel,
  limitsLine,
  noGridNote,
  pasted,
  pasteHint,
  pasteSentence,
  pastes,
  physicalOf,
  plotDrawn,
  rawOf,
  readOnlyNote,
  rowHeader,
  statedNote,
  type TypedCell,
  typedRaw,
  typedRefusal,
  wanted,
} from "./objectValues";

// Every fixture below is `GET /api/values?name=…` against examples/demo, read verbatim off a
// real answer rather than invented, the same way the objects it draws are real.

/** CurveA: one row against AxisA, a linear conversion on both the object and its axis. */
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

/** MapA: four rows of six, x_axis AxisA and y_axis AxisB, both linear. */
const MAP_A: ValuesReply = {
  revision: 1,
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
  stated: "array",
  axes: [
    {
      position: "x_axis",
      name: "AxisA",
      unit: "Hz",
      breakpoints: [0, 3200, 6400, 12800, 19200, 32000],
      conversion: { kind: "linear", factor: 0.25, offset: 0 },
    },
    {
      position: "y_axis",
      name: "AxisB",
      unit: "%",
      breakpoints: [0, 60, 140, 200],
      conversion: { kind: "linear", factor: 0.5, offset: 0 },
    },
  ],
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "Controller",
  file: "/repo/examples/demo/components/controller.ddd.json",
  findings: [],
};

/** BlockA: one row of eight against no axis at all, and the identity conversion. */
const BLOCK_A: ValuesReply = {
  revision: 1,
  name: "BlockA",
  kind: "value_block",
  datatype: "uint8",
  unit: "",
  conversion: { kind: "identity" },
  minimum: 0,
  maximum: 255,
  shape: [8],
  rows: [[0, 12, 28, 52, 84, 124, 180, 255]],
  stated: "array",
  axes: [],
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "UserInterface",
  file: "/repo/examples/demo/components/user_interface.ddd.json",
  findings: [],
};

/** ValueK: two dimensional, against no axis - the "else indices" arm neither CurveA (one
 * dimensional) nor MapA (an axis on both sides) reaches. */
const VALUE_K: ValuesReply = {
  revision: 1,
  name: "ValueK",
  kind: "measurement",
  datatype: "sint8",
  unit: "",
  conversion: { kind: "identity" },
  minimum: -128,
  maximum: 127,
  shape: [3, 4],
  rows: [
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
  ],
  stated: "array",
  axes: [],
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "EventLogger",
  file: "/repo/examples/demo/subsystems/logging/event_logger.ddd.json",
  findings: [],
};

/** ParameterA: a plain calibration parameter - shapeless, so its one value is a grid of one
 * cell: 3200 raw, which its factor of 0.25 reads as 800 Hz. */
const PARAMETER_A: ValuesReply = {
  revision: 1,
  name: "ParameterA",
  kind: "parameter",
  datatype: "uint16",
  unit: "Hz",
  conversion: { kind: "linear", factor: 0.25, offset: 0 },
  minimum: 500,
  maximum: 1500,
  shape: [],
  rows: [[3200]],
  stated: "scalar",
  axes: [],
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "Controller",
  file: "/repo/examples/demo/components/controller.ddd.json",
  findings: [],
};

/** ValueC: a scalar stating no init, which the startup code zeroes: one cell of 0, unstated. */
const VALUE_C: ValuesReply = {
  ...PARAMETER_A,
  name: "ValueC",
  kind: "measurement",
  rows: [[0]],
  stated: "none",
};

/** A list written for an object of no shape (an `init-invalid` of its own): no value to show,
 * so no cell for one to sit in. */
const VALUE_A: ValuesReply = {
  revision: 1,
  name: "ValueA",
  kind: "measurement",
  datatype: "uint8",
  unit: "%",
  conversion: { kind: "linear", factor: 0.5, offset: 0 },
  minimum: 0,
  maximum: 100,
  shape: [],
  rows: [],
  stated: "scalar",
  axes: [],
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "SensorHub",
  file: "/repo/examples/demo/components/sensor_hub.ddd.json",
  findings: [],
};

/** CurveX over AxisX, an axis stating a size and no init at all: measured on a project of
 * those two declarations alone, which answers the curve's own three numbers and an axis with
 * `breakpoints: []`. `test_an_axis_with_no_init_gives_no_breakpoints` states the intent on the
 * Python side - "the grid degrades to indices, not a crash" - and this is the half that did
 * not: a header of no columns, so a row of no value cells. */
const CURVE_X: ValuesReply = {
  revision: 1,
  name: "CurveX",
  kind: "curve",
  datatype: "uint8",
  unit: "",
  conversion: { kind: "identity" },
  minimum: 0,
  maximum: 255,
  shape: [3],
  rows: [[1, 2, 3]],
  stated: "array",
  axes: [
    {
      position: "axis",
      name: "AxisX",
      unit: "",
      breakpoints: [],
      conversion: { kind: "identity" },
    },
  ],
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "A",
  file: "/repo/a.ddd.json",
  findings: [],
};

/** The same degradation down a map's side: MapA with both its axes' breakpoints taken away,
 * built from the reply above it rather than measured - the way `AReadOnlyGrid` is built from
 * BlockA's own answer - because no example pairs a map with two empty axes. */
const MAP_WITHOUT_BREAKPOINTS: ValuesReply = {
  ...MAP_A,
  axes: MAP_A.axes.map((axis) => ({ ...axis, breakpoints: [] })),
};

/** BlockA made a uint64 block of two whose file holds 9007199254740993 and 18446744073709551615,
 * as the route answers it: each the double nearest it, 2^53 and 2^64 - which no uint64 holds -
 * and the block marked as one the grid cannot show. Built from BlockA's own answer rather than
 * measured, the way `MAP_WITHOUT_BREAKPOINTS` is: no example holds a number past 2^53. */
const BIG: ValuesReply = {
  ...BLOCK_A,
  datatype: "uint64",
  maximum: 2 ** 64,
  shape: [2],
  rows: [[2 ** 53, 2 ** 64]],
  unshown: "BlockA",
  maximum_text: "18446744073709551615",
};

/** SoftwareLabel: a shaped object initialised with text - no grid either, the other way. */
const SOFTWARE_LABEL: ValuesReply = {
  revision: 1,
  name: "SoftwareLabel",
  kind: "value_block",
  datatype: "uint8",
  unit: "",
  conversion: { kind: "string" },
  minimum: 0,
  maximum: 255,
  shape: [16],
  rows: [],
  stated: "text",
  axes: [],
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "Controller",
  file: "/repo/examples/demo/components/controller.ddd.json",
  findings: [],
};

describe("physicalOf", () => {
  test("a linear conversion multiplies and offsets", () => {
    expect(physicalOf(1200, { kind: "linear", factor: 0.01, offset: 0 })).toBe(12);
  });

  test("anything else hands the raw count back", () => {
    expect(physicalOf(1200, { kind: "identity" })).toBe(1200);
  });

  test("a missing factor or offset reads as the identity's own defaults", () => {
    expect(physicalOf(12, { kind: "linear" })).toBe(12);
  });
});

describe("rawOf", () => {
  test("an integer datatype rounds to the nearest whole raw count", () => {
    expect(rawOf(12.004, { kind: "linear", factor: 0.01, offset: 0 }, "uint16")).toBe(1200);
  });

  test("a float datatype keeps the exact raw count", () => {
    expect(rawOf(12.004, { kind: "linear", factor: 0.01, offset: 0 }, "float32")).toBeCloseTo(
      1200.4,
      9,
    );
  });

  test("anything but a linear conversion takes the physical value as the raw one", () => {
    expect(rawOf(84, { kind: "identity" }, "uint8")).toBe(84);
  });
});

describe("columnHeader", () => {
  test("CurveA in physical reads AxisA's breakpoints through AxisA's own conversion", () => {
    expect(columnHeader(CURVE_A, true)).toEqual(["0", "800", "1600", "3200", "4800", "8000"]);
  });

  test("CurveA in raw is AxisA's breakpoints untouched", () => {
    expect(columnHeader(CURVE_A, false)).toEqual(["0", "3200", "6400", "12800", "19200", "32000"]);
  });

  test("MapA reads its x axis, AxisA, and not its y", () => {
    // The x/y assignment itself, in words rather than in a picture: MapA's rows are AxisB's
    // readings (below) and its columns AxisA's - swapping the two would draw a plausible grid
    // with every number in the wrong cell, and only this and the row test say which is which.
    expect(columnHeader(MAP_A, true)).toEqual(["0", "800", "1600", "3200", "4800", "8000"]);
  });

  test("BlockA, against no axis, is the column indices", () => {
    expect(columnHeader(BLOCK_A, true)).toEqual(["0", "1", "2", "3", "4", "5", "6", "7"]);
  });

  test("an axis that states no breakpoints falls back to the indices", () => {
    // Not `[]`: a header of no columns draws a row of no value cells, so the curve's three
    // numbers would be invisible and uneditable.
    expect(columnHeader(CURVE_X, true)).toEqual(["0", "1", "2"]);
  });

  test("an object with no cell draws no columns at all", () => {
    expect(columnHeader(VALUE_A, true)).toEqual([]);
  });

  test("a scalar is one column, its value", () => {
    expect(columnHeader(PARAMETER_A, true)).toEqual(["Value"]);
    expect(columnHeader(PARAMETER_A, false)).toEqual(["Value"]);
  });
});

describe("rowHeader", () => {
  test("MapA in physical is AxisB's breakpoints through AxisB's own conversion", () => {
    expect(rowHeader(MAP_A, true)).toEqual(["0", "30", "70", "100"]);
  });

  test("CurveA, one row and no y axis, is labelled with the object itself", () => {
    // Spec 5.2's own sketch: `CurveA (ms)` beside its values, under `AxisA (Hz)` above them.
    expect(rowHeader(CURVE_A, true)).toEqual(["CurveA (ms)"]);
  });

  test("in raw the row keeps the object's name and drops its unit", () => {
    // The cells there hold 1200, 900, 800 - counts, not milliseconds - so `(ms)` beside them
    // would be a label the numbers under it contradict.
    expect(rowHeader(CURVE_A, false)).toEqual(["CurveA"]);
  });

  test("an object with no unit is labelled by its bare name", () => {
    expect(rowHeader(BLOCK_A, true)).toEqual(["BlockA"]);
  });

  test("ValueK, two dimensional against no axis, is the row indices", () => {
    expect(rowHeader(VALUE_K, true)).toEqual(["0", "1", "2"]);
  });

  test("a y axis that states no breakpoints falls back to the row indices", () => {
    expect(rowHeader(MAP_WITHOUT_BREAKPOINTS, true)).toEqual(["0", "1", "2", "3"]);
  });

  test("an object with no cell draws no rows at all", () => {
    expect(rowHeader(VALUE_A, true)).toEqual([]);
  });

  test("a scalar is one row, labelled with the object itself as a single row is", () => {
    expect(rowHeader(PARAMETER_A, true)).toEqual(["ParameterA (Hz)"]);
    expect(rowHeader(PARAMETER_A, false)).toEqual(["ParameterA"]);
  });
});

describe("cornerLabel", () => {
  test("a curve names the axis its columns are laid against", () => {
    expect(cornerLabel(CURVE_A, true)).toBe("AxisA (Hz)");
  });

  test("in raw it keeps the axis's name and drops its unit", () => {
    // The header under it reads 0, 3200, 6400 - AxisA's own counts, which are not Hz.
    expect(cornerLabel(CURVE_A, false)).toBe("AxisA");
  });

  test("a map names the axis its rows are laid against", () => {
    // Spec 5.2's map sketch: AxisB (%) down the side, AxisA (Hz) across the top - the one
    // reading that tells a reader which unit belongs to which edge.
    expect(cornerLabel(MAP_A, true)).toBe("AxisB (%)");
  });

  test("a grid laid against indices alone names nothing", () => {
    expect(cornerLabel(BLOCK_A, true)).toBe("");
  });

  test("a two dimensional grid with no y axis names nothing either", () => {
    expect(cornerLabel(VALUE_K, true)).toBe("");
  });
});

describe("columnAxisLabel", () => {
  test("a map names its x axis above the columns", () => {
    expect(columnAxisLabel(MAP_A, true)).toBe("AxisA (Hz)");
  });

  test("in raw that name carries no unit either", () => {
    expect(columnAxisLabel(MAP_A, false)).toBe("AxisA");
  });

  test("a single row says nothing above it - its own corner names the axis", () => {
    expect(columnAxisLabel(CURVE_A, true)).toBe("");
  });

  test("a two dimensional grid with no x axis says nothing", () => {
    expect(columnAxisLabel(VALUE_K, true)).toBe("");
  });
});

describe("typedRaw", () => {
  test("a decimal comma is not a number, rather than the whole part of one", () => {
    // `parseFloat("1,5")` is 1: half the world's decimal separator, silently planning a write
    // of a value the reader did not type.
    expect(typedRaw("1,5", BLOCK_A, false)).toBeNull();
  });

  test("a numeric prefix is not a number either", () => {
    expect(typedRaw("7abc", BLOCK_A, false)).toBeNull();
  });

  test("an empty cell is nothing typed, not zero", () => {
    expect(typedRaw("  ", BLOCK_A, false)).toBeNull();
  });

  test("a number with space around it is that number", () => {
    expect(typedRaw(" 12 ", BLOCK_A, false)).toBe(12);
  });

  test("a fraction in raw is the fraction, for the server to weigh against the datatype", () => {
    expect(typedRaw("7.5", BLOCK_A, false)).toBe(7.5);
  });

  test("in physical it is the raw count the conversion comes to, rounded for an integer", () => {
    expect(typedRaw("12.004", CURVE_A, true)).toBe(1200);
  });
});

describe("typedRefusal", () => {
  test("what is not wholly a number is refused in the grid's own voice", () => {
    expect(typedRefusal("1,5", BLOCK_A)).toBe("'1,5' is not a number");
  });

  test("a number is not refused", () => {
    expect(typedRefusal("7.5", BLOCK_A)).toBeNull();
  });

  test("an empty cell is not refused - nothing has been typed yet", () => {
    expect(typedRefusal("", BLOCK_A)).toBeNull();
  });
});

describe("a number a double cannot hold", () => {
  // Past 2^53 a double, the number the page holds, no longer holds every whole number, and
  // `Number` reads the others as a double beside them, saying nothing. Planned from what it
  // read, 9007199254740993 was written as 9007199254740992; the 64 bit mask
  // 0x8000000000000001, read as 2^63, was written as 9223372036854776000, the shortest decimal
  // of that double, which is 0x80000000000000C0 - its low bit cleared and two others set; and
  // 18446744073709551615, the most a uint64 holds, read as 2^64, was refused as a number that
  // does not fit, though nobody typed it. Below 2^53 a double holds every whole number, but from
  // 2^51 it no longer holds every fraction: 4503599627370496.5 read as 4503599627370496, and
  // planned so for an integer.
  const INEXACT = "where the page cannot hold every whole number exactly";
  const FRACTION = "is not a whole number, and the page cannot hold its fraction";
  const UINT64 = BIG;
  const SINT64: ValuesReply = { ...BIG, datatype: "sint64" };
  const FLOAT64: ValuesReply = { ...BIG, datatype: "float64", unshown: null };
  const FLOAT32: ValuesReply = { ...BIG, datatype: "float32", unshown: null };

  test.each([
    // An integer cell takes a whole number up to 2^53, as it is written - 2^53 itself the
    // server refuses a 64 bit integer, which cannot tell it from 2^53 + 1 rounded.
    { text: "9007199254740991", cell: UINT64, raw: 9007199254740991, refused: null },
    { text: "9007199254740992", cell: UINT64, raw: 2 ** 53, refused: null },
    { text: "-9007199254740992", cell: SINT64, raw: -(2 ** 53), refused: null },
    { text: "0x1F", cell: UINT64, raw: 31, refused: null },
    // `Infinity` is read as the double it is, on no side of 2^53: no whole number at all, and
    // the server's range refuses it.
    { text: "Infinity", cell: UINT64, raw: Number.POSITIVE_INFINITY, refused: null },
    // Past it, whichever side, in every spelling `Number` reads, the space around it included.
    {
      text: "9007199254740993",
      cell: UINT64,
      raw: null,
      refused: `'9007199254740993' is past 2^53, ${INEXACT}`,
    },
    {
      text: "-9007199254740993",
      cell: SINT64,
      raw: null,
      refused: `'-9007199254740993' is past -2^53, ${INEXACT}`,
    },
    {
      text: "0x8000000000000001",
      cell: UINT64,
      raw: null,
      refused: `'0x8000000000000001' is past 2^53, ${INEXACT}`,
    },
    {
      text: "18446744073709551615",
      cell: UINT64,
      raw: null,
      refused: `'18446744073709551615' is past 2^53, ${INEXACT}`,
    },
    {
      text: "0x20000000000001",
      cell: UINT64,
      raw: null,
      refused: `'0x20000000000001' is past 2^53, ${INEXACT}`,
    },
    {
      text: `0b1${"0".repeat(52)}1`,
      cell: UINT64,
      raw: null,
      refused: `'0b1${"0".repeat(52)}1' is past 2^53, ${INEXACT}`,
    },
    {
      text: "0o400000000000000001",
      cell: UINT64,
      raw: null,
      refused: `'0o400000000000000001' is past 2^53, ${INEXACT}`,
    },
    {
      text: " 9007199254740993 ",
      cell: UINT64,
      raw: null,
      refused: `' 9007199254740993 ' is past 2^53, ${INEXACT}`,
    },
    {
      text: "9007199254740993.0",
      cell: UINT64,
      raw: null,
      refused: `'9007199254740993.0' is past 2^53, ${INEXACT}`,
    },
    {
      text: "1.8446744073709551615e19",
      cell: UINT64,
      raw: null,
      refused: `'1.8446744073709551615e19' is past 2^53, ${INEXACT}`,
    },
    { text: "1e19", cell: UINT64, raw: null, refused: `'1e19' is past 2^53, ${INEXACT}` },
    {
      text: "9007199254740992.5",
      cell: UINT64,
      raw: null,
      refused: `'9007199254740992.5' is past 2^53, ${INEXACT}`,
    },
    {
      text: "-9.007199254740993e15",
      cell: SINT64,
      raw: null,
      refused: `'-9.007199254740993e15' is past -2^53, ${INEXACT}`,
    },
    // A fraction the double cannot hold is no whole number, rather than the one it reads as; a
    // fraction it holds is the fraction, which the server refuses an integer in raw.
    {
      text: "4503599627370496.5",
      cell: UINT64,
      raw: null,
      refused: `'4503599627370496.5' ${FRACTION}`,
    },
    {
      text: "2251799813685248.25",
      cell: UINT64,
      raw: null,
      refused: `'2251799813685248.25' ${FRACTION}`,
    },
    { text: "2251799813685248.5", cell: UINT64, raw: 2251799813685248.5, refused: null },
    // A float cell takes the double whatever the spelling: FLT_MAX is a whole number past 2^53
    // too, and the double is what the float holds.
    { text: "9007199254740993", cell: FLOAT64, raw: 2 ** 53, refused: null },
    { text: "10000000000000000000", cell: FLOAT64, raw: 1e19, refused: null },
    { text: "1e19", cell: FLOAT64, raw: 1e19, refused: null },
    { text: "4503599627370496.5", cell: FLOAT64, raw: 4503599627370496, refused: null },
    {
      text: "3.4028234663852886e38",
      cell: FLOAT32,
      raw: 3.4028234663852886e38,
      refused: null,
    },
  ])("'$text' in a $cell.datatype cell", ({ text, cell, raw, refused }) => {
    expect(typedRaw(text, cell, false)).toBe(raw);
    expect(typedRefusal(text, cell)).toBe(refused);
  });

  test("a pasted block holding one is refused in the same words, and plans nothing", () => {
    expect(pasted("9007199254740993\t9007199254740995", BIG, false)).toEqual({
      rows: null,
      refusal: `'9007199254740993' is past 2^53, ${INEXACT}`,
    });
  });

  test("so is a block holding one in the cell a header row and column leave", () => {
    const text = ["\t0\t1", `BlockA\t1\t18446744073709551615`].join("\n");
    expect(pasted(text, BIG, true).refusal).toBe(`'18446744073709551615' is past 2^53, ${INEXACT}`);
  });

  test("and a pasted fraction an integer cell would lose", () => {
    expect(pasted("1\t4503599627370496.5", BIG, false).refusal).toBe(
      `'4503599627370496.5' ${FRACTION}`,
    );
  });

  test("a pasted block up to 2^53 is read as it is written", () => {
    expect(pasted("9007199254740991\t-9007199254740992", SINT64, false).rows).toEqual([
      [9007199254740991, -(2 ** 53)],
    ]);
  });

  test("a float block takes a whole number past 2^53 as the double it is", () => {
    expect(pasted("9007199254740993\t10000000000000000000", FLOAT64, false).rows).toEqual([
      [2 ** 53, 1e19],
    ]);
  });
});

describe("the work a pasted block costs", () => {
  // A 64 by 64 map's 4,096 cells, counted rather than timed: each cell is read once, and only a
  // cell of sixteen whole digits, the one length that falls either side of 2^53, asks `BigInt` -
  // which throws for a fraction, so asking it of every cell made a block of fractions cost about
  // a hundred times what reading their numbers does.
  const MAP_64: ValuesReply = {
    ...MAP_A,
    datatype: "uint64",
    conversion: { kind: "identity" },
    shape: [64, 64],
    axes: [],
  };
  const block = (cell: (index: number) => string) =>
    Array.from({ length: 64 }, (_, row) =>
      Array.from({ length: 64 }, (_, column) => cell(row * 64 + column)).join("\t"),
    ).join("\n");

  test("a block of fractions asks BigInt nothing", () => {
    const asked = vi.spyOn(globalThis, "BigInt");
    try {
      const read = pasted(
        block((index) => (index * 0.37).toFixed(2)),
        MAP_64,
        false,
      );
      expect(read.rows?.flat()).toHaveLength(4096);
      expect(asked).not.toHaveBeenCalled();
    } finally {
      asked.mockRestore();
    }
  });

  test("a block of sixteen digit numbers asks it once a cell", () => {
    const asked = vi.spyOn(globalThis, "BigInt");
    try {
      const read = pasted(
        block(() => "9007199254740991"),
        MAP_64,
        false,
      );
      expect(read.rows?.flat()).toHaveLength(4096);
      expect(asked).toHaveBeenCalledTimes(4096);
    } finally {
      asked.mockRestore();
    }
  });
});

describe("limitsLine", () => {
  test("the limits as the doubles they cross as, where those show them", () => {
    expect(limitsLine(CURVE_A)).toBe("0 … 655.35");
  });

  test("a limit the double cannot carry in its own digits, not the double's", () => {
    // 2^64 - 1, the most a uint64 holds, crosses as 2^64 and printed as 18446744073709552000,
    // which none holds, over every 64 bit values page.
    expect(limitsLine(BIG)).toBe("0 … 18446744073709551615");
  });

  test("on either side", () => {
    const sint64: ValuesReply = {
      ...BIG,
      datatype: "sint64",
      minimum: -(2 ** 63),
      maximum: 2 ** 63,
      minimum_text: "-9223372036854775808",
      maximum_text: "9223372036854775807",
    };
    expect(limitsLine(sint64)).toBe("-9223372036854775808 … 9223372036854775807");
  });
});

describe("noGridNote", () => {
  const AT_OR_PAST =
    "holds a whole number at or past ±2^53, where the page cannot hold every whole number " +
    "exactly, so the grid cannot show it";

  test("a grid of numbers the page holds has nothing to say", () => {
    expect(noGridNote(CURVE_A)).toBeNull();
  });

  test("text is no grid at all", () => {
    expect(noGridNote(SOFTWARE_LABEL)).toBe(
      "'SoftwareLabel' is initialised with text, not with a grid",
    );
  });

  test("a block the route marks is not drawn as other numbers", () => {
    expect(noGridNote(BIG)).toBe(`'BlockA' ${AT_OR_PAST}`);
  });

  test("an axis it marks is named, whichever object's grid lies against it", () => {
    expect(noGridNote({ ...CURVE_A, unshown: "AxisA" })).toBe(`'AxisA' ${AT_OR_PAST}`);
  });

  test("text is said first: it is no grid whatever it holds", () => {
    expect(noGridNote({ ...SOFTWARE_LABEL, unshown: "SoftwareLabel" })).toBe(
      "'SoftwareLabel' is initialised with text, not with a grid",
    );
  });
});

describe("readOnlyNote", () => {
  test("a grid with a producing file has nothing to say", () => {
    expect(readOnlyNote(CURVE_A)).toBeNull();
  });

  test("a name nothing produces has no declaration to write into", () => {
    // `owner` is null only where nothing produces it at all, which
    // `test_an_object_nothing_produces_has_no_file_or_pointer` pins on the Python side.
    expect(readOnlyNote({ ...BLOCK_A, file: null, owner: null })).toBe(
      "nothing produces 'BlockA', so it has no values to set",
    );
  });

  test("a name more than one declaration produces has no single one", () => {
    // The other cause of the same read-only grid, and `set_cell`'s own second sentence: the
    // owner is named - these are its numbers - and there is still no file to write into.
    expect(readOnlyNote({ ...BLOCK_A, file: null })).toBe(
      "'BlockA' is produced in more than one place, so there is no one file to set it in",
    );
  });
});

describe("cellAt", () => {
  test("a scalar is the whole object, named by no element at all", () => {
    expect(cellAt(0, 0, [])).toBe("");
  });

  test("a single row names its element by the column alone", () => {
    expect(cellAt(0, 2, [6])).toBe("[2]");
  });

  test("a map names its row and its column", () => {
    expect(cellAt(1, 3, [4, 6])).toBe("[1][3]");
  });
});

describe("elementLabel", () => {
  test("a scalar's cell is its value", () => {
    expect(elementLabel(0, 0, [])).toBe("the value");
  });

  test("a single row names its element by the column alone, one-based", () => {
    expect(elementLabel(0, 2, [6])).toBe("element 3");
  });

  test("a map names its row and its column, one-based", () => {
    expect(elementLabel(1, 3, [4, 6])).toBe("element 2, 4");
  });
});

describe("cellSentence", () => {
  test("a scalar's value, in physical with its own unit", () => {
    expect(cellSentence(PARAMETER_A, 0, 0, 4000, true)).toBe(
      "Sets the value of ParameterA to 1000 Hz",
    );
  });

  test("a scalar's value, in raw", () => {
    expect(cellSentence(PARAMETER_A, 0, 0, 4000, false)).toBe(
      "Sets the value of ParameterA to 4000",
    );
  });

  test("a curve's cell, one-based, in physical", () => {
    // The same [2] and 750 the client tests plan onto CurveA: 750 raw ms-counts is 7.5 ms.
    expect(cellSentence(CURVE_A, 0, 2, 750, true)).toBe("Sets element 3 of CurveA to 7.5 ms");
  });

  test("a map's cell names its row and its column, one-based, in physical", () => {
    // [1][3] one-based is "element 2, 4"; 99 is the raw Task 3's own endpoint test plans onto
    // that cell (tests/test_gui_api.py:2697), and 49.5 % is what it reads through MapA's ×0.5
    // conversion - so the page's sentence and the server's test name the same cell change.
    expect(cellSentence(MAP_A, 1, 3, 99, true)).toBe("Sets element 2, 4 of MapA to 49.5 %");
  });

  test("in raw, the count is written as typed, with no unit", () => {
    expect(cellSentence(CURVE_A, 0, 2, 750, false)).toBe("Sets element 3 of CurveA to 750");
  });

  test("an object with no unit carries none in its sentence either", () => {
    expect(cellSentence(BLOCK_A, 0, 4, 84, true)).toBe("Sets element 5 of BlockA to 84");
  });
});

/** A uint32 block holding numbers of nine, ten, two and seven digits. */
const WIDE_WHOLE: ValuesReply = {
  ...BLOCK_A,
  datatype: "uint32",
  maximum: 4294967295,
  shape: [4],
  rows: [[123456789, 4000000000, 42, 1000000]],
};

/** A float64 block whose numbers are spelled in fifteen, eleven and nine characters. */
const WIDE_FRACTIONS: ValuesReply = {
  ...BLOCK_A,
  datatype: "float64",
  shape: [3],
  rows: [[0.1234567890123, 1234567.125, -0.000001]],
};

/** MapA counted in steps of 0.125 %, its first cell 83 counts: 10.375 % in physical. */
const EIGHTHS: ValuesReply = {
  ...MAP_A,
  conversion: { kind: "linear", factor: 0.125, offset: 0 },
  rows: [[83, 24, 28, 30, 32, 30], ...MAP_A.rows.slice(1)],
};

/** A cell typed into, in physical unless said. */
function typedCell(row: number, column: number, typed: string, physical = true): TypedCell {
  return { row, column, typed, physical };
}

describe("cellText", () => {
  test("a cell shows what its count reads as in physical, and the count itself in raw", () => {
    expect(cellText(CURVE_A, [], 0, 2, true)).toBe("8");
    expect(cellText(CURVE_A, [], 0, 2, false)).toBe("800");
  });

  test("a cell typed into shows what was typed, in the reading it was typed in, and no other does", () => {
    const typed = [typedCell(0, 2, "7.25")];
    expect(cellText(CURVE_A, typed, 0, 2, true)).toBe("7.25");
    expect(cellText(CURVE_A, typed, 0, 1, true)).toBe("9");
    expect(cellText(MAP_A, [typedCell(1, 3, "7.25", false)], 1, 3, false)).toBe("7.25");
    expect(cellText(MAP_A, [typedCell(1, 3, "7.25", false)], 3, 1, false)).toBe("10");
  });

  test("in the other reading, it shows the count its text comes to, read as the grid now reads", () => {
    // 7.25 ms typed comes to 725 counts; 13 counts typed read 0.13 ms.
    expect(cellText(CURVE_A, [typedCell(0, 2, "7.25")], 0, 2, false)).toBe("725");
    expect(cellText(CURVE_A, [typedCell(0, 2, "13", false)], 0, 2, true)).toBe("0.13");
    // 5.1 % comes to the 10 counts a sint8 map can hold, which read 5 %.
    expect(cellText(MAP_A, [typedCell(0, 1, "5.1")], 0, 1, false)).toBe("10");
  });

  test("text that comes to no count is shown as typed in either reading", () => {
    expect(cellText(CURVE_A, [typedCell(0, 2, "1,5")], 0, 2, false)).toBe("1,5");
    expect(cellText(CURVE_A, [typedCell(0, 2, "")], 0, 2, false)).toBe("");
  });

  test("a cell its row does not reach reads zero, as the startup code makes it", () => {
    expect(cellText({ ...CURVE_A, rows: [[1200, 900]] }, [], 0, 4, false)).toBe("0");
    expect(cellText({ ...MAP_A, rows: MAP_A.rows.slice(0, 2) }, [], 3, 0, true)).toBe("0");
  });
});

describe("columnChars", () => {
  test("each column of a uint32 block holds its own number whole", () => {
    expect(columnChars(WIDE_WHOLE, [], false, 4)).toEqual([9, 10, 2, 7]);
    expect(columnChars(WIDE_WHOLE, [], true, 4)).toEqual([9, 10, 2, 7]);
  });

  test("a float64 block's fractions are counted as the page spells them", () => {
    expect(columnChars(WIDE_FRACTIONS, [], true, 3)).toEqual([15, 11, 9]);
  });

  test("a map's column is as wide as the longest number of its rows, read as the grid reads it", () => {
    // 83, 18, 12 and 6 counts read 10.375, 2.25, 1.5 and 0.75 %; the next column's longest are
    // 2.75 and 1.25. In raw every count of the map is two digits at most.
    expect(columnChars(EIGHTHS, [], true, 6)).toEqual([6, 4, 4, 4, 4, 4]);
    expect(columnChars(EIGHTHS, [], false, 6)).toEqual([2, 2, 2, 2, 2, 2]);
  });

  test("what is typed into a cell widens its own column alone, while it is typed", () => {
    expect(columnChars(WIDE_WHOLE, [typedCell(0, 2, "4294967295", false)], false, 4)).toEqual([
      9, 10, 10, 7,
    ]);
    expect(columnChars(WIDE_WHOLE, [typedCell(0, 2, "", false)], false, 4)).toEqual([9, 10, 0, 7]);
  });

  test("a column past the row's last value is counted as the zero it shows", () => {
    expect(columnChars({ ...CURVE_A, rows: [[1200, 900]] }, [], false, 3)).toEqual([4, 3, 1]);
  });

  test("a grid of no rows has no width to give", () => {
    expect(columnChars({ ...CURVE_A, rows: [] }, [], true, 6)).toEqual([0, 0, 0, 0, 0, 0]);
  });
});

describe("pasteSentence", () => {
  test("names the object a pasted table is about to replace every value of", () => {
    expect(pasteSentence(CURVE_A)).toBe("Replaces every value of CurveA");
  });

  test("carries no count of its own, one-dimensional or not - the hint above already has it", () => {
    expect(pasteSentence(MAP_A)).toBe("Replaces every value of MapA");
  });
});

describe("drawable", () => {
  test("a text init is not a grid, however it is shaped", () => {
    expect(drawable(SOFTWARE_LABEL)).toBe(false);
  });

  test("an object with no cell for a value to sit in is not", () => {
    expect(drawable(VALUE_A)).toBe(false);
  });

  test("a scalar is one cell, stated or not", () => {
    expect(drawable(PARAMETER_A)).toBe(true);
    expect(drawable(VALUE_C)).toBe(true);
  });

  test("a shaped, non-text object is drawable", () => {
    expect(drawable(CURVE_A)).toBe(true);
  });
});

describe("pasted", () => {
  test("a curve's six values, in physical, become the counts the file holds", () => {
    // 12 ms through ×0.01 is 1200 counts - the same arithmetic a typed cell goes through.
    const block = pasted("12\t9\t8\t7.5\t7\t6.5", CURVE_A, true);
    expect(block.refusal).toBeNull();
    expect(block.rows).toEqual([[1200, 900, 800, 750, 700, 650]]);
  });

  test("in raw, the counts are taken as they are", () => {
    const block = pasted("1300\t950\t850\t800\t750\t700", CURVE_A, false);
    expect(block.rows).toEqual([[1300, 950, 850, 800, 750, 700]]);
  });

  test("a map takes four rows of six", () => {
    const text = [
      "1\t2\t3\t4\t5\t6",
      "7\t8\t9\t10\t11\t12",
      "13\t14\t15\t16\t17\t18",
      "19\t20\t21\t22\t23\t24",
    ].join("\n");
    expect(pasted(text, MAP_A, false).rows).toEqual([
      [1, 2, 3, 4, 5, 6],
      [7, 8, 9, 10, 11, 12],
      [13, 14, 15, 16, 17, 18],
      [19, 20, 21, 22, 23, 24],
    ]);
  });

  test("a header row and column are dropped without being read", () => {
    // What selecting the drawn grid gives: a blank corner, AxisA's readings, the CurveA label -
    // and readings that belong to no axis at all, which are discarded just the same.
    const text = ["\t0\t800\t1600\t3200\t4800\t8000", "CurveA (ms)\t12\t9\t8\t7.5\t7\t6.5"].join(
      "\n",
    );
    expect(pasted(text, CURVE_A, true).rows).toEqual([[1200, 900, 800, 750, 700, 650]]);
  });

  test("a map's header row and column are dropped too", () => {
    const text = [
      "\t0\t800\t1600\t3200\t4800\t8000",
      "0\t1\t2\t3\t4\t5\t6",
      "30\t7\t8\t9\t10\t11\t12",
      "70\t13\t14\t15\t16\t17\t18",
      "100\t19\t20\t21\t22\t23\t24",
    ].join("\n");
    expect(pasted(text, MAP_A, false).rows?.[3]).toEqual([19, 20, 21, 22, 23, 24]);
  });

  test("breakpoints above values, with no labels, matches neither shape", () => {
    const text = ["0\t3200\t6400\t12800\t19200\t32000", "1200\t900\t800\t750\t700\t650"].join("\n");
    expect(pasted(text, CURVE_A, false).refusal).toBe(
      "expected 1 row of 6, or 2 rows of 7 with a header; got 2 rows of 6",
    );
  });

  test("a column is refused: the grid draws a curve as a row", () => {
    expect(pasted("1200\n900\n800\n750\n700\n650", CURVE_A, false).refusal).toBe(
      "expected 1 row of 6, or 2 rows of 7 with a header; got 6 rows of 1",
    );
  });

  test("rows of different lengths are not a table", () => {
    expect(pasted("1\t2\t3\t4\t5\t6\n7\t8\t9", MAP_A, false).refusal).toBe(
      "this is not a table: its rows are 6 and 3 values long",
    );
  });

  test("three different lengths are listed, not joined by two ands", () => {
    // `join(" and ")` reads for two and turns three into "6 and 3 and 9", which is one
    // sentence pretending to be three.
    const text = "1\t2\t3\t4\t5\t6\n7\t8\t9\n1\t2\t3\t4\t5\t6\t7\t8\t9";
    expect(pasted(text, MAP_A, false).refusal).toBe(
      "this is not a table: its rows are 6, 3 and 9 values long",
    );
  });

  test("a comma is the decimal separator where no cell has a point", () => {
    expect(pasted("12\t9\t8\t7,5\t7\t6,5", CURVE_A, true).rows).toEqual([
      [1200, 900, 800, 750, 700, 650],
    ]);
  });

  test("a block mixing a comma and a point does not know which it means", () => {
    expect(pasted("12\t9\t8\t7.5\t7\t6,5", CURVE_A, true).refusal).toBe(
      "this mixes '.' and ',' as decimal separators, so it is not clear what it means",
    );
  });

  test("a thousands separator beside a decimal comma is not a number", () => {
    expect(pasted("1.234,56\t9\t8\t7.5\t7\t6.5", CURVE_A, true).refusal).toBe(
      "'1.234,56' is not a number",
    );
  });

  test("a comma before three digits could be either, so the block is refused", () => {
    // What an English spreadsheet puts on the clipboard for twelve hundred, and what a French
    // one puts there for one and a fifth. Read as a decimal point - the rule as it stood - a
    // uint32 curve of 1,000 / 2,000 / 3,000 was written 1 / 2 / 3 and nothing said so.
    expect(pasted("1,200\t2\t3\t4\t5\t6", CURVE_A, false).refusal).toBe(
      "the comma in '1,200' could be a decimal point or a thousands separator, so it is not " +
        "clear what it means; paste the column unformatted",
    );
  });

  test("a comma before one, two or four digits is a decimal point still", () => {
    // The blocks §4.2 was written for are untouched: only three digits at the end of the cell
    // are a grouping anyone writes, so 1,5 and 1,25 stay halves and 1,2345 stays a decimal.
    expect(pasted("1,5\t1,25\t1,2345\t7\t7\t7", CURVE_A, false).rows).toEqual([
      [1.5, 1.25, 1.2345, 7, 7, 7],
    ]);
  });

  test("a header's own cells are read for neither the comma rule nor the grouping", () => {
    // AxisA's readings are the header, and one of them carries a point - which, weighed with
    // the values, would turn the comma rule off and refuse a perfectly good French block; and
    // another is grouped, which would refuse it a second way. Spec 3 says the header is
    // discarded without being read, and this is where that has to mean something.
    const text = ["\t0\t3.2\t1,600\t3200\t4800\t8000", "CurveA (ms)\t12\t9\t8\t7,5\t7\t6,5"].join(
      "\n",
    );
    expect(pasted(text, CURVE_A, true).rows).toEqual([[1200, 900, 800, 750, 700, 650]]);
  });

  test("whitespace inside a cell is not stripped", () => {
    expect(pasted("1 234\t9\t8\t7.5\t7\t6.5", CURVE_A, true).refusal).toBe(
      "'1 234' is not a number",
    );
  });

  test("an empty cell is nothing, not zero", () => {
    expect(pasted("12\t\t8\t7.5\t7\t6.5", CURVE_A, true).refusal).toBe("'' is not a number");
  });

  test("a value block over indices takes one row of eight", () => {
    expect(pasted("0\t12\t28\t52\t84\t124\t180\t255", BLOCK_A, false).rows).toEqual([
      [0, 12, 28, 52, 84, 124, 180, 255],
    ]);
  });
});

describe("pasteHint", () => {
  test("a curve asks for one row", () => {
    expect(pasteHint(CURVE_A)).toBe(
      "Paste 1 row of 6 values from a spreadsheet to replace them all.",
    );
  });

  test("a map asks for four", () => {
    expect(pasteHint(MAP_A)).toBe(
      "Paste 4 rows of 6 values from a spreadsheet to replace them all.",
    );
  });
});

describe("wanted", () => {
  test("a scalar takes one row of one", () => {
    expect(wanted(PARAMETER_A)).toEqual([1, 1]);
  });

  test("a curve takes one row of its width and a map its own", () => {
    expect(wanted(CURVE_A)).toEqual([1, 6]);
    expect(wanted(MAP_A)).toEqual([4, 6]);
  });
});

describe("pastes", () => {
  test("a table is pasted into a grid of a shape", () => {
    expect(pastes(CURVE_A)).toBe(true);
    expect(pastes(MAP_A)).toBe(true);
  });

  test("one value is no table, which the server refuses it", () => {
    expect(pastes(PARAMETER_A)).toBe(false);
  });
});

describe("plotDrawn", () => {
  test("a grid is drawn as a picture too", () => {
    expect(plotDrawn(CURVE_A)).toBe(true);
  });

  test("one point plots nothing", () => {
    expect(plotDrawn(PARAMETER_A)).toBe(false);
  });
});

describe("statedNote", () => {
  test("an object stating one value for every element says so", () => {
    expect(statedNote({ ...CURVE_A, stated: "scalar" })).toBe("Stated once, for every cell.");
  });

  test("an object stating nothing says so, a scalar too", () => {
    expect(statedNote({ ...CURVE_A, stated: "none" })).toBe("Nothing is stated.");
    expect(statedNote(VALUE_C)).toBe("Nothing is stated.");
  });

  test("a table written out says nothing", () => {
    expect(statedNote(CURVE_A)).toBeNull();
  });

  test("a scalar written is one value for one cell, which needs no sentence", () => {
    expect(statedNote(PARAMETER_A)).toBeNull();
  });
});
