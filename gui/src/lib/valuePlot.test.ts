import { describe, expect, test, vi } from "vitest";
import type { GridAxis, ValuesReply } from "../api/types";
import { BOX, plotted } from "./valuePlot";

const AXIS_A = {
  position: "axis",
  name: "AxisA",
  unit: "Hz",
  breakpoints: [0, 3200, 6400, 12800, 19200, 32000],
  conversion: { kind: "linear", factor: 0.25, offset: 0 },
};

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
  axes: [AXIS_A],
  unshown: null,
  minimum_text: null,
  maximum_text: null,
  owner: "Controller",
  file: "controller.ddd.json",
  findings: [],
};

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
  file: "user_interface.ddd.json",
  findings: [],
};

const CURVE_B: ValuesReply = {
  ...CURVE_A,
  name: "CurveB",
  datatype: "uint8",
  unit: "%",
  conversion: { kind: "linear", factor: 0.5, offset: 0 },
  minimum: 0,
  maximum: 127.5,
  rows: [[200, 200, 200, 200, 200, 200]],
  stated: "scalar",
};

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
    { ...AXIS_A, position: "x_axis" },
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
  file: "controller.ddd.json",
  findings: [],
};

const inside = BOX.width - BOX.left - BOX.right;

describe("plotted", () => {
  test("a curve is one line of six points", () => {
    const plot = plotted(CURVE_A, true);
    expect(plot.lines).toHaveLength(1);
    expect(plot.lines[0]?.points).toHaveLength(6);
    expect(plot.lines[0]?.label).toBe("");
  });

  test("the x positions follow the breakpoints, not their order", () => {
    // AxisA reads 0, 800, 1600, 3200, 4800, 8000 - gaps of 800, 800, 1600, 1600, 3200. Evenly
    // spaced they would sit a fifth apart; proportional, the third is a fifth of the way along
    // and the fourth two fifths.
    const xs = plotted(CURVE_A, true).lines[0]?.points.map((p) => p.x) ?? [];
    expect(xs[0]).toBeCloseTo(BOX.left);
    expect(xs[2]).toBeCloseTo(BOX.left + inside * 0.2);
    expect(xs[3]).toBeCloseTo(BOX.left + inside * 0.4);
    expect(xs[5]).toBeCloseTo(BOX.left + BOX.width - BOX.left - BOX.right);
  });

  test("without an axis the x positions are the indices, evenly spaced", () => {
    const xs = plotted(BLOCK_A, true).lines[0]?.points.map((p) => p.x) ?? [];
    expect(xs[0]).toBeCloseTo(BOX.left);
    expect(xs[4]).toBeCloseTo(BOX.left + inside * (4 / 7));
  });

  test("the range is the values padded by a twentieth", () => {
    // CurveA reads 6.5 to 12, a span of 5.5, so a twentieth is 0.275.
    const plot = plotted(CURVE_A, true);
    expect(plot.low).toBeCloseTo(6.225);
    expect(plot.high).toBeCloseTo(12.275);
  });

  test("a value at the top of the range is drawn at the top of the padding", () => {
    const plot = plotted(CURVE_A, true);
    expect(plot.lines[0]?.points[0]?.y).toBeGreaterThan(BOX.top);
    expect(plot.lines[0]?.points[0]?.y).toBeLessThan(BOX.top + 20);
  });

  test("limits outside the values are not drawn", () => {
    // 0 and 655.35 against values of 6.5 to 12: the ordinary case, and neither is in frame.
    expect(plotted(CURVE_A, true).rules).toEqual([]);
  });

  test("limits that fall inside are drawn, both of them", () => {
    // BlockA spans exactly its own limits, so both land on the values' extremes - inside the
    // padded range, which is the whole reason the range is padded.
    const rules = plotted(BLOCK_A, true).rules;
    expect(rules.map((rule) => rule.value)).toEqual([0, 255]);
  });

  test("in raw counts a limit is converted back", () => {
    // `minimum` and `maximum` are physical. CurveB's upper limit of 127.5 % is 255 counts, and
    // drawing 127.5 against counts of 200 would put the line in the wrong place entirely.
    const withLimit: ValuesReply = { ...CURVE_B, maximum: 102 };
    expect(plotted(withLimit, false).rules.map((rule) => rule.value)).toEqual([204]);
  });

  test("a range of zero gets a span of its own", () => {
    // CurveB reads 100 throughout, so there is nothing to scale; 100 ± a twentieth of itself.
    const plot = plotted(CURVE_B, true);
    expect(plot.low).toBeCloseTo(95);
    expect(plot.high).toBeCloseTo(105);
  });

  test("a range of zero at zero gets one either side", () => {
    // A row of zeros, and a twentieth of zero is zero - there is no proportion to take.
    const zeros: ValuesReply = { ...BLOCK_A, rows: [[0, 0, 0, 0, 0, 0, 0, 0]] };
    const plot = plotted(zeros, true);
    expect([plot.low, plot.high]).toEqual([-1, 1]);
  });

  test("a row with no values gets the same span as the zero row, not Infinity", () => {
    // A `value_block` of `dimensions: [6]` stated with `"init": []` resolves with `shape=(6,)`
    // and `rows=[[]]` - measured against a scratch copy of `examples/demo`, not assumed.
    // `Math.min()`/`Math.max()` of nothing are `Infinity`/`-Infinity`, which is not a range and
    // is what the side readings would print without the guard.
    const empty: ValuesReply = { ...BLOCK_A, shape: [6], rows: [[]] };
    const plot = plotted(empty, true);
    expect([plot.low, plot.high]).toEqual([-1, 1]);
    expect(plot.lines[0]?.points).toEqual([]);
  });

  test("a reading has the arithmetic's tail taken off before it is printed", () => {
    // Nothing in `examples/demo` pads to a tail, so this fixture is the reason the rounding
    // exists rather than a demonstration of it: an ordinary uint8 x0.1 curve reading 0.5 to 1.2
    // pads to a `high` of exactly 1.2349999999999999, which the frame would print in full beside
    // values of one decimal. `low` is clean at 0.465, so only one end of the range moves.
    const tenths: ValuesReply = {
      ...CURVE_A,
      datatype: "uint8",
      conversion: { kind: "linear", factor: 0.1, offset: 0 },
      rows: [[5, 6, 8, 9, 11, 12]],
    };
    const plot = plotted(tenths, true);
    expect(plot.high).toBe(1.235);
    expect(plot.low).toBe(0.465);
  });

  test("a flat line at zero is ruled by its own lower limit", () => {
    // A row stating zero everywhere under limits of `0 … 65535` - `ValueD`'s in the demo, were its
    // file to state its zeros; its absent init draws no picture (`plotDrawn`) - and the range of
    // -1 to 1 the line above gives it puts the lower limit *inside* the frame, so the rule is
    // drawn exactly where the flat line is. That is correct and looks odd, which is worth knowing
    // before a picture of it is reported as a fault.
    const zeros: ValuesReply = { ...BLOCK_A, rows: [[0, 0, 0, 0, 0, 0, 0, 0]] };
    const plot = plotted(zeros, true);
    expect(plot.rules.map((rule) => rule.value)).toEqual([0]);
    expect(plot.rules[0]?.y).toBeCloseTo(plot.lines[0]?.points[0]?.y ?? -1);
  });

  test("one point is a point and no line", () => {
    const single: ValuesReply = { ...BLOCK_A, shape: [1], rows: [[7]] };
    const points = plotted(single, true).lines[0]?.points ?? [];
    expect(points).toHaveLength(1);
    expect(points[0]?.x).toBeCloseTo(BOX.left + inside / 2);
  });

  test("a map is four lines, each labelled with its own reading", () => {
    const plot = plotted(MAP_A, true);
    expect(plot.lines).toHaveLength(4);
    expect(plot.lines.map((line) => line.label)).toEqual(["0", "30", "70", "100"]);
  });

  test("a row with no label of its own is left unlabelled", () => {
    // A y axis stating fewer breakpoints than the object has rows: the analysis would file a
    // finding, and the page still has to draw what it was sent.
    const short: ValuesReply = {
      ...MAP_A,
      axes: [MAP_A.axes[0] as GridAxis, { ...(MAP_A.axes[1] as GridAxis), breakpoints: [0, 60] }],
    };
    expect(plotted(short, true).lines.map((line) => line.label)).toEqual(["0", "30", "", ""]);
  });

  test("the ticks are the grid's own column readings", () => {
    const plot = plotted(CURVE_A, true);
    expect(plot.ticks.map((tick) => tick.label)).toEqual([
      "0",
      "800",
      "1600",
      "3200",
      "4800",
      "8000",
    ]);
    // Proportional placement (spec §3) is about where a reading sits, not only what it says -
    // the third tick, like the third point above, is a fifth of the way across.
    expect(plot.ticks[2]?.x).toBeCloseTo(BOX.left + inside * 0.2);
  });

  test("the labels name the axis below and the object beside", () => {
    const plot = plotted(CURVE_A, true);
    expect([plot.xLabel, plot.yLabel]).toEqual(["AxisA (Hz)", "CurveA (ms)"]);
  });

  test("in raw counts the labels drop their units", () => {
    const plot = plotted(CURVE_A, false);
    expect([plot.xLabel, plot.yLabel]).toEqual(["AxisA", "CurveA"]);
  });

  test("laid against indices there is no axis to name", () => {
    expect(plotted(BLOCK_A, true).xLabel).toBe("");
  });

  // The tests below are not in the brief. They close branch-coverage gaps that the brief's own
  // fixtures leave unreached, per the task's instruction to add a covering test rather than
  // delete the branch. See the task report for why each one is needed.

  test("a map whose x axis states no breakpoints is indexed by its own width, not its row count", () => {
    // An axis states a `size` and need not state an `init`; one that does not states no
    // breakpoints at all. A map still needs both of its axes - only this one's breakpoints go
    // missing, not the axis itself or the y axis beside it. MapA is 4 rows of 6, and the
    // fallback must answer 6 - its *column* count - not 4, its row count.
    const noInit: ValuesReply = {
      ...MAP_A,
      axes: [{ ...(MAP_A.axes[0] as GridAxis), breakpoints: [] }, MAP_A.axes[1] as GridAxis],
    };
    const xs = plotted(noInit, true).lines[0]?.points.map((p) => p.x) ?? [];
    expect(xs).toHaveLength(6);
    expect(xs[5]).toBeCloseTo(BOX.left + inside);
  });

  test("an axis stating fewer breakpoints than the shape places its columns by their indices", () => {
    // 15:M7: the columns are the shape's, and an axis stating three breakpoints for six columns
    // places none of the three past it; the six are laid out evenly, as over no axis, where the
    // three past the last breakpoint were piled up at the axis's start.
    const shortAxis: ValuesReply = {
      ...CURVE_A,
      axes: [{ ...AXIS_A, breakpoints: [0, 3200, 6400] }],
    };
    const xs = plotted(shortAxis, true).lines[0]?.points.map((p) => p.x) ?? [];
    expect(xs).toHaveLength(6);
    expect(xs[0]).toBeCloseTo(BOX.left);
    expect(xs[5]).toBeCloseTo(BOX.left + inside);
  });

  test("and its ticks read the indices, as over an axis stating no breakpoints (fix round 1, M10)", () => {
    // Uneven breakpoints show what reading them under index places did: 100 was drawn halfway
    // between 0 and 5000, at the second of six evenly spaced places.
    const uneven: ValuesReply = {
      ...CURVE_A,
      conversion: { kind: "identity" },
      axes: [{ ...AXIS_A, conversion: { kind: "identity" }, breakpoints: [0, 100, 5000] }],
    };
    const ticks = plotted(uneven, true).ticks;
    expect(ticks.map((tick) => tick.label)).toEqual(["0", "1", "2", "3", "4", "5"]);
    expect(ticks.map((tick) => tick.x)).toEqual(
      plotted(uneven, true).lines[0]?.points.map((point) => point.x),
    );
    expect(ticks[1]?.x).toBeCloseTo(BOX.left + inside / 5);
    // The axis is still the one named beside them.
    expect(plotted(uneven, true).xLabel).toBe("AxisA (Hz)");
  });

  test("an axis stating more breakpoints than the shape places the shape's columns by theirs", () => {
    const narrow: ValuesReply = { ...CURVE_A, shape: [2], rows: [[1200, 900]] };
    const xs = plotted(narrow, true).lines[0]?.points.map((p) => p.x) ?? [];
    expect(xs).toEqual([BOX.left, BOX.left + inside]);
  });

  test("values past the shape are not drawn, as the grid draws none of them", () => {
    const long: ValuesReply = { ...CURVE_A, rows: [[1, 2, 3, 4, 5, 6, 7, 8], [9]] };
    expect(plotted(long, false).lines.map((line) => line.points.length)).toEqual([6]);
  });
});

