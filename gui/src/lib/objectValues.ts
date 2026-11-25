import type { ValuesReply } from "../api/types";
import {
  type CommaMeaning,
  type Decimal,
  decimalOfDouble,
  decimalText,
  doubleOf,
  floatReading,
  type Linear,
  notANumber,
  pastedComma,
  physicalValue,
  rawCount,
  readNumber,
  significant,
  singleOf,
  typedComma,
} from "./numbers";

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

/** A linear conversion's factor and offset as the decimals the reply spells them in, or `null` for
 * any other conversion - the identity, an enum, a string - which hands the raw count back, as
 * `raw_reading` in the models does and says. A factor of zero, which the models refuse, is none
 * either. */
function linearOf(conversion: Conversion): Linear | null {
  if (conversion.kind !== "linear") return null;
  const factor = number(conversion.factor, 1);
  if (factor === 0) return null;
  return {
    factor: decimalOfDouble(factor),
    offset: decimalOfDouble(number(conversion.offset, 0)),
  };
}

/** Where one raw count sits as a physical value, for a picture to place it: the count through a
 * linear conversion, in the double arithmetic, which a position needs no more digits of. What a
 * reader reads is `physicalText`. */
export function physicalOf(raw: number, conversion: Conversion): number {
  if (conversion.kind !== "linear") return raw;
  return raw * number(conversion.factor, 1) + number(conversion.offset, 0);
}

/** Whether `datatype` stores a floating point number - which the double the page holds is too -
 * rather than a whole one. */
function floating(datatype: string): boolean {
  return datatype.startsWith("float");
}

/** The readings worked out so far, by datatype, conversion and raw count: a grid draws each of its
 * cells more than once a keystroke, and a float's reading is looked for. Let go whole once it holds
 * more than `HELD` of them, so that a session reading grid after grid holds no more. */
const READINGS = new Map<string, string>();

/** The most readings `READINGS` holds before it is let go. */
const HELD = 50_000;

/** How many readings are held now, which is never more than one past `HELD`. */
export function heldReadings(): number {
  return READINGS.size;
}

/** How a raw count of `datatype` reads in raw: the count, a `float32`'s as the float32 its file's
 * number rounds to, as briefly as it reads back (`singleOf`, fix round 1, M4) - float32 data a
 * script spelled at double precision, `0.10000000149011612`, reads 0.1. */
export function rawText(raw: number, datatype: string): string {
  return String(datatype === "float32" ? singleOf(raw) : raw);
}

/**
 * How a raw count of `datatype` reads in physical under `conversion` (15:M6), never cut at twelve
 * significant digits - 1234567890123 is 1234567890123, where twelve digits read 1234567890120 -
 * and never with the tail of the double arithmetic - 255 counts of 0.03 are 7.65, not
 * 7.6499999999999995. A whole datatype's count reads as the count times the factor, plus the
 * offset, exactly; a float's as the shortest decimal whose own raw count is the same float again
 * (`floatReading`). Anything but a linear conversion reads as the count itself (`rawText`).
 */
export function physicalText(raw: number, conversion: Conversion, datatype: string): string {
  const linear = linearOf(conversion);
  if (linear === null) return rawText(raw, datatype);
  const key = `${datatype}|${String(conversion.factor)}|${String(conversion.offset)}|${raw}`;
  const known = READINGS.get(key);
  if (known !== undefined) return known;
  const text = decimalText(
    floating(datatype) ? floatReading(raw, linear, datatype) : physicalValue(raw, linear),
  );
  if (READINGS.size > HELD) READINGS.clear();
  READINGS.set(key, text);
  return text;
}

/** The raw count a physical value needs, as a typed one comes to it (`rawCount`), for a picture to
 * place a limit by; where the page could send none - a whole count past 2^53, a float beyond its
 * datatype or rounding to zero - the count the double arithmetic places it at. */
export function rawOf(physical: number, conversion: Conversion, datatype: string): number {
  const count = rawCount(decimalOfDouble(physical), linearOf(conversion), datatype);
  if ("raw" in count) return count.raw;
  return conversion.kind === "linear"
    ? (physical - number(conversion.offset, 0)) / number(conversion.factor, 1)
    : physical;
}

/** A computed value with the tail of the arithmetic taken off, to twelve significant digits, as
 * `round_physical` takes it off server side - an exact half to the even digit, as it does. */
