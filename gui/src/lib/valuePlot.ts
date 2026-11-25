import type { GridAxis, ValuesReply } from "../api/types";
import {
  columnAxis,
  columnHeader,
  labelled,
  physicalOf,
  rawOf,
  rounded,
  rowHeader,
  wanted,
} from "./objectValues";

/** The drawn box, in the `viewBox`'s own units - one fixed frame scaled to whatever width the
 * component is given, so the drawing is resolution-free and its screenshot is stable. The left
 * margin holds the two y readings, the bottom one the x readings. */
export const BOX = { width: 640, height: 200, left: 56, right: 16, top: 8, bottom: 28 } as const;

export interface PlotPoint {
  x: number;
  y: number;
}

export interface PlotLine {
  label: string;
  /** Whether the label is drawn: it has words, and no label drawn before it stands within a line's
   * height of it (`LABEL_GAP`). A label left out is still the grid's own row header. */
  labelled: boolean;
  points: PlotPoint[];
}

/** What a reading's figure needs of the margin beside the frame, in the box's own units: each
 * character of the 10px text a little over a digit's width, the gap between the figure and the
 * frame, and a little to spare. */
const READING_CHAR = 6.5;
const READING_GAP = 6;
const READING_PAD = 2;

/** One of the two readings printed beside the frame: the figure, and where its point stands. */
export interface PlotReading {
  text: string;
  y: number;
}

/** The least height between two row labels, in the box's own units: a line of the 10px text they
 * are drawn in, and a pixel over. Two nearer than this are drawn over one another. */
export const LABEL_GAP = 11;

export interface PlotRule {
  value: number;
  y: number;
}

export interface Plot {
  lines: PlotLine[];
  ticks: { x: number; label: string }[];
  rules: PlotRule[];
  xLabel: string;
  yLabel: string;
  /** The range the values are drawn in, with the arithmetic's tail taken off the way
   * `columnHeader` already takes it off a tick's. The padding is ordinary floating point: a
   * `x0.1` curve running 0.5 to 1.2 pads to a `high` of 1.2349999999999999. The geometry keeps the
   * exact numbers. */
  low: number;
  high: number;
  /** Where the frame's left edge stands: `BOX.left`, or further right where a reading is too long
   * for that margin. */
  left: number;
  /** The greatest and the least value a cell holds, each beside the frame at the place of the
   * point that reads it, the greatest first - what a reader finds in the grid, never the padded
   * range's own figures, which no cell holds (16:M22). One where every cell reads alike, none where
   * no cell holds a value. */
  readings: PlotReading[];
}

const PAD = 20;

/** The axis whose readings place the values along the bottom, or `undefined` where they sit at
 * their indices: an object laid against no axis, or against one stating fewer breakpoints than
 * the shape has columns, which places none of them - no breakpoint of it could place the columns
 * past its last in order (15:M7). */
function placing(reply: ValuesReply): GridAxis | undefined {
  const axis = columnAxis(reply);
  return axis === undefined || axis.breakpoints.length < wanted(reply)[1] ? undefined : axis;
}

/** Where the values sit along the bottom, one place for each column the object's shape has: the
 * axis's own readings where it states one for every column (`placing`), and otherwise the
 * indices, evenly spaced because they are, while breakpoints are not. An axis stating more
 * breakpoints than the shape places the shape's columns alone. */
function alongTheBottom(reply: ValuesReply, physical: boolean): number[] {
  const width = wanted(reply)[1];
  const axis = placing(reply);
  if (axis === undefined) {
    return Array.from({ length: width }, (_, index) => index);
  }
  return axis.breakpoints
    .slice(0, width)
    .map((raw) => (physical ? physicalOf(raw, axis.conversion) : raw));
}

/** The rows the picture draws, each cut at the shape's last column, and no row past its last: the
 * values the grid draws, and none it does not. */
function drawnRows(reply: ValuesReply): number[][] {
  const [height, width] = wanted(reply);
  return reply.rows.slice(0, height).map((row) => row.slice(0, width));
}

/** The least and the greatest of `values`, found in one pass - never by spreading them as the
 * arguments of `Math.min` and `Math.max`, which a place asked for each point of a large grid made
 * quadratic, and which throws past the number of arguments the engine takes (15:M8). `[Infinity,
 * -Infinity]` of none. */
function extremes(values: readonly number[]): [number, number] {
  let low = Infinity;
  let high = -Infinity;
  for (const value of values) {
    if (value < low) low = value;
    if (value > high) high = value;
  }
  return [low, high];
}

/** The range the values are drawn in: their own span with a twentieth of it to spare above and
 * below, so a limit that falls on an extreme - which is where both of `BlockA`'s fall - is drawn
 * inside the frame rather than clipped to its edge.
 *
 * A span of zero has no twentieth worth taking, and a scale built on it divides by zero: an
 * object stating one value for every element is real (`CurveB`) and so is one stating none at
 * all. Such a range is the value with a twentieth of *itself* either side, or one either side
 * where the value is zero and there is no proportion to take.
 *
 * A row can hold no values at all - the `extremes` of nothing are `Infinity` and `-Infinity`,
 * which is not a range and prints as those two words. An `init` of `[]` against a
 * stated shape reaches this: `_check_init_shape` files a finding but does not drop the
 * declaration, so the reply still has to draw *something*. It gets the same span the zero case
 * gets, -1 to 1, there being no values to take a proportion of either. */
