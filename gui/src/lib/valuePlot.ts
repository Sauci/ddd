import type { ValuesReply } from "../api/types";
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
  points: PlotPoint[];
}

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
  /** The two readings printed at the frame's edges, with the arithmetic's tail taken off the
   * way `columnHeader` already takes it off a tick's. The padding below is ordinary floating
   * point: a `x0.1` curve running 0.5 to 1.2 pads to a `high` of 1.2349999999999999, and that
   * is what a reader would see beside one-decimal values. The geometry keeps the exact numbers. */
  low: number;
  high: number;
}

const PAD = 20;

/** Where the values sit along the bottom, one place for each column the object's shape has: the
 * axis's own readings where it states one for every column, and the indices otherwise - evenly
 * spaced because they are, while breakpoints are not. An axis stating fewer breakpoints than the
 * shape places none of its columns, which no breakpoint of it could place in order, and one
 * stating more places the shape's columns alone (15:M7). */
function alongTheBottom(reply: ValuesReply, physical: boolean): number[] {
  const width = wanted(reply)[1];
  const axis = columnAxis(reply);
  if (axis === undefined || axis.breakpoints.length < width) {
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

/** The range the values are drawn in: their own span with a twentieth of it to spare above and
 * below, so a limit that falls on an extreme - which is where both of `BlockA`'s fall - is drawn
 * inside the frame rather than clipped to its edge.
 *
 * A span of zero has no twentieth worth taking, and a scale built on it divides by zero: an
 * object stating one value for every element is real (`CurveB`) and so is one stating none at
 * all. Such a range is the value with a twentieth of *itself* either side, or one either side
 * where the value is zero and there is no proportion to take.
 *
 * A row can hold no values at all - `Math.min()` and `Math.max()` of nothing are `Infinity` and
 * `-Infinity`, which is not a range and prints as those two words. An `init` of `[]` against a
 * stated shape reaches this: `_check_init_shape` files a finding but does not drop the
 * declaration, so the reply still has to draw *something*. It gets the same span the zero case
 * gets, -1 to 1, there being no values to take a proportion of either. */
function rangeOf(values: number[]): [number, number] {
  if (values.length === 0) return [-1, 1];
  const low = Math.min(...values);
  const high = Math.max(...values);
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

export function plotted(reply: ValuesReply, physical: boolean): Plot {
  const xs = alongTheBottom(reply, physical);
  const rows = drawnRows(reply);
  const values = rows.flatMap((row) =>
    row.map((raw) => (physical ? physicalOf(raw, reply.conversion) : raw)),
  );
  const [low, high] = rangeOf(values);
  const across = BOX.width - BOX.left - BOX.right;
  const down = BOX.height - BOX.top - BOX.bottom;
  // A place for every column the shape has (`alongTheBottom`), and no row or tick drawn past the
  // shape's last column (`drawnRows`, `columnHeader`): each index read here has its place.
  const xAt = (index: number) =>
    placed(xs[index] as number, Math.min(...xs), Math.max(...xs), BOX.left, across);
  const yAt = (value: number) => BOX.top + down - placed(value, low, high, 0, down);
  const labels = reply.shape.length === 1 ? rows.map(() => "") : rowHeader(reply, physical);
  const axis = columnAxis(reply);
  return {
    // A label for every row the shape has (`rowHeader`), and no row drawn past its last.
    lines: rows.map((row, index) => ({
      label: labels[index] as string,
      points: row.map((raw, at) => ({
        x: xAt(at),
        y: yAt(physical ? physicalOf(raw, reply.conversion) : raw),
      })),
    })),
    ticks: columnHeader(reply, physical).map((label, index) => ({ x: xAt(index), label })),
    rules: [reply.minimum, reply.maximum]
      .map((limit) => (physical ? limit : rawOf(limit, reply.conversion, reply.datatype)))
      .filter((value) => value >= low && value <= high)
      .map((value) => ({ value, y: yAt(value) })),
    xLabel: axis === undefined ? "" : labelled(axis.name, axis.unit, physical),
    yLabel: labelled(reply.name, reply.unit, physical),
    low: rounded(low),
    high: rounded(high),
  };
}