/** A grid of `rows` by `columns` of uint8 counts, laid against an axis stating a breakpoint for
 * every column, or against none. */
function grid(rows: number, columns: number, axis: boolean): ValuesReply {
  return {
    ...BLOCK_A,
    shape: rows === 1 ? [columns] : [rows, columns],
    rows: Array.from({ length: rows }, (_, row) =>
      Array.from({ length: columns }, (_, column) => (row * 7 + column) % 256),
    ),
    axes: axis
      ? [
          {
            ...AXIS_A,
            position: "x_axis",
            conversion: { kind: "identity" },
            breakpoints: Array.from({ length: columns }, (_, column) => column * 3),
          },
        ]
      : [],
  };
}

/** How many numbers the plot's two extremes were asked of, in all, while `work` ran: every
 * argument of every `Math.min` and `Math.max` call - which is what a spread of the values for each
 * point costs, and a pass over them once does not. */
function extremesAskedOf(work: () => void): number {
  let asked = 0;
  const counting = (original: (...values: number[]) => number) =>
    function counted(...values: number[]) {
      asked += values.length;
      return original(...values);
    };
  const [lowest, highest] = [counting(Math.min), counting(Math.max)];
  const min = vi.spyOn(Math, "min").mockImplementation(lowest);
  const max = vi.spyOn(Math, "max").mockImplementation(highest);
  try {
    work();
  } finally {
    min.mockRestore();
    max.mockRestore();
  }
  return asked;
}