function rangeOf(values: number[]): [number, number] {
  if (values.length === 0) return [-1, 1];
  const [low, high] = extremes(values);
  if (low !== high) {
    const pad = (high - low) / PAD;
    return [low - pad, high + pad];
  }
  const span = low === 0 ? 1 : Math.abs(low) / PAD;
  return [low - span, low + span];
}

/** A reading's place in the box, from a range to a side of it. */
function placed(value: number, from: number, to: number, start: number, length: number): number {
  return from === to ? start + length / 2 : start + ((value - from) / (to - from)) * length;
}

/** What `plotted` drew, by the reply and the reading it drew: a grid is drawn again on every
 * keystroke typed into it, and what it draws changes with neither (15:M8). Held by the reply
 * itself, so that a reply let go takes its plots with it. */
const DRAWN = new WeakMap<ValuesReply, { raw?: Plot; physical?: Plot }>();

/** The plot of `reply` in the reading asked for, worked out once for as long as the page holds the
 * reply: the same plot, not an equal one, so that what draws it can see nothing changed. */
export function plotted(reply: ValuesReply, physical: boolean): Plot {
  const kept = DRAWN.get(reply) ?? {};
  DRAWN.set(reply, kept);
  const key = physical ? "physical" : "raw";
  const known = kept[key];
  if (known !== undefined) return known;
  const plot = drawn(reply, physical);
  kept[key] = plot;
  return plot;
}

/** The readings beside the frame, from the greatest and the least value: each at its own place,
 * and the one where both are the same value. The range is padded a twentieth of the span beyond
 * the two (`rangeOf`), so that two readings stand the better part of the frame's height apart,
 * however little the values differ: they never meet. */
function readingsOf(
  ends: readonly [number, number] | null,
  yAt: (value: number) => number,
): PlotReading[] {
  if (ends === null) return [];
  const [greatest, least] = ends;
  if (greatest === least) return [{ text: String(rounded(greatest)), y: yAt(greatest) }];
  return [
    { text: String(rounded(greatest)), y: yAt(greatest) },
    { text: String(rounded(least)), y: yAt(least) },
  ];
}

function drawn(reply: ValuesReply, physical: boolean): Plot {
  const xs = alongTheBottom(reply, physical);
  const rows = drawnRows(reply);
  const values = rows.flatMap((row) =>
    row.map((raw) => (physical ? physicalOf(raw, reply.conversion) : raw)),
  );
  const [low, high] = rangeOf(values);
  const [least, greatest] = extremes(values);
  // The margin that holds the readings: the box's own, or wider where a reading's figure is longer
  // than it holds, so that none loses a leading digit to the frame's edge (16:M22).
  const longest = values.length === 0 ? 0 : String(rounded(greatest)).length;
  const left = Math.max(
    BOX.left,
    READING_GAP + READING_PAD + READING_CHAR * Math.max(longest, String(rounded(least)).length),
  );
  const across = BOX.width - left - BOX.right;
  const down = BOX.height - BOX.top - BOX.bottom;
  // A place for every column the shape has (`alongTheBottom`), and no row or tick drawn past the
  // shape's last column (`drawnRows`, `columnHeader`): each index read here has its place.
  const [first, last] = extremes(xs);
  const xAt = (index: number) => placed(xs[index] as number, first, last, left, across);
  const yAt = (value: number) => BOX.top + down - placed(value, low, high, 0, down);
  const labels = reply.shape.length === 1 ? rows.map(() => "") : rowHeader(reply, physical);
  const lines = rows.map((row, index) => ({
    // A label for every row the shape has (`rowHeader`), and no row drawn past its last.
    label: labels[index] as string,
    labelled: false,
    points: row.map((raw, at) => ({
      x: xAt(at),
      y: yAt(physical ? physicalOf(raw, reply.conversion) : raw),
    })),
  }));
  // A row's label stands at its last point: kept where no label kept before it is a line's height
  // away or nearer, in the order of the rows.
  const stood: number[] = [];
  for (const line of lines) {
    const end = line.points.at(-1);
    if (line.label === "" || end === undefined) continue;
    if (stood.some((y) => Math.abs(y - end.y) < LABEL_GAP)) continue;
    line.labelled = true;
    stood.push(end.y);
  }
  // The axis placing the values along the bottom (`placing`), or none where they sit at their
  // indices - an axis stating fewer breakpoints than the shape included, which is not named under
  // ticks reading the indices: its name and unit there made readings of them, `AxisA (Hz)` under
  // 0 to 5, where the grid's header above reads its breakpoints.
  const axis = placing(reply);
  return {
    lines,
    // Where the values sit at their indices, the ticks read them, as over an axis stating no
    // breakpoints: a breakpoint read at an index's place said what the place is not - 100, of
    // breakpoints 0, 100 and 5000, drawn halfway between 0 and 5000 (fix round 1, M10).
    ticks: (axis === undefined
      ? Array.from({ length: wanted(reply)[1] }, (_, index) => String(index))
      : columnHeader(reply, physical)
    ).map((label, index) => ({ x: xAt(index), label })),
    rules: [reply.minimum, reply.maximum]
      .map((limit) => (physical ? limit : rawOf(limit, reply.conversion, reply.datatype)))
      .filter((value) => value >= low && value <= high)
      .map((value) => ({ value, y: yAt(value) })),
    xLabel: axis === undefined ? "" : labelled(axis.name, axis.unit, physical),
    yLabel: labelled(reply.name, reply.unit, physical),
    low: rounded(low),
    high: rounded(high),
    left,
    readings: readingsOf(values.length === 0 ? null : [greatest, least], yAt),
  };
}
