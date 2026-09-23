import type { ValuesReply } from "../api/types";

/** A conversion as the server hands it over: its kind and whatever that kind states.
 *
 * Not the brief's `{ kind: string; factor?: number; offset?: number }`: `Conversion` is
 * `dict[str, Any]` on the Python side (`ValuesReply.conversion`, `GridAxis.conversion`), so the
 * generated type is an index signature, `{ [k: string]: unknown }` - not assignable to a type
 * with a required `kind`. This takes the shape the reply actually has, the idiom
 * `gui/src/lib/variableKeys.ts:202`'s `conversion(fields: Record<string, unknown>)` already
 * uses for the same dict. */
type Conversion = Record<string, unknown>;

/** One field of a conversion, narrowed to a number: anything that is not one, `undefined`
 * included, reads as `fallback` - the width `LinearConversion` itself gives `factor` and
 * `offset` when a file leaves them out. */
function number(value: unknown, fallback: number): number {
  return typeof value === "number" ? value : fallback;
}

/** What one raw count reads as. Only a linear conversion multiplies; everything else - the
 * identity, an enum, a string - hands the raw count back, which is what `raw_reading` in the
 * models does and says. */
export function physicalOf(raw: number, conversion: Conversion): number {
  if (conversion.kind !== "linear") return raw;
  return rounded(raw * number(conversion.factor, 1) + number(conversion.offset, 0));
}

/** The raw count a physical value needs, rounded to a whole number where the datatype stores
 * one. Most physical values are the image of no raw count at all, so this is where a typed
 * value becomes one the file can hold - and the grid then shows what was stored, not what was
 * typed. */
export function rawOf(physical: number, conversion: Conversion, datatype: string): number {
  const exact =
    conversion.kind === "linear"
      ? (physical - number(conversion.offset, 0)) / number(conversion.factor, 1)
      : physical;
  return datatype.startsWith("float") ? exact : Math.round(exact);
}

/** The tail of the arithmetic taken off, as `round_physical` takes it off server side. */
function rounded(value: number): number {
  return Number.parseFloat(value.toPrecision(12));
}

/** Whether this object can be drawn as a grid at all: text is not one. */
export function drawable(reply: ValuesReply): boolean {
  return reply.stated !== "text" && reply.shape.length > 0;
}

/** The axis at `position`, or `undefined` where this object references none there. */
function axisOf(reply: ValuesReply, position: string) {
  return reply.axes.find((axis) => axis.position === position);
}

/** The axis the columns are laid against: a map's x axis, or a curve's only one. */
function columnAxis(reply: ValuesReply) {
  return axisOf(reply, "x_axis") ?? axisOf(reply, "axis");
}

/** What an object or an axis is called beside its own numbers: `AxisA (Hz)`, or the bare name
 * where it carries no unit. Spec 5.2 labels both edges of every grid it draws, because the
 * header converts by the axis's rule and the values by the object's - two different units, and
 * nothing else on the screen says which belongs to which. */
function labelled(name: string, unit: string): string {
  return unit === "" ? name : `${name} (${unit})`;
}

/** The label in the corner, above the row labels (spec 5.2): the axis the rows are laid
 * against for a map - `AxisB (%)` - and the axis the columns are laid against for a single
 * row, where `AxisA (Hz)` sits over `CurveA (ms)`. `""` for a grid laid against indices. */
export function cornerLabel(reply: ValuesReply): string {
  if (reply.shape.length === 1) {
    const columns = columnAxis(reply);
    return columns === undefined ? "" : labelled(columns.name, columns.unit);
  }
  const rows = axisOf(reply, "y_axis");
  return rows === undefined ? "" : labelled(rows.name, rows.unit);
}

/** The label above the column header, naming the axis the columns are laid against - spec
 * 5.2's `AxisA (Hz) →` over a map, whose own corner is taken by the rows' axis. `""` for a
 * single row, whose corner names that axis itself, and for columns laid against indices. */
export function columnAxisLabel(reply: ValuesReply): string {
  if (reply.shape.length === 1) return "";
  const columns = columnAxis(reply);
  return columns === undefined ? "" : labelled(columns.name, columns.unit);
}

