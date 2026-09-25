import type { ValuesReply } from "../api/types";
import { columnAxis, columnHeader, labelled, physicalOf, rawOf, rowHeader } from "./objectValues";

/** The drawn box, in the `viewBox`'s own units - one fixed frame scaled to whatever width the
 * component is given, so the drawing is resolution-free and its screenshot is stable. The left
 * margin holds the two y readings, the bottom one the x readings. */
export const BOX = { width: 640, height: 200, left: 56, right: 8, top: 8, bottom: 28 } as const;

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
  low: number;
  high: number;
}

const PAD = 20;

/** How many values a row holds - the shape's last dimension, and 0 for a shape of none. */
function widthOf(reply: ValuesReply): number {
  const [first = 0, second] = reply.shape;
  return second === undefined ? first : second;
}

/** Where the values sit along the bottom: the axis's own readings where there is one, and the
 * indices otherwise - which are evenly spaced because they are, while breakpoints are not. */
function alongTheBottom(reply: ValuesReply, physical: boolean): number[] {
  const axis = columnAxis(reply);
  if (axis === undefined || axis.breakpoints.length === 0) {
    return Array.from({ length: widthOf(reply) }, (_, index) => index);
  }
  return axis.breakpoints.map((raw) => (physical ? physicalOf(raw, axis.conversion) : raw));
}

/** The range the values are drawn in: their own span with a twentieth of it to spare above and
 * below, so a limit that falls on an extreme - which is where both of `BlockA`'s fall - is drawn
 * inside the frame rather than clipped to its edge.
 *
 * A span of zero has no twentieth worth taking, and a scale built on it divides by zero: an
 * object stating one value for every element is real (`CurveB`) and so is one stating none at
 * all. Such a range is the value with a twentieth of *itself* either side, or one either side
 * where the value is zero and there is no proportion to take. */
function rangeOf(values: number[]): [number, number] {
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
  const values = reply.rows.flatMap((row) =>
    row.map((raw) => (physical ? physicalOf(raw, reply.conversion) : raw)),
  );
  const [low, high] = rangeOf(values);
  const across = BOX.width - BOX.left - BOX.right;
  const down = BOX.height - BOX.top - BOX.bottom;
  const xAt = (index: number) =>
    placed(xs[index] ?? 0, Math.min(...xs), Math.max(...xs), BOX.left, across);
  const yAt = (value: number) => BOX.top + down - placed(value, low, high, 0, down);
  const labels = reply.shape.length === 1 ? reply.rows.map(() => "") : rowHeader(reply, physical);
  const axis = columnAxis(reply);
  return {
    lines: reply.rows.map((row, index) => ({
      label: labels[index] ?? "",
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
    low,
    high,
  };
}