describe("plotted over a large grid (15:M8)", () => {
  test.each([
    ["a row of 4,096 over an axis", grid(1, 4096, true)],
    ["a row of 4,096 at its indices", grid(1, 4096, false)],
    ["a map of 64 by 64", grid(64, 64, false)],
  ])("%s finds each axis's extremes once, in work linear in its cells", (_, reply) => {
    const cells = reply.rows.flat().length;
    expect(cells).toBe(4096);
    const asked = extremesAskedOf(() => plotted(reply, true));
    // Two figures asked of every cell at most - the values' extremes - and as many of every
    // column's place; where each point spreads the places, it is 4,096 times as many.
    expect(asked).toBeLessThanOrEqual(4 * cells);
  });

  test("a grid past the engine's argument limit is drawn, not thrown at", () => {
    const plot = plotted(grid(1, 300_000, true), false);
    expect(plot.lines[0]?.points).toHaveLength(300_000);
    expect(plot.low).toBeLessThan(0);
    expect(plot.high).toBeGreaterThan(255);
  });

  test("its points are where the same values put them in a small grid", () => {
    const plot = plotted(grid(1, 4096, true), false);
    const points = plot.lines[0]?.points ?? [];
    expect(points[0]?.x).toBe(BOX.left);
    expect(points[4095]?.x).toBe(BOX.left + inside);
    expect(points[2048]?.x).toBeCloseTo(BOX.left + (inside * 2048) / 4095);
  });
});

describe("a plot is worked out again only when what it draws changes", () => {
  test("the same reply read the same way is the one plot, drawn again", () => {
    const reply = grid(1, 64, true);
    expect(plotted(reply, true)).toBe(plotted(reply, true));
    expect(plotted(reply, false)).toBe(plotted(reply, false));
  });

  test("a reading changes it, and so does another reply", () => {
    const reply = grid(1, 64, true);
    expect(plotted(reply, false)).not.toBe(plotted(reply, true));
    expect(plotted({ ...reply }, true)).not.toBe(plotted(reply, true));
  });

  test("and it is the plot the reading draws, whichever was asked for first", () => {
    const reply = grid(1, 8, false);
    const raw = plotted(reply, false);
    const physical = plotted(reply, true);
    expect(plotted(reply, false)).toBe(raw);
    expect(plotted(reply, true)).toBe(physical);
  });
});
