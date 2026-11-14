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

/** Whether `datatype` stores a floating point number - which the double the page holds is too -
 * rather than a whole one. */
function floating(datatype: string): boolean {
  return datatype.startsWith("float");
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
  return floating(datatype) ? exact : Math.round(exact);
}

/** The tail of the arithmetic taken off, as `round_physical` takes it off server side. */
export function rounded(value: number): number {
  return Number.parseFloat(value.toPrecision(12));
}

/** Whether this object can be drawn as a grid at all: text is not one, and nor is an object the
 * server laid no cell out for - a list written for an object of no shape. An object of no shape
 * that states a number, or nothing, is a grid of one cell: its value. */
export function drawable(reply: ValuesReply): boolean {
  return reply.stated !== "text" && (reply.shape.length > 0 || reply.rows.length > 0);
}

/** Whether a table is pasted into this object's grid: not into the one cell of a scalar, which
 * the server refuses a table of (`set_values`) - one value is typed. */
export function pastes(reply: ValuesReply): boolean {
  return reply.shape.length > 0;
}

/** Whether the object's values are drawn as a picture under the grid: one point plots nothing, so
 * a scalar has none. */
export function plotDrawn(reply: ValuesReply): boolean {
  return reply.shape.length > 0;
}

/** What a grid says of how its producer states the object, or `null` where the file writes the
 * table out. Nothing at all is stated whatever the shape. One value stated for every element is a
 * sentence only of a grid of several: a scalar's one value is the one cell it fills. */
export function statedNote(reply: ValuesReply): string | null {
  if (reply.stated === "none") return "Nothing is stated.";
  if (reply.stated === "scalar" && reply.shape.length > 0) return "Stated once, for every cell.";
  return null;
}

/** The axis at `position`, or `undefined` where this object references none there. */
function axisOf(reply: ValuesReply, position: string) {
  return reply.axes.find((axis) => axis.position === position);
}

/** The axis the columns are laid against: a map's x axis, or a curve's only one. */
export function columnAxis(reply: ValuesReply) {
  return axisOf(reply, "x_axis") ?? axisOf(reply, "axis");
}

/** What an object or an axis is called beside its own numbers: `AxisA (Hz)` over the readings
 * its conversion makes, and the bare `AxisA` over raw counts - which are counts and not Hz, so
 * a unit there would be a label the numbers under it contradict. Spec 5.2 labels both edges of
 * every grid it draws, because the header converts by the axis's rule and the values by the
 * object's - two different units, and nothing else on the screen says which belongs to which. */