export function rounded(value: number): number {
  return significant(value, 12);
}

/** Whether this object can be drawn as a grid at all: text is not one, and nor is an object the
 * server laid no cell out for - a list written for an object of no shape. An object of no shape
 * that states a number, or nothing, is a grid of one cell: its value. */
export function drawable(reply: ValuesReply): boolean {
  return reply.stated !== "text" && (reply.shape.length > 0 || reply.rows.length > 0);
}

/** Whether the grid is the one cell of a scalar, which keeps its natural width where a curve or a map
 * is laid across the page. */
export function oneCell(reply: ValuesReply): boolean {
  return reply.shape.length === 0;
}

/** Whether a table is pasted into this object's grid: not into the one cell of a scalar, which
 * the server refuses a table of (`set_values`) - one value is typed. */
export function pastes(reply: ValuesReply): boolean {
  return reply.shape.length > 0;
}

/** Whether the object's values are drawn as a picture under the grid: one point plots nothing, so
 * a scalar has none. The picture follows the cells, drawing what the file states (`drawnRows`):
 * a grid stating nothing, every cell of it hollow, has no point to place and draws none either,
 * where it drew a line of the startup code's zeros under cells saying the file holds none. */
export function plotDrawn(reply: ValuesReply): boolean {
  return reply.shape.length > 0 && reply.stated !== "none";
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
 * `9007199254740992`. Planned from what it read, that was written as `9007199254740992`; and
 * `18446744073709551615`, the most a uint64 holds, read as 2^64, was refused as a number that does
 * not fit, which nobody typed. A 64 bit mask written in hexadecimal lost its low bits the same way,
 * before hexadecimal was refused as no decimal notation (`numbers.ts`). */
const EXACT = 2n ** 53n;

/** How many digits 2^53 is written in, `9007199254740992`: a whole part of fewer is inside it,
 * and a whole part of more is past it, whatever the digits. */
const EXACT_DIGITS = 16;

/** Why a number past ±2^53 is refused, in the same words wherever it was typed or pasted. */
const INEXACT = "where the page cannot hold every whole number exactly";

/** A whole number in decimal digits, with or without a sign. */
const WHOLE = /^[+-]?\d+$/;

/** The sentence a number past ±2^53 is refused with, naming it as `said` and its side. */
function pastSentence(said: string, side: -1 | 1): string {
  return `'${said}' is past ${side < 0 ? "-" : ""}2^53, ${INEXACT}`;
}

/** The sentence a whole number past ±2^53 is refused with where it is spelled in decimal digits,
 * or `null` for any other text. What a field with no datatype to weigh it by refuses: a limit,
 * which a float states as freely as any number, and which a fraction or an exponent spells as the
 * double it is. */
export function wholePast(text: string): string | null {
  const trimmed = text.trim();
  if (!WHOLE.test(trimmed)) return null;
  // `BigInt` reads exactly this spelling, a sign on decimal digits included.
  const whole = BigInt(trimmed);
  if (whole > EXACT) return pastSentence(text, 1);
  return whole < -EXACT ? pastSentence(text, -1) : null;
}

/** Which side of ±2^53 a decimal lies past, `0` where it lies inside, from its digits: the number
 * is its significant digits times ten to its exponent, so its whole part has `wholeDigits` digits -
 * none, or fewer, for a number under one - and is compared with 2^53 itself only where those are
 * sixteen, the one length that falls either side of it. Past 2^53 by a fraction,
 * `9007199254740992.5`, is past it. Measured on 4,096 fractional cells, reading their numbers this
 * way costs about a millisecond, four or five times what `Number` alone takes; asking `BigInt` of
 * every cell, which throws for a fraction, took over twenty. */
function sideOf(decimal: Decimal): -1 | 0 | 1 {
  const { negative, digits, exponent } = decimal;
  const wholeDigits = digits.length + exponent;
  let past = wholeDigits > EXACT_DIGITS;
  if (wholeDigits === EXACT_DIGITS) {
    const head = BigInt(digits.slice(0, EXACT_DIGITS).padEnd(EXACT_DIGITS, "0"));
    past = head > EXACT || (head === EXACT && exponent < 0);
  }
  if (!past) return 0;
  return negative ? -1 : 1;
}

/** What a cell reads a text as: the raw count it writes, or the sentence it is refused with. */
type CellRead = { raw: number } | { refusal: string; ambiguous: boolean };

/** Why a float of `datatype` holds no value `said` comes to: past the most it holds, or nonzero
 * where it rounds to zero - which the double it would be sent as could not say. */
function floatRefusal(
  said: string,
  datatype: string,
  beyond: boolean,
): { refusal: string; ambiguous: false } {
  return {
    refusal: beyond
      ? `'${said}' is past what a ${datatype} holds`
      : `'${said}' rounds to zero in ${datatype}`,
    ambiguous: false,
  };
}

/** The raw count `decimal`, typed in raw into a cell of `datatype`, writes - the text read is the
 * count - or the sentence it is refused with, naming it as `said`. A float cell takes the double
 * whatever the digits - the double is what a float holds, and FLT_MAX is a whole number past 2^53
 * as much as 2^64 is - but none past the most a double holds, nor one rounding to zero in it; a
 * `float32`'s is planned as the float32 it rounds to (`singleOf`). Any
 * other cell refuses a number past ±2^53, and a fraction the double drops, which it would plan as
 * the whole number the double reads it as; a fraction the double keeps is the server's to refuse
 * an integer. */
function rawRead(decimal: Decimal, said: string, datatype: string): CellRead {
  const double = doubleOf(decimal);
  if (floating(datatype)) {
    if (!Number.isFinite(double)) return floatRefusal(said, datatype, true);
    if (double === 0 && decimal.digits !== "") return floatRefusal(said, datatype, false);
    // A float32 holds the float the number rounds to, which is what is planned: C's FLT_MAX,
    // 3.4028235e38, lies past FLT_MAX's own double, which the server refuses. What rounds to
    // zero in a float32 is the server's to refuse, as the double typed.
    if (datatype === "float32" && Math.fround(double) !== 0) return { raw: singleOf(double) };
    return { raw: double };
  }
  const side = sideOf(decimal);
  if (side !== 0) return { refusal: pastSentence(said, side), ambiguous: false };
  if (decimal.exponent < 0 && Number.isInteger(double)) {
    return {
      refusal: `'${said}' is not a whole number, and the page cannot hold its fraction`,
      ambiguous: false,
    };
  }
  return { raw: double };
}

/** The raw count `decimal`, typed in physical into a cell of `reply`, writes (`rawCount`), or the
 * sentence it is refused with, naming it as `said`. A whole datatype's count is weighed against
 * ±2^53, not the value typed (task 1's n1: 1e16 at a factor of 1000 is 1e13, inside it), and a
 * float's against what its datatype holds. A fraction is the conversion's to round, the decimal
 * holding every digit of it. */
function physicalRead(decimal: Decimal, said: string, reply: ValuesReply): CellRead {
  const linear = linearOf(reply.conversion);
  const count = rawCount(decimal, linear, reply.datatype);
  if ("raw" in count) return count;
  if ("past" in count) {
    // Under no conversion the value typed is the count, and is said to be past 2^53 itself.
    if (linear === null) return { refusal: pastSentence(said, count.past), ambiguous: false };
    return {
      refusal: `'${said}' comes to a raw count past ${count.past < 0 ? "-" : ""}2^53, ${INEXACT}`,
      ambiguous: false,
    };
  }
  return floatRefusal(said, reply.datatype, "beyond" in count);
}

/** Whether two decimals are the one number. */
function same(a: Decimal, b: Decimal): boolean {
  return a.negative === b.negative && a.digits === b.digits && a.exponent === b.exponent;
}

/**
 * One bound of a range typed for `datatype`, read as a cell of it reads a number (task 1's n3): the
 * double the page sends, or the sentence it is refused with, naming it as `said`. A float's bound
 * is the double it is, however it is spelled - 1e19 among them, which digits past 2^53 once
 * refused - but none past the most the float holds, nor one rounding to zero in it. Any other
 * datatype's is refused past ±2^53 in every spelling, an exponent's too, and wherever the double
 * would send another number than the one typed: a fraction it cannot hold, which from 2^51 on it
 * sent rounded.
 */
export function boundRead(
  decimal: Decimal,
  said: string,
  datatype: string,
): { value: number } | { refusal: string } {
  const double = doubleOf(decimal);
  if (floating(datatype)) {
    if (Number.isFinite(double) && (double !== 0 || decimal.digits === ""))
      return { value: double };
    return { refusal: floatRefusal(said, datatype, !Number.isFinite(double)).refusal };
  }
  const side = sideOf(decimal);
  if (side !== 0) return { refusal: pastSentence(said, side) };
  if (!same(decimalOfDouble(double), decimal)) {
    return { refusal: `'${said}' has a fraction the page cannot hold exactly` };
  }
  return { value: double };
}

/** What `text`, typed into a cell of `reply` in physical or in raw, comes to: the raw count it
 * writes, the sentence the cell refuses it with - `ambiguous` where that is a comma that could be
 * either, which a choice of what it means answers (`numbers.ts`) - or `null` for a cell the reader
 * has emptied, which is no mistake but a cell nothing has been typed into yet. `meaning` says what
 * a comma that could be either is. */
export function cellRead(
  text: string,
  reply: ValuesReply,
  physical: boolean,
  meaning?: CommaMeaning,
): CellRead | null {
  if (text.trim() === "") return null;
  const read = readNumber(text, meaning);
  if (!("decimal" in read)) return read;
  return physical
    ? physicalRead(read.decimal, text, reply)
    : rawRead(read.decimal, text, reply.datatype);
}

/** The raw count `text`, typed into a cell of `reply`, writes, or `null` where it writes none:
 * nothing typed, or a text the cell refuses (`cellRead`), for which no plan is asked. */
export function typedRaw(
  text: string,
  reply: ValuesReply,
  physical: boolean,
  meaning?: CommaMeaning,
): number | null {
  const read = cellRead(text, reply, physical, meaning);
  return read !== null && "raw" in read ? read.raw : null;
}

/** The sentence a cell of `reply` refuses what was typed with, or `null` where there is nothing
 * to refuse (`cellRead`). */
export function typedRefusal(
  text: string,
  reply: ValuesReply,
  physical: boolean,
  meaning?: CommaMeaning,
): string | null {
  const read = cellRead(text, reply, physical, meaning);
  return read !== null && "refusal" in read ? read.refusal : null;
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

/** A pasted block, read against the object the grid is showing. Exactly one of `rows` and
 * `refusal` is set, so a reader narrows on `refusal === null` and needs no fallback for the
 * other; `ambiguous` is the value whose comma could be a decimal point or a thousands separator,
 * where that is what is refused - the choice of what it means is offered for it. `header` says
 * whether the block's first row and column were taken for a header, and are not written, which
 * the sentence over its preview says (`pasteSentence`, decision 15.1): never of a refused block,
 * which writes nothing. */
export type Pasted =
  | { rows: number[][]; header: boolean; refusal: null; ambiguous: null }
  | { rows: null; header: false; refusal: string; ambiguous: string | null };

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

/**
 * A block pasted into the grid of `reply`, read in physical or in raw: the raw counts it writes,
 * row by row, or why it writes none.
 *
 * Its commas are read by the block's own rule (`pastedComma`, `numbers.ts`): a spreadsheet writes
 * every number of a block with the same separators, so one value whose comma can only be a decimal
 * point - `0,5`, or `0,125`, where a first group of 0 groups no thousands - makes every comma of
 * the block one, `1,250` beside it among them; a block writing its decimal point both ways is
 * refused. A comma nothing in the block decides is read as `chosen` says, and refused until it
 * says - `1,200` is twelve hundred from a spreadsheet that groups thousands and one and a fifth
 * from one that writes decimals with a comma, and read either way, without asking, it stored a
 * calibration nobody typed. A header row and column, pasted along with the values, are dropped
 * unread: their readings are no part of what is written. Nothing but the block's size tells a
 * header from values - a block of the size a header makes is read so whatever it holds - so the
 * answer says whether it was (`header`), for the sentence over the preview to say.
 */
export function pasted(
  text: string,
  reply: ValuesReply,
  physical: boolean,
  chosen?: CommaMeaning,
): Pasted {
  const cells = celled(text);
  const widths = new Set(cells.map((row) => row.length));
  if (widths.size > 1) {
    return {
      rows: null,
      header: false,
      refusal: `this is not a table: its rows are ${listed([...widths])} values long`,
      ambiguous: null,
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
      header: false,
      refusal:
        `expected ${table(rows, columns)}, or ${table(rows + 1, columns + 1)} with a header; ` +
        `got ${table(cells.length, width)}`,
      ambiguous: null,
    };
  }
  const values = header ? cells.slice(1).map((row) => row.slice(1)) : cells;
  const block = pastedComma(values.flat());
  if ("refusal" in block) {
    return { rows: null, header: false, refusal: block.refusal, ambiguous: null };
  }
  const meaning = block.meaning ?? chosen;
  const read: number[][] = [];
  for (const row of values) {
    const counts: number[] = [];
    for (const cell of row) {
      // An empty cell is no value, where a cell typed into and emptied is nothing typed yet.
      const value = cellRead(cell, reply, physical, meaning) ?? {
        refusal: notANumber(cell),
        ambiguous: false,
      };
      if ("refusal" in value) {
        return {
          rows: null,
          header: false,
          refusal: value.refusal,
          ambiguous: value.ambiguous ? cell : null,
        };
      }
      counts.push(value.raw);
    }
    read.push(counts);
  }
  return { rows: read, header, refusal: null, ambiguous: null };
}

/**
 * The one value a paste's text holds, where it holds one: a single cell, a trailing line break
 * aside - what a spreadsheet puts on the clipboard for one cell copied - or `null` for anything
 * more, a block, which replaces every value (`pasted`). One value pasted into a cell sets that
 * cell as if it were typed there, held with the cells typed before it (decision 15.2): read as a
 * table, it was refused as one of the wrong shape, and the cells typed went with it. The text is
 * the cell's as it was pasted, which the cell reads as it reads one typed - an empty one too,
 * which is a cell nothing is typed into.
 */
export function pastedValue(text: string): string | null {
  const cells = celled(text).flat();
  return cells.length === 1 ? cells.join("") : null;
}

/** The line under the grid saying what shape a paste wants - the only way the feature is
 * discoverable, and the hint that stops the commonest refusal before it happens - and that one
 * value pasted into a cell sets that cell (`pastedValue`, decision 15.2). */
export function pasteHint(reply: ValuesReply): string {
  const [rows, columns] = wanted(reply);
  return (
    `Paste ${table(rows, columns)} values from a spreadsheet to replace them all, ` +
    "or one value into a cell to set it."
  );
}

/** One raw count in physical or in raw, as a cell, a column or a row header shows it - a
 * breakpoint, whose axis's datatype the reply leaves out, read as a whole datatype's count is,
 * exactly (`physicalText`, `rawText`). */
function reading(raw: number, conversion: Conversion, physical: boolean, datatype = ""): string {
  return physical ? physicalText(raw, conversion, datatype) : rawText(raw, datatype);
}

/** The indices `0`, `1`, `2`, … up to (not including) `count`. */
function indices(count: number): string[] {
  return Array.from({ length: count }, (_, index) => String(index));
}

/** An axis as the reply carries it, beside the object laid against it. */
type GridAxis = ValuesReply["axes"][number];

/**
 * The labels of `count` columns, or rows, laid against `axis` - `count` the object's own shape
 * (15:M7): a breakpoint labels its own column and nothing more, so an axis stating fewer
 * breakpoints than the shape leaves the columns past its last one unlabelled, rather than drawing
 * the grid narrower than the object and leaving its values past them unreachable; and an axis
 * stating more labels no column past the shape. An axis stating none at all - a `size` with no
 * `init` - is laid out as no axis is, by the indices, rather than as a header of no columns.
 */
function laidAgainst(axis: GridAxis | undefined, count: number, physical: boolean): string[] {
  if (axis === undefined || axis.breakpoints.length === 0) return indices(count);
  return Array.from({ length: count }, (_, at) => {
    const raw = axis.breakpoints[at];
    return raw === undefined ? "" : reading(raw, axis.conversion, physical);
  });
}

/** The header above the columns, one for each column the object's shape has (`laidAgainst`): the
 * x axis's readings where it states them, else indices. */
export function columnHeader(reply: ValuesReply, physical: boolean): string[] {
  // A scalar has one column, which is its value; an object with no cell, none.
  if (reply.shape.length === 0) return reply.rows.length > 0 ? ["Value"] : [];
  return laidAgainst(columnAxis(reply), wanted(reply)[1], physical);
}

/** The label down the side of each row, one for each row the object's shape has: the object's own
 * `name (unit)` for a single row, which is what spec 5.2 draws beside its values, and a map's y
 * axis's readings where it states them, else indices (`laidAgainst`). */
export function rowHeader(reply: ValuesReply, physical: boolean): string[] {
  // A scalar's one row is the object itself, as a single row's is.
  if (reply.shape.length === 0) {
    return reply.rows.length > 0 ? [labelled(reply.name, reply.unit, physical)] : [];
  }
  if (reply.shape.length === 1) return [labelled(reply.name, reply.unit, physical)];
  return laidAgainst(axisOf(reply, "y_axis"), wanted(reply)[0], physical);
}

/** The value the file states at a cell, or `undefined` where it states none there: an object that
 * states nothing, whose zeros are the startup code's, or a row too short to reach the cell - a
 * cell its shape has and the file does not hold, which the grid draws hollow (15:M7). */
export function statedValue(reply: ValuesReply, row: number, column: number): number | undefined {
  return reply.stated === "none" ? undefined : reply.rows[row]?.[column];
}

/** What a cell is called: `elementLabel`'s phrase, and for a cell the file does not state
 * (`statedValue`), that it does not - the one sign, for a reader who cannot see it, that the
 * empty field is no value the file holds. */
export function cellName(reply: ValuesReply, row: number, column: number): string {
  const element = elementLabel(row, column, reply.shape);
  return statedValue(reply, row, column) === undefined ? `${element}, not stated` : element;
}

/** A cell of the values grid the reader has typed into: where it is, what was typed, and whether
 * it was typed in physical - the reading its text is read in, whichever the grid shows now - and,
 * where its comma could be a decimal point or a thousands separator, which the reader said it is.
 * The grid holds every cell typed into (`typedCells.ts`). */
export interface TypedCell {
  row: number;
  column: number;
  typed: string;
  physical: boolean;
  comma?: CommaMeaning | undefined;
}

/** What a comma that could be either means in `cell`, one of the cells typed into a grid: what the
 * reader said of this cell's, where they said - an answer given stands, whatever a cell typed
 * later shows (fix round 1, M1: `0,5` typed after made a `1,500` said to group thousands 1.5) -
 * else the reading `typed` shows, where it shows one (`typedComma`). */
export function commaOf(typed: readonly TypedCell[], cell: TypedCell): CommaMeaning | undefined {
  return cell.comma ?? typedComma(typed.map((held) => held.typed));
}

/** What one cell's field shows. A cell typed into shows what was typed, in the reading it was
 * typed in; in the other, the count its text comes to, read as the grid now reads - so that
 * turning the grid from physical to raw neither changes what a typed cell sets nor shows a
 * physical number among raw counts - or the text itself, where it comes to no count. Any other
 * cell shows its raw count, or what that count reads as in physical; one the file does not state
 * (`statedValue`) shows nothing, where it read 0 as though the file held it (15:M7). */
export function cellText(
  reply: ValuesReply,
  typed: readonly TypedCell[],
  row: number,
  column: number,
  physical: boolean,
): string {
  const held = typed.find((cell) => cell.row === row && cell.column === column);
  if (held === undefined) {
    const raw = statedValue(reply, row, column);
    return raw === undefined ? "" : reading(raw, reply.conversion, physical, reply.datatype);
  }
  if (held.physical === physical) return held.typed;
  const raw = typedRaw(held.typed, reply, held.physical, commaOf(typed, held));
  return raw === null ? held.typed : reading(raw, reply.conversion, physical, reply.datatype);
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
  const value = physical ? physicalReading(raw, reply) : rawText(raw, reply.datatype);
  return `Sets ${element} of ${reply.name} to ${value}`;
}

/** A raw count's physical reading, with the object's own unit where it has one. */
export function physicalReading(raw: number, reply: ValuesReply): string {
  const value = physicalText(raw, reply.conversion, reply.datatype);
  return reply.unit === "" ? value : `${value} ${reply.unit}`;
}

/** The sentence above a pasted table's preview, as `cellSentence` is a cell's: what is about to
 * happen, so that a reader who pasted physical values and sees raw counts in the hunks is told
 * the two are one change and not two - and, where the table's first row and column were taken for
 * a header (`header`, `Pasted.header`), that they are not written (decision 15.1): a block of the
 * size a header makes is read so whatever it holds, and a reader who meant something else learns
 * it here, before opening Show changes. */
export function pasteSentence(reply: ValuesReply, header: boolean): string {
  const replaces = `Replaces every value of ${reply.name}`;
  if (!header) return replaces;
  return `${replaces}; the first row and column pasted are taken for a header and not written`;
}
