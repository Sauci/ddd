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

/** What an object or an axis is called beside its own numbers: `AxisA (Hz)` over the readings
 * its conversion makes, and the bare `AxisA` over raw counts - which are counts and not Hz, so
 * a unit there would be a label the numbers under it contradict. Spec 5.2 labels both edges of
 * every grid it draws, because the header converts by the axis's rule and the values by the
 * object's - two different units, and nothing else on the screen says which belongs to which. */
function labelled(name: string, unit: string, physical: boolean): string {
  return physical && unit !== "" ? `${name} (${unit})` : name;
}

/** The label in the corner, above the row labels (spec 5.2): the axis the rows are laid
 * against for a map - `AxisB (%)` - and the axis the columns are laid against for a single
 * row, where `AxisA (Hz)` sits over `CurveA (ms)`. `""` for a grid laid against indices. */
export function cornerLabel(reply: ValuesReply, physical: boolean): string {
  if (reply.shape.length === 1) {
    const columns = columnAxis(reply);
    return columns === undefined ? "" : labelled(columns.name, columns.unit, physical);
  }
  const rows = axisOf(reply, "y_axis");
  return rows === undefined ? "" : labelled(rows.name, rows.unit, physical);
}

/** The label above the column header, naming the axis the columns are laid against - spec
 * 5.2's `AxisA (Hz) →` over a map, whose own corner is taken by the rows' axis. `""` for a
 * single row, whose corner names that axis itself, and for columns laid against indices. */