export function labelled(name: string, unit: string, physical: boolean): string {
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

/** 2^53, where a double - the number the page holds - stops holding every whole number. Past it
 * `Number` reads a whole number as a double beside it, saying nothing: `9007199254740993` as
 * `9007199254740992`, and `0x8000000000000001`, a 64 bit mask, as 2^63. Planned from what it
 * read, the first was written as `9007199254740992`; the mask as `9223372036854776000`, the
 * shortest decimal of 2^63, which is `0x80000000000000C0` - its low bit cleared and two others
 * set; and `18446744073709551615`, the most a uint64 holds, read as 2^64, was refused as a number
 * that does not fit, which nobody typed. */
const EXACT = 2n ** 53n;

/** How many digits 2^53 is written in, `9007199254740992`: a whole part of fewer is inside it,
 * and a whole part of more is past it, whatever the digits. */
const EXACT_DIGITS = 16;

/** Why a number past ±2^53 is refused, in the same words wherever it was typed or pasted. */
const INEXACT = "where the page cannot hold every whole number exactly";

/** A decimal spelling `Number` reads, its sign, whole digits, fraction and exponent apart: `5.`,
 * `.5` and `1e19` among them. `Number` has read the text before this is asked, so a match holds a
 * digit somewhere - `.` and `e5` are no numbers. */
const DECIMAL = /^([+-]?)(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/;

/** A whole number in hexadecimal, binary or octal digits, which `Number` reads with no sign. */
const NONDECIMAL = /^0(?:[xX][0-9a-fA-F]+|[bB][01]+|[oO][0-7]+)$/;

/** A whole number in decimal digits, with or without a sign. */
const WHOLE = /^[+-]?\d+$/;

/** The sentence a number past ±2^53 is refused with, naming it as `said` and its side. */
function pastSentence(said: string, side: -1 | 1): string {
  return `'${said}' is past ${side < 0 ? "-" : ""}2^53, ${INEXACT}`;
}

/** The sentence a whole number past ±2^53 is refused with where it is spelled as one - in
 * digits, or in hexadecimal, binary or octal - or `null` for any other text. What a field with no
 * datatype to weigh it by refuses: a limit, which a float states as freely as any number, and
 * which a fraction or an exponent spells as the double it is. */
export function wholePast(text: string): string | null {
  const trimmed = text.trim();
  if (!WHOLE.test(trimmed) && !NONDECIMAL.test(trimmed)) return null;
  // `BigInt` reads exactly these spellings, a sign on decimal digits included.
  const whole = BigInt(trimmed);
  if (whole > EXACT) return pastSentence(text, 1);
  return whole < -EXACT ? pastSentence(text, -1) : null;
}

/** What a text says as a number: the double `Number` reads it as; which side of ±2^53 the number
 * it spells lies past, `0` where it lies inside; and whether that number has a fraction. */
interface Spelled {
  double: number;
  side: -1 | 0 | 1;
  fraction: boolean;
}

/** `text` read once as the number it spells, or `null` where it spells none `Number` reads. The
 * spelling decides before `BigInt` is asked anything: only a whole part of sixteen digits - the
 * one length that falls either side of 2^53 - and a hexadecimal, binary or octal number are
 * compared with 2^53 exactly. Measured on 4,096 fractional cells, this reads them in about a
 * millisecond, four or five times what `Number` alone takes; asking `BigInt` of every cell, which
 * throws for a fraction, took over twenty. `Infinity` is read as the double it is, on no side. */
function spelled(text: string): Spelled | null {
  const trimmed = text.trim();
  const double = Number(trimmed);
  if (trimmed === "" || Number.isNaN(double)) return null;
  const decimal = DECIMAL.exec(trimmed);
  if (decimal !== null) return exactly(double, decimal);
  if (NONDECIMAL.test(trimmed)) {
    return { double, side: BigInt(trimmed) > EXACT ? 1 : 0, fraction: false };
  }
  return { double, side: 0, fraction: false };
}

/** A decimal spelling's side of ±2^53 and whether it has a fraction, from its digits: the number
 * is its significant digits times ten to `scale`, so its whole part has `wholeDigits` digits -
 * none, or fewer, for a number under one - and is compared with 2^53 itself only where those are
 * sixteen. Past 2^53 by a fraction, `9007199254740992.5`, is past it. */
function exactly(double: number, match: RegExpExecArray): Spelled {
  const [, sign, whole = "", fraction = "", power = "0"] = match;
  const digits = `${whole}${fraction}`.replace(/^0+/, "");
  const significant = digits.replace(/0+$/, "");
  if (significant === "") return { double, side: 0, fraction: false };
  const scale = Number(power) - fraction.length + (digits.length - significant.length);
  const wholeDigits = significant.length + scale;
  let past = wholeDigits > EXACT_DIGITS;
  if (wholeDigits === EXACT_DIGITS) {
    const head = BigInt(significant.slice(0, EXACT_DIGITS).padEnd(EXACT_DIGITS, "0"));
    past = head > EXACT || (head === EXACT && scale < 0);
  }
  return { double, side: past ? (sign === "-" ? -1 : 1) : 0, fraction: scale < 0 };
}

/** How a cell of `datatype` reads `text`, naming it as `said` where it refuses it: the double it
 * takes, or the sentence. A float cell takes the double whatever the spelling - the double is
 * what a float holds, and FLT_MAX is a whole number past 2^53 as much as 2^64 is. Any other cell
 * refuses a number past ±2^53 in any spelling, and a fraction the double drops, which it would
 * plan as the whole number the double reads it as; a fraction the double keeps is the server's
 * to refuse an integer, in raw, and the conversion's to round, in physical. */
function readOf(
  text: string,
  said: string,
  datatype: string,
): { double: number } | { refusal: string } {
  const read = spelled(text);
  if (read === null) return { refusal: `'${said}' is not a number` };
  if (floating(datatype)) return { double: read.double };
  if (read.side !== 0) return { refusal: pastSentence(said, read.side) };
  if (read.fraction && Number.isInteger(read.double)) {
    return { refusal: `'${said}' is not a whole number, and the page cannot hold its fraction` };
  }
  return { double: read.double };
}

/** The raw count `text`, typed into a cell of `reply`, writes, or `null` where it writes none:
 * nothing typed, or a text the cell refuses (`typedRefusal`), for which no plan is asked.
 * `parseFloat` takes a numeric prefix, so `1,5` - a decimal comma, which half the world writes -
 * would read as `1` and plan a write of it; `Number` weighs the whole string, and an empty cell is
 * nothing typed rather than the zero `Number("")` answers. */
export function typedRaw(text: string, reply: ValuesReply, physical: boolean): number | null {
  if (text.trim() === "") return null;
  const read = readOf(text, text, reply.datatype);
  if ("refusal" in read) return null;
  return physical ? rawOf(read.double, reply.conversion, reply.datatype) : read.double;
}

/** The sentence a cell of `reply` refuses what was typed with, or `null` where there is nothing
 * to refuse: a cell the reader has emptied is not a mistake, it is a cell nothing has been typed
 * into yet. */
export function typedRefusal(text: string, reply: ValuesReply): string | null {
  if (text.trim() === "") return null;
  const read = readOf(text, text, reply.datatype);
  return "refusal" in read ? read.refusal : null;
}

/** The limits as the line above the grid says them: each the double it crossed as, but a whole
 * number past 2^53 in the digits the route sends with it (`ValuesReply.maximum_text`), the
 * double printing another number - 18446744073709552000 for the most a uint64 holds. */
export function limitsLine(reply: ValuesReply): string {
  return `${reply.minimum_text ?? reply.minimum} … ${reply.maximum_text ?? reply.maximum}`;
}

/** Why this grid draws none of its numbers, or `null` where it draws them. Text is no grid at
 * all, whatever it holds. And the route marks a block whose numbers - this one's or an axis's -
 * hold a whole number the page cannot draw as the number it is and set back (`ValuesReply.
 * unshown`): past 2^53, which reaches the page as the double nearest it, or at 2^53 in a 64 bit
 * integer, which refuses a value at 2^53. */
export function noGridNote(reply: ValuesReply): string | null {
  if (reply.stated === "text") return `'${reply.name}' is initialised with text, not with a grid`;
  if (reply.unshown === null) return null;
  return `'${reply.unshown}' holds a whole number at or past ±2^53, ${INEXACT}, so the grid cannot show it`;
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

/** The rows and columns the object itself takes, as a table is counted: what a paste must hold,
 * and what a cell typed into must lie inside (`typedCells.ts`). A scalar, which has no shape, is
 * one row of one: its value is its one cell. A reply with no cell at all never reaches here,
 * since `ValuesPage` answers "has no cell for a value to sit in" before it draws a grid. */
export function wanted(reply: ValuesReply): [number, number] {
  const [first = 1, second] = reply.shape;
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
          "is not clear what it means; paste the column unformatted",
      };
    }
  }
  const read: number[][] = [];
  for (const row of values) {
    const counts: number[] = [];
    for (const cell of row) {
      const read = readOf(decimal ? cell.replace(",", ".") : cell, cell, reply.datatype);
      if ("refusal" in read) return { rows: null, refusal: read.refusal };
      counts.push(physical ? rawOf(read.double, reply.conversion, reply.datatype) : read.double);
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
  // A scalar has one column, which is its value; an object with no cell, none.
  if (reply.shape.length === 0) return reply.rows.length > 0 ? ["Value"] : [];
  const axis = columnAxis(reply);
  if (axis !== undefined && axis.breakpoints.length > 0) {
    return axis.breakpoints.map((raw) => reading(raw, axis.conversion, physical));
  }
  return indices(wanted(reply)[1]);
}

/** The label down the side of each row: the y axis's readings where it states any, else
 * indices - and, for a single row, the object's own `name (unit)`, which is what spec 5.2
 * draws beside its values. */
export function rowHeader(reply: ValuesReply, physical: boolean): string[] {
  const axis = axisOf(reply, "y_axis");
  if (axis !== undefined && axis.breakpoints.length > 0) {
    return axis.breakpoints.map((raw) => reading(raw, axis.conversion, physical));
  }
  // A scalar's one row is the object itself, as a single row's is.
  if (reply.shape.length === 0) {
    return reply.rows.length > 0 ? [labelled(reply.name, reply.unit, physical)] : [];
  }
  if (reply.shape.length === 1) return [labelled(reply.name, reply.unit, physical)];
  return indices(wanted(reply)[0]);
}

/** A cell of the values grid the reader has typed into: where it is, what was typed, and whether
 * it was typed in physical - the reading its text is read in, whichever the grid shows now. The
 * grid holds every cell typed into (`typedCells.ts`). */
export interface TypedCell {
  row: number;
  column: number;
  typed: string;
  physical: boolean;
}

/** What one cell's field shows. A cell typed into shows what was typed, in the reading it was
 * typed in; in the other, the count its text comes to, read as the grid now reads - so that
 * turning the grid from physical to raw neither changes what a typed cell sets nor shows a
 * physical number among raw counts - or the text itself, where it comes to no count. Any other
 * cell shows its raw count, or what that count reads as in physical; one its row does not reach
 * reads 0, as the startup code makes it. */
export function cellText(
  reply: ValuesReply,
  typed: readonly TypedCell[],
  row: number,
  column: number,
  physical: boolean,
): string {
  const held = typed.find((cell) => cell.row === row && cell.column === column);
  if (held === undefined)
    return reading(reply.rows[row]?.[column] ?? 0, reply.conversion, physical);
  if (held.physical === physical) return held.typed;
  const raw = typedRaw(held.typed, reply, held.physical);
  return raw === null ? held.typed : reading(raw, reply.conversion, physical);
}

/** How many characters wide each of the grid's `columns` is drawn: the longest text its fields
 * show, the numbers of its rows and what is typed into them alike. A field cut short hides the end
 * of its number with no sign of it, and under right aligned digits a cut number reads as a smaller
 * one - 4000000000 as 400000. Column by column, so that one long number widens its own column and
 * leaves the others as narrow as theirs; counted in characters, which the grid's monospace sets
 * one `ch` apiece. */
export function columnChars(
  reply: ValuesReply,
  typed: readonly TypedCell[],
  physical: boolean,
  columns: number,
): number[] {
  return Array.from({ length: columns }, (_, column) =>
    Math.max(
      0,
      ...reply.rows.map((_, row) => cellText(reply, typed, row, column, physical).length),
    ),
  );
}

/** `[2]` for a single row, `[1][3]` for a map, and none at all for a scalar, whose one cell is the
 * object itself: the pointer ends at its `init`. */
export function cellAt(row: number, column: number, shape: number[]): string {
  if (shape.length === 0) return "";
  return shape.length === 1 ? `[${column}]` : `[${row}][${column}]`;
}

/** "element 3" for a single row, "element 2, 4" for a map - `cellAt`'s own one-based phrase,
 * for a sentence rather than a pointer - and "the value" for a scalar. */
export function elementLabel(row: number, column: number, shape: number[]): string {
  if (shape.length === 0) return "the value";
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
export function physicalReading(raw: number, reply: ValuesReply): string {
  const value = physicalOf(raw, reply.conversion);
  return reply.unit === "" ? String(value) : `${value} ${reply.unit}`;
}

/** The sentence above a pasted table's preview, as `cellSentence` is a cell's: what is about to
 * happen, so that a reader who pasted physical values and sees raw counts in the hunks is told
 * the two are one change and not two. */
export function pasteSentence(reply: ValuesReply): string {
  return `Replaces every value of ${reply.name}`;
}