/** Why this grid cannot be written, or `null` where it can be: the two sentences
 * `object_values.set_cell` refuses each cause with, since a grid with no file to write into
 * has one cause or the other and never both. `owner` tells them apart - it is `null` only
 * where nothing produces the object at all, which the Python side measures and pins. */
export function readOnlyNote(reply: ValuesReply): string | null {
  if (reply.file !== null) return null;
  if (reply.owner === null) return `nothing produces '${reply.name}', so it has no values to set`;
  return `'${reply.name}' is produced in more than one place, so there is no one file to set it in`;
}

/** What a reader typed, as a number: `NaN` for anything that is not wholly one. `parseFloat`
 * takes a numeric prefix, so `1,5` - a decimal comma, which half the world writes - would read
 * as `1` and plan a write of it; `Number` weighs the whole string, and an empty cell is
 * nothing typed rather than the zero `Number("")` answers. */
export function typedNumber(text: string): number {
  return text.trim() === "" ? Number.NaN : Number(text);
}

/** The sentence a cell refuses what was typed with, or `null` where there is nothing to
 * refuse: a cell the reader has emptied is not a mistake, it is a cell nothing has been typed
 * into yet. */
export function typedRefusal(text: string): string | null {
  if (text.trim() === "" || !Number.isNaN(typedNumber(text))) return null;
  return `'${text}' is not a number`;
}

/** One breakpoint, in physical or in raw, as a column or a row header shows it. */
function reading(raw: number, conversion: Conversion, physical: boolean): string {
  return String(physical ? physicalOf(raw, conversion) : raw);
}

/** The indices `0`, `1`, `2`, … up to (not including) `count`. */
function indices(count: number): string[] {
  return Array.from({ length: count }, (_, index) => String(index));
}

/** The header above the columns: the x axis's readings where it states any, else indices. An
 * axis states a `size` and need not state an `init`, and then it has no breakpoints at all -
 * the grid degrades to indices there, as it does for an object with no axis, rather than to a
 * header of no columns and a row of no cells. */
export function columnHeader(reply: ValuesReply, physical: boolean): string[] {
  const axis = columnAxis(reply);
  if (axis !== undefined && axis.breakpoints.length > 0) {
    return axis.breakpoints.map((raw) => reading(raw, axis.conversion, physical));
  }
  return indices(reply.shape[reply.shape.length - 1] ?? 0);
}

/** The label down the side of each row: the y axis's readings where it states any, else
 * indices - and, for a single row, the object's own `name (unit)`, which is what spec 5.2
 * draws beside its values. */
export function rowHeader(reply: ValuesReply, physical: boolean): string[] {
  const axis = axisOf(reply, "y_axis");
  if (axis !== undefined && axis.breakpoints.length > 0) {
    return axis.breakpoints.map((raw) => reading(raw, axis.conversion, physical));
  }
  if (reply.shape.length === 1) return [labelled(reply.name, reply.unit)];
  return indices(reply.shape[0] ?? 0);
}

/** `[2]` for a single row, `[1][3]` for a map. */
export function cellAt(row: number, column: number, shape: number[]): string {
  return shape.length === 1 ? `[${column}]` : `[${row}][${column}]`;
}

/** "element 3" for a single row, "element 2, 4" for a map - `cellAt`'s own one-based phrase,
 * for a sentence rather than a pointer. */
export function elementLabel(row: number, column: number, shape: number[]): string {
  return shape.length === 1 ? `element ${column + 1}` : `element ${row + 1}, ${column + 1}`;
}

/** The sentence above the preview. */
export function cellSentence(
  reply: ValuesReply,
  row: number,
  column: number,
  raw: number,
  physical: boolean,
): string {
  const element = elementLabel(row, column, reply.shape);
  const value = physical ? physicalReading(raw, reply) : String(raw);
  return `Sets ${element} of ${reply.name} to ${value}`;
}

/** A raw count's physical reading, with the object's own unit where it has one. */
function physicalReading(raw: number, reply: ValuesReply): string {
  const value = physicalOf(raw, reply.conversion);
  return reply.unit === "" ? String(value) : `${value} ${reply.unit}`;
}