export function columnAxisLabel(reply: ValuesReply, physical: boolean): string {
  if (reply.shape.length === 1) return "";
  const columns = columnAxis(reply);
  return columns === undefined ? "" : labelled(columns.name, columns.unit, physical);
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

/** A pasted block, read against the object the grid is showing. Exactly one of the two fields is
 * set, so a reader narrows on `refusal === null` and needs no fallback for the other. */
export type Pasted = { rows: number[][]; refusal: null } | { rows: null; refusal: string };

/** The block as a spreadsheet writes it: rows by newline, cells by tab, a trailing newline
 * dropped because every spreadsheet adds one. */
function celled(text: string): string[][] {
  const lines = text.replace(/\r\n/g, "\n").replace(/\n$/, "").split("\n");
  return lines.map((line) => line.split("\t"));
}

/** The rows and columns the object itself takes, as a table is counted. */
function wanted(reply: ValuesReply): [number, number] {
  const [first = 0, second] = reply.shape;
  return second === undefined ? [1, first] : [first, second];
}

/** `1 row of 6`, `4 rows of 6` - how a block is counted, the same spelling `_table` uses in
 * `object_values.py`. The word "values" is left to whichever sentence wants it. */
function table(rows: number, columns: number): string {
  return `${rows} row${rows === 1 ? "" : "s"} of ${columns}`;
}

/** `6 and 3`, `6, 3 and 9` - a list as a sentence says it, commas between all but the last and
 * `and` before that one. `join(" and ")` reads for two and turns three into `6 and 3 and 9`.
 * Called only where there are at least two, since one width is no ragged block - so the tail
 * is taken by `slice`, which has no first element to fall back from. */
function listed(numbers: number[]): string {
  const all = numbers.map(String);
  return `${all.slice(0, -1).join(", ")} and ${all.slice(-1).join("")}`;
}

/** A comma before exactly three digits at the end of a cell - `1,200`, which an English
 * spreadsheet writes for twelve hundred and a French one for one and a fifth. Two digits are no
 * grouping (`1,25`) and neither are four (`1,2345`), so both stay decimals. */
const GROUPED = /,\d{3}$/;

/** The first cell whose comma could be a thousands separator, or `undefined` where no cell's
 * could. Trimmed, because a cell padded by the spreadsheet is the same number. */
function groupedCell(cells: string[][]): string | undefined {
  return cells.flat().find((cell) => GROUPED.test(cell.trim()));
}

/** Whether a comma is this block's decimal separator: only where no cell states a point and no
 * cell states two commas, so `1,5` reads as one and a half and `1.234,56` never does. */
function commaIsDecimal(cells: string[][]): boolean {
  const all = cells.flat();
  if (all.some((cell) => cell.includes("."))) return false;
  return all.every((cell) => (cell.match(/,/g) ?? []).length <= 1);
}

/** Whether two *different* cells disagree about the separator, which is the one case worth its
 * own sentence. A single cell holding both - `1.234,56` - is not a block that mixes them; it is
 * a cell that is not a number, and saying so names the cell a reader has to go and fix. */
function mixesSeparators(cells: string[][]): boolean {
  const all = cells.flat();
  return (
    all.some((cell) => cell.includes(".") && !cell.includes(",")) &&
    all.some((cell) => cell.includes(",") && !cell.includes("."))
  );
}

export function pasted(text: string, reply: ValuesReply, physical: boolean): Pasted {
  const cells = celled(text);
  const widths = new Set(cells.map((row) => row.length));
  if (widths.size > 1) {
    return {
      rows: null,
      refusal: `this is not a table: its rows are ${listed([...widths])} values long`,
    };
  }
  // Every row is the same length by now, so the widest is the width - and taking it this way
  // needs no index into `cells`, which would carry a fallback nothing can reach: a split on a
  // non-empty separator always answers at least one row.
  const width = Math.max(0, ...widths);
  const [rows, columns] = wanted(reply);
  const header = cells.length === rows + 1 && width === columns + 1;
  if (!header && (cells.length !== rows || width !== columns)) {
    return {
      rows: null,
      refusal:
        `expected ${table(rows, columns)}, or ${table(rows + 1, columns + 1)} with a header; ` +
        `got ${table(cells.length, width)}`,
    };
  }
  const values = header ? cells.slice(1).map((row) => row.slice(1)) : cells;
  const decimal = commaIsDecimal(values);
  if (mixesSeparators(values)) {
    return {
      rows: null,
      refusal: "this mixes '.' and ',' as decimal separators, so it is not clear what it means",
    };
  }
  // The one comma nothing can decide, refused rather than read: `1,200` is twelve hundred from
  // a spreadsheet that groups thousands and one and a fifth from one that writes decimals with
  // a comma, and both are ordinary. Read either way it stores a calibration nobody typed - a
  // thousand times too small, or a thousand times too large - and says nothing, which is the
  // guessing this whole rule exists to refuse. Only where the comma would otherwise be the
  // decimal separator: a block that states a point elsewhere has already said what its commas
  // are, and `mixesSeparators` above answers that one.
  if (decimal) {
    const grouped = groupedCell(values);
    if (grouped !== undefined) {
      return {
        rows: null,
        refusal:
          `the comma in '${grouped}' could be a decimal point or a thousands separator, so it ` +
          "is not clear what it means; paste the block with no thousands separators",
      };
    }
  }
  const read: number[][] = [];
  for (const row of values) {
    const counts: number[] = [];
    for (const cell of row) {
      const typed = typedNumber(decimal ? cell.replace(",", ".") : cell);
      if (Number.isNaN(typed)) return { rows: null, refusal: `'${cell}' is not a number` };
      counts.push(physical ? rawOf(typed, reply.conversion, reply.datatype) : typed);
    }
    read.push(counts);
  }
  return { rows: read, refusal: null };
}

/** The line under the grid saying what shape a paste wants - the only way the feature is
 * discoverable, and the hint that stops the commonest refusal before it happens. */
export function pasteHint(reply: ValuesReply): string {
  const [rows, columns] = wanted(reply);
  return `Paste ${table(rows, columns)} values from a spreadsheet to replace them all.`;
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
  if (reply.shape.length === 1) return [labelled(reply.name, reply.unit, physical)];
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

/** The sentence above a pasted table's preview, as `cellSentence` is a cell's: what is about to
 * happen, so that a reader who pasted physical values and sees raw counts in the hunks is told
 * the two are one change and not two. */
export function pasteSentence(reply: ValuesReply): string {
  return `Replaces every value of ${reply.name}`;
}
