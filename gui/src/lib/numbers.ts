/**
 * How the page reads a number, wherever one is typed or pasted: a grid's cells and a pasted block,
 * a range's two fields, a size and a dimension, a constant's value, a section's alignment and a
 * raster's event. One grammar, so that no field takes a spelling another refuses, and one rule for
 * a comma, which half the world writes as its decimal point.
 *
 * The grammar is decimal notation: an optional sign, digits with an optional fraction or a fraction
 * alone, and an optional exponent, the white space around it ignored. Each field once took what
 * `Number` takes, and `Number` reads hexadecimal, binary and octal spellings, and `Infinity`:
 * `0x10` planned 16, `0b101` 5, `0o17` 15, and `Infinity` was refused in python's word for it,
 * `inf`. Those spellings, `NaN` and underscores are refused here, in one sentence, before anything
 * is asked of the server.
 */

/** A number read exactly as it is written: its sign, its significant digits - no leading zero and
 * no trailing one, none at all for zero - and the power of ten they are scaled by. `-1.250` is
 * `{ negative: true, digits: "125", exponent: -2 }`. Held as digits rather than as the double
 * nearest them, so that what was typed is what is weighed. */
export interface Decimal {
  negative: boolean;
  digits: string;
  exponent: number;
}

/** What a comma is taken for where the text alone cannot say: a decimal point, or the separator
 * between groups of three digits. */
export type CommaMeaning = "decimal" | "grouping";

/** A text read as a number, or the sentence it is refused with - `ambiguous` where the refusal is
 * a comma that could be either, which a choice of what it means answers. */
export type NumberRead = { decimal: Decimal } | { refusal: string; ambiguous: boolean };

/** Decimal notation: a sign, digits with an optional fraction or a fraction alone, an exponent -
 * the groups the sign, the whole digits, the fraction after them, the fraction alone and the
 * power. */
const DECIMAL = /^([+-]?)(?:(\d+)(?:\.(\d*))?|\.(\d+))(?:[eE]([+-]?\d+))?$/;

/** The spellings of a number in another notation, refused rather than read: hexadecimal, binary
 * and octal, which `Number` reads; infinity and not-a-number in every spelling `Number` or python's
 * `float` reads; and digits parted by underscores, which python reads. */
const OTHER_NOTATION =
  /^[+-]?(?:0[xbo][\da-z_]+|inf(?:inity)?|nan|(?=[^_]*_)(?=\D*\d)[\d_.,]*(?:e[+-]?[\d_]*)?)$/i;

/** One comma that could group thousands as readily as part a fraction: a first group of one to
 * three digits that does not start with 0, then exactly three digits ending the number's digits.
 * `1,200` is twelve hundred from a spreadsheet that groups thousands, and one and a fifth from one
 * that writes decimals with a comma. */
const EITHER = /^[+-]?[1-9]\d{0,2},\d{3}(?:[eE][+-]?\d+)?$/;

/** Thousands grouped by commas, with the decimal point after them if there is one: `1,234,567`,
 * `1,234.5`. */
const GROUPED_BY_COMMAS = /^[+-]?[1-9]\d{0,2}(?:,\d{3})+(?:\.\d*)?(?:[eE][+-]?\d+)?$/;

/** Thousands grouped by points, then the comma that is the decimal point: `1.234,5`. */
const GROUPED_BY_POINTS = /^[+-]?[1-9]\d{0,2}(?:\.\d{3})+,\d*(?:[eE][+-]?\d+)?$/;

/** The sentence a number in another notation is refused with, the same in every field. */
export function notDecimal(text: string): string {
  return `'${text}' is not a number in decimal notation`;
}

/** The sentence a text that is no number at all is refused with. */
export function notANumber(text: string): string {
  return `'${text}' is not a number`;
}

/** The sentence a comma that could be a decimal point or a thousands separator is refused with,
 * until it is said which. */
export function ambiguousComma(text: string): string {
  return `the comma in '${text}' could be a decimal point or a thousands separator`;
}

/** The sentence a pasted block writing its decimal point both ways is refused with: a comma that
 * can only be the decimal point beside a point that is one. */
export const MIXES =
  "this mixes '.' and ',' as decimal separators, so it is not clear what it means";

/** The sentence a pasted block writing its comma both ways is refused with: a comma that can only
 * be the decimal point beside commas that can only group thousands - naming no point, which such a
 * block need not hold (fix round 1, M1: `1,234,567` beside `0,5` was said to mix '.' and ','). */
export const COMMA_BOTH_WAYS =
  "this writes ',' both as a decimal separator and as a thousands separator, so it is not " +
  "clear what it means";

/** How many times `character` stands in `text`. */
function count(text: string, character: string): number {
  return text.split(character).length - 1;
}

/**
 * `text` - trimmed, holding a comma that could not be either (`EITHER`) - in the grammar's own
 * spelling, its commas read by what they can be. A comma is the decimal point where it cannot group
 * thousands: after a first group of 0 or of more than three digits, or before anything but exactly
 * three digits. Commas group thousands where they cannot be the decimal point: two of them, or a
 * point after them. Text holding both a point and a comma has its decimal point last: the comma,
 * the points before it grouping thousands (`1.234,5` is 1234.5), or the point, the commas before it
 * grouping them (`1,234.5` is 1234.5). Text grouped any other way is left as it is, for the
 * grammar to refuse.
 */
function settled(text: string): string {
  if (text.includes(".")) {
    if (text.lastIndexOf(",") > text.lastIndexOf(".")) {
      return GROUPED_BY_POINTS.test(text) ? text.replaceAll(".", "").replace(",", ".") : text;
    }
    return GROUPED_BY_COMMAS.test(text) ? text.replaceAll(",", "") : text;
  }
  if (count(text, ",") > 1) return GROUPED_BY_COMMAS.test(text) ? text.replaceAll(",", "") : text;
  return text.replace(",", ".");
}

/** The farthest from 0 an exponent is held, either way: far past every number a double or any
 * datatype holds, and a whole number the arithmetic on a decimal's exponent keeps exact (fix
 * round 1, M2). Read as written, `1e1000000000000000000000` had an exponent `String` spells
 * `1e+21`, which made the digits no number at all once spelled back. */
const EXPONENT_HELD = 1e15;

/** The number a match of `DECIMAL` spells, exactly: its digits stripped of the zeros that say
 * nothing, and the power of ten they are scaled by - held within `EXPONENT_HELD`. */
function decimalOf(match: RegExpExecArray): Decimal {
  const [, sign = "", whole = "", fraction = "", alone = "", power = "0"] = match;
  const after = fraction === "" ? alone : fraction;
  const lead = `${whole}${after}`.replace(/^0+/, "");
  const digits = lead.replace(/0+$/, "");
  if (digits === "") return { negative: false, digits: "", exponent: 0 };
  const held = Math.min(EXPONENT_HELD, Math.max(-EXPONENT_HELD, Number(power)));
  const exponent = held - after.length + (lead.length - digits.length);
  return { negative: sign === "-", digits, exponent };
}

/** `text` matched by the grammar, its commas read (`settled`), or the sentence it is refused
 * with. */
function matched(
  text: string,
  meaning: CommaMeaning | undefined,
): RegExpExecArray | { refusal: string; ambiguous: boolean } {
  const trimmed = text.trim();
  if (OTHER_NOTATION.test(trimmed)) return { refusal: notDecimal(text), ambiguous: false };
  let spelled = trimmed;
  if (EITHER.test(trimmed)) {
    if (meaning === undefined) return { refusal: ambiguousComma(text), ambiguous: true };
    spelled = trimmed.replace(",", meaning === "decimal" ? "." : "");
  } else if (trimmed.includes(",")) {
    spelled = settled(trimmed);
  }
  return DECIMAL.exec(spelled) ?? { refusal: notANumber(text), ambiguous: false };
}

/**
 * `text` read as a number, or why it is not one. White space around it is no part of it. A comma is
 * read by what it can be (`settled`); one that could be a decimal point or a thousands separator
 * alike is read as `meaning` says, and is refused, `ambiguous`, where nothing says it - the same
 * sentence in every field, which a grid offers to answer with one press.
 *
 * Refused in other words: a number in another notation (`notDecimal`), and text that is no number
 * at all (`notANumber`), the empty text among it.
 */
export function readNumber(text: string, meaning?: CommaMeaning): NumberRead {
  const match = matched(text, meaning);
  return "refusal" in match ? match : { decimal: decimalOf(match) };
}

/** `text` read as `readNumber` reads it, spelled as json spells a number: whole where it was
 * written whole, and with its point or its exponent where it was written with one, its digits as
 * they were typed - `2.0` stays `2.0` and `2` stays `2`, `.5` travels as `0.5`, `+5` as `5` and
 * `1,5` as `1.5`. What a field whose spelling says what a number is sends, a constant's value. */
export function jsonNumber(
  text: string,
  meaning?: CommaMeaning,
): { json: string } | { refusal: string; ambiguous: boolean } {
  const match = matched(text, meaning);
  return "refusal" in match ? match : { json: jsonOf(match) };
}

/** `text` read as `readNumber` reads it, and spelled as `jsonNumber` spells it: what a field that
 * weighs a number and then sends it as typed reads - a range's two bounds. */
export function spelledNumber(
  text: string,
  meaning?: CommaMeaning,
): { decimal: Decimal; json: string } | { refusal: string; ambiguous: boolean } {
  const match = matched(text, meaning);
  return "refusal" in match ? match : { decimal: decimalOf(match), json: jsonOf(match) };
}

/** A match of `DECIMAL` as json spells it (`jsonNumber`). */
function jsonOf(match: RegExpExecArray): string {
  const [, sign, whole = "", fraction, alone, power] = match;
  const point = fraction ?? alone;
  return (
    `${sign === "-" ? "-" : ""}${whole.replace(/^0+(?=\d)/, "") || "0"}` +
    `${point === undefined ? "" : `.${point || "0"}`}${power === undefined ? "" : `e${power}`}`
  );
}

/** What the separators of one number show of themselves: a comma that can only be the decimal
 * point (`decimal`: `0,5`, `1234,567`, `1.234,5`); commas that can only group thousands, with no
 * point (`grouping`: `1,234,567`) or before the point that is the decimal point (`grouped`:
 * `1,234.5`); a point that is the decimal point, and no comma (`point`); one comma that could be
 * either (`ambiguous`); or nothing - no separator, or text that is no number however it is read. */
type Shown = "decimal" | "grouping" | "grouped" | "point" | "ambiguous" | "nothing";

function shown(text: string): Shown {
  const trimmed = text.trim();
  if (!trimmed.includes(",")) {
    return trimmed.includes(".") && DECIMAL.test(trimmed) ? "point" : "nothing";
  }
  if (EITHER.test(trimmed)) return "ambiguous";
  if (!DECIMAL.test(settled(trimmed))) return "nothing";
  if (trimmed.includes(".")) {
    return trimmed.lastIndexOf(",") > trimmed.lastIndexOf(".") ? "decimal" : "grouped";
  }
  return count(trimmed, ",") > 1 ? "grouping" : "decimal";
}

/** Which readings of a comma the values `all` show: a decimal point, where one's comma can only be
 * one, and thousands separators, where one's commas can only group them. */
function readings(all: ReadonlySet<Shown>): { decimal: boolean; grouping: boolean } {
  return { decimal: all.has("decimal"), grouping: all.has("grouping") || all.has("grouped") };
}

/**
 * What the comma means in a block pasted from a spreadsheet, which writes every number of a block
 * with the same separators: the reading the block's values show where they all show one - a
 * decimal point wherever one value's comma cannot group thousands, thousands separators wherever
 * one value's commas cannot be a decimal point (fix round 1, M1: `1,500` beside `1,234,567` is
 * fifteen hundred, and nothing is asked) - and otherwise nothing said, a comma that could be either
 * being refused until it is said. A block showing both writes its comma both ways
 * (`COMMA_BOTH_WAYS`), and one whose decimal comma stands beside a point that is the decimal point
 * writes its decimal point both ways (`MIXES`): nothing can tell which value means what, refused.
 */
export function pastedComma(
  texts: readonly string[],
): { refusal: string } | { meaning: CommaMeaning | undefined } {
  const all = new Set(texts.map(shown));
  const { decimal, grouping } = readings(all);
  if (decimal && (all.has("point") || all.has("grouped"))) return { refusal: MIXES };
  if (decimal && grouping) return { refusal: COMMA_BOTH_WAYS };
  return { meaning: decimal ? "decimal" : grouping ? "grouping" : undefined };
}

/** What the comma means among values typed together - the cells typed into one grid, a range's two
 * fields: the reading they show where they all show one, as a pasted block's (`pastedComma`), and
 * nothing where they show both or none. Each typed value is read as it is written beside that, so
 * none of them is refused for another's separators. */
export function typedComma(texts: readonly string[]): CommaMeaning | undefined {
  const { decimal, grouping } = readings(new Set(texts.map(shown)));
  if (decimal === grouping) return undefined;
  return decimal ? "decimal" : "grouping";
}

/** A decimal as a sentence spells it: the way `String` spells the double of the same value, so
 * that a number read and a number held read alike - `1500`, `1.5`, `1e+21`. */
export function decimalText(decimal: Decimal): string {
  const { negative, digits, exponent } = decimal;
  if (digits === "") return "0";
  const sign = negative ? "-" : "";
  // Where the decimal point falls, counted from the first digit: ECMAScript's own rule for when a
  // number is written out and when it takes an exponent (Number::toString).
  const point = digits.length + exponent;
  if (exponent >= 0 && point <= 21) return `${sign}${digits}${"0".repeat(exponent)}`;
  if (point > 0 && point <= 21) return `${sign}${digits.slice(0, point)}.${digits.slice(point)}`;
  if (point > -6 && point <= 0) return `${sign}0.${"0".repeat(-point)}${digits}`;
  const rest = digits.length > 1 ? `.${digits.slice(1)}` : "";
  const power = point - 1;
  return `${sign}${digits[0]}${rest}e${power < 0 ? "-" : "+"}${Math.abs(power)}`;
}

/** The double nearest a decimal, as `Number` reads its digits - an infinity, or a zero, on its own
 * side for one past every double. Its exponent is spelled in digits, which `decimalOf` holds it to
 * (`EXPONENT_HELD`): spelled `1e+21` from 1e21 on, it made the digits NaN, which a cell then sent
 * as a count (fix round 1, M2). */
export function doubleOf(decimal: Decimal): number {
  const { negative, digits, exponent } = decimal;
  return digits === "" ? 0 : Number(`${negative ? "-" : ""}${digits}e${exponent}`);
}

/** What one choice of a comma's meaning offers: the meaning, and what the button taking it says. */
export interface CommaChoice {
  meaning: CommaMeaning;
  label: string;
}

/** The two answers to a comma that could be either, in `text`: each saying the number `text` then
 * reads as, so that the press says what it does - `A decimal point: 1.5`, `A thousands separator:
 * 1500`. A text that reads as no number by a meaning is named as it stands. */
export function commaChoices(text: string): CommaChoice[] {
  const readAs = (meaning: CommaMeaning) => {
    const read = readNumber(text, meaning);
    return "decimal" in read ? decimalText(read.decimal) : text;
  };
  return [
    { meaning: "decimal", label: `A decimal point: ${readAs("decimal")}` },
    { meaning: "grouping", label: `A thousands separator: ${readAs("grouping")}` },
  ];
}

/** A decimal as the double `value` is spelled by `String`, its shortest spelling that reads back
 * as it: a raw count, a factor, an offset as the reply carries them. */
export function decimalOfDouble(value: number): Decimal {
  const read = readNumber(String(value));
  return "decimal" in read ? read.decimal : { negative: false, digits: "", exponent: 0 };
}

/** A rational number held exactly: a numerator over a positive denominator. */
interface Ratio {
  num: bigint;
  den: bigint;
}

/** Ten to `power`, a whole number of at least zero. */
function tenTo(power: number): bigint {
  return 10n ** BigInt(power);
}

/** A decimal as the ratio it is exactly. */
function ratioOf(decimal: Decimal): Ratio {
  const whole =
    BigInt(decimal.digits === "" ? "0" : decimal.digits) * (decimal.negative ? -1n : 1n);
  return decimal.exponent >= 0
    ? { num: whole * tenTo(decimal.exponent), den: 1n }
    : { num: whole, den: tenTo(-decimal.exponent) };
}

function minus(a: Ratio, b: Ratio): Ratio {
  return { num: a.num * b.den - b.num * a.den, den: a.den * b.den };
}

/** `a` over `b`, `b` not zero. */
function over(a: Ratio, b: Ratio): Ratio {
  const sign = b.num < 0n ? -1n : 1n;
  return { num: a.num * b.den * sign, den: a.den * b.num * sign };
}

/** The whole number nearest `ratio`, an exact half rounded to the even one - as python rounds, and
 * as `round_physical` (`models/conversion.py`) rounds the digit it keeps: 2.5 is 2, 3.5 is 4, and
 * -2.5 is -2, either side of zero alike. */
function halfEven(ratio: Ratio): bigint {
  const { num, den } = ratio;
  const floor = num >= 0n ? num / den : -((-num + den - 1n) / den);
  const twice = 2n * (num - floor * den);
  if (twice < den) return floor;
  if (twice > den) return floor + 1n;
  return floor % 2n === 0n ? floor : floor + 1n;
}

/** How many binary digits a positive whole number takes. */
function bits(whole: bigint): number {
  return whole.toString(2).length;
}

/** A binary floating point format: the digits its significand holds, and the least and the most
 * power of two a significand of those digits is scaled by. */
interface Format {
  digits: number;
  least: number;
  most: number;
}

/** A double, IEEE 754's binary64. */
const DOUBLE: Format = { digits: 53, least: -1074, most: 971 };

/** A float, binary32, which a `float32` stores. */
const SINGLE: Format = { digits: 24, least: -149, most: 104 };

/** The number of `format` nearest `ratio`, an exact half rounded to the even significand - the
 * rounding a compiler and `Number` make of a literal - as the double holding it: zero below the
 * least the format holds, and an infinity past the most. Computed on whole numbers alone, so that
 * no rounding of the arithmetic's own comes before the one rounding there is. */
function nearestIn(ratio: Ratio, format: Format): number {
  if (ratio.num === 0n) return 0;
  const negative = ratio.num < 0n;
  const num = negative ? -ratio.num : ratio.num;
  const den = ratio.den;
  // The power of two that leaves the significand `format.digits` long: estimated from the lengths,
  // then corrected by one where the estimate falls a digit short.
  let power = bits(num) - bits(den) - format.digits;
  const scaled = (at: number) => (at >= 0 ? [num, den << BigInt(at)] : [num << BigInt(-at), den]);
  let [top, bottom] = scaled(power) as [bigint, bigint];
  if (top / bottom >= 1n << BigInt(format.digits)) {
    power += 1;
    [top, bottom] = scaled(power) as [bigint, bigint];
  }
  if (power < format.least) {
    power = format.least;
    [top, bottom] = scaled(power) as [bigint, bigint];
  }
  let significand = halfEven({ num: top, den: bottom });
  if (significand === 1n << BigInt(format.digits)) {
    significand >>= 1n;
    power += 1;
  }
  if (power > format.most) return negative ? Number.NEGATIVE_INFINITY : Number.POSITIVE_INFINITY;
  const value = Number(significand) * 2 ** power;
  return negative ? -value : value;
}

/** FLT_MAX, the most a float holds, as the double it is: the widest significand at the most power
 * of two, which `String` spells 3.4028234663852886e+38. */
const SINGLE_MOST = (2 ** SINGLE.digits - 1) * 2 ** SINGLE.most;

/** The shortest spelling of a float - a `float32`'s, as a double - that a compiler reads back as
 * it: the double the digits are, so that `String` spells them - 0.1 for the float nearest 0.1,
 * rather than the 0.10000000149011612 of its exact value. But never a double past FLT_MAX's own:
 * FLT_MAX's shortest spelling, 3.4028235e38, is one, which the server's range for a `float32`
 * refuses, and `ddd check` with it, so ±FLT_MAX is spelled as its own double. */
function shortestSingle(value: number): number {
  for (let digits = 1; digits < 9; digits += 1) {
    const spelled = Number(value.toPrecision(digits));
    if (Math.fround(spelled) === value) return Math.abs(spelled) > SINGLE_MOST ? value : spelled;
  }
  return Number(value.toPrecision(9));
}

/**
 * The float32 a file's number `raw` rounds to, spelled as briefly as it reads back
 * (`shortestSingle`): what a `float32` holds of it, however many digits the file spells - float32
 * data a script writes out at double precision, `0.10000000149011612`, is 0.1 (fix round 1, M4).
 * A number past what a float32 holds is left as the file states it.
 */
export function singleOf(raw: number): number {
  const single = Math.fround(raw);
  if (!Number.isFinite(single)) return raw;
  return single === 0 ? 0 : shortestSingle(single);
}

/** The number a float datatype stores nearest the exact value of `ratio`, spelled as briefly as
 * the datatype reads it back: a double for `float64`, and for `float32` the shortest spelling of
 * the float (`shortestSingle`). */
function nearestFloat(ratio: Ratio, datatype: string): number {
  if (datatype !== "float32") return nearestIn(ratio, DOUBLE);
  const single = nearestIn(ratio, SINGLE);
  return Number.isFinite(single) && single !== 0 ? shortestSingle(single) : single;
}

/** A linear conversion's factor and offset, as the decimals the reply's doubles spell. */
export interface Linear {
  factor: Decimal;
  offset: Decimal;
}

/** What the raw count of a physical value comes to: the double holding it, or why there is none
 * the page can send - a whole raw count past ±2^53 (`past`), or a float beyond what the datatype
 * holds (`beyond`) or rounding to zero in it (`zero`). */
export type RawCount = { raw: number } | { past: -1 | 1 } | { beyond: true } | { zero: true };

/** 2^53, where a double stops holding every whole number. */
const WHOLE_LIMIT = 2n ** 53n;

/** The decimal `value` is, or one as far out on its side of zero and as few digits to work with,
 * where its exponent is so far from 0 that its exact digits would cost more than any datatype can
 * tell apart: a typed `1e2000` - an infinity to a double - is 1e1100, past every datatype, and
 * `1e-2000` is 1e-1100, which a float rounds to zero and is refused for, and a whole count rounds
 * to 0 (fix round 1, M2: it was held by its double, a zero planned for a float, and from an
 * exponent of 1e21 NaN, said to be past 2^53). */
function bounded(value: Decimal): Decimal {
  const magnitude = value.digits.length + value.exponent;
  if (Math.abs(magnitude) <= 1100) return value;
  return { negative: value.negative, digits: "1", exponent: magnitude > 0 ? 1100 : -1100 };
}

/**
 * The raw count a physical value comes to under `linear` - the identity where it is `null` - for
 * `datatype`, worked out exactly on the decimals, the one rounding there is made once, at the end:
 *
 * - a whole datatype's is the whole number nearest it, an exact half to the even one as
 *   `round_physical` rounds (3:M4: `Math.round` made 2.5 3 and -2.5 -2); weighed against ±2^53
 *   itself, where a double stops holding every whole number - not the physical value typed, which
 *   past it may come to a count well inside (task 1's n1: 1e16 at a factor of 1000 is 1e13);
 * - a boolean's is not rounded: it holds 0 and 1 alone, and anything else is the server's to
 *   refuse in the words it refuses it in raw - but past ±2^53 it is past it, as a whole count is,
 *   and one the double rounds to zero is said to (fix round 1, M2: 1e400 was sent as Infinity,
 *   which the server refused as python's `inf`, and 1e-400 as a false nobody typed);
 * - a float's is the float its datatype stores nearest, spelled as briefly as it reads back
 *   (15:M5): 0.3 at a factor of 0.1 is 3, where the double arithmetic made it 2.9999999999999996.
 */
export function rawCount(physical: Decimal, linear: Linear | null, datatype: string): RawCount {
  const value = ratioOf(bounded(physical));
  const exact =
    linear === null ? value : over(minus(value, ratioOf(linear.offset)), ratioOf(linear.factor));
  if (datatype.startsWith("float")) {
    const raw = nearestFloat(exact, datatype);
    if (!Number.isFinite(raw)) return { beyond: true };
    return raw === 0 && exact.num !== 0n ? { zero: true } : { raw };
  }
  if (datatype === "boolean") {
    const past = exact.num > WHOLE_LIMIT * exact.den || exact.num < -WHOLE_LIMIT * exact.den;
    if (past) return { past: exact.num < 0n ? -1 : 1 };
    const raw = nearestIn(exact, DOUBLE);
    return raw === 0 && exact.num !== 0n ? { zero: true } : { raw };
  }
  const whole = halfEven(exact);
  if (whole > WHOLE_LIMIT) return { past: 1 };
  if (whole < -WHOLE_LIMIT) return { past: -1 };
  return { raw: Number(whole) };
}

/** A decimal's digits as the whole number they spell, zero for none. */
function wholeOf(decimal: Decimal): bigint {
  return BigInt(decimal.digits || "0");
}

/** `a` times `b`, exactly. */
function product(a: Decimal, b: Decimal): Decimal {
  return normal(wholeOf(a) * wholeOf(b), a.negative !== b.negative, a.exponent + b.exponent);
}

/** `a` plus `b`, exactly. */
function sum(a: Decimal, b: Decimal): Decimal {
  const exponent = Math.min(a.exponent, b.exponent);
  const signed = (d: Decimal) =>
    wholeOf(d) * tenTo(d.exponent - exponent) * (d.negative ? -1n : 1n);
  const total = signed(a) + signed(b);
  return normal(total < 0n ? -total : total, total < 0n, exponent);
}

/** A whole number of digits, its sign and its power of ten, as a decimal: no trailing zero. */
function normal(whole: bigint, negative: boolean, exponent: number): Decimal {
  if (whole === 0n) return { negative: false, digits: "", exponent: 0 };
  const text = whole.toString();
  const digits = text.replace(/0+$/, "");
  return { negative, digits, exponent: exponent + (text.length - digits.length) };
}

/** The physical value of a raw count under `linear`, exactly: the count times the factor, plus the
 * offset, in decimal digits - no tail of the double arithmetic, and none of its digits cut off. */
export function physicalValue(raw: number, linear: Linear): Decimal {
  return sum(product(decimalOfDouble(raw), linear.factor), linear.offset);
}

/** The two decimals of `digits` significant digits either side of `value`, the nearer first. */
function around(value: Decimal, digits: number): Decimal[] {
  const kept = value.digits.slice(0, digits);
  const exponent = value.exponent + value.digits.length - digits;
  const lower = normal(BigInt(kept), value.negative, exponent);
  const upper = normal(BigInt(kept) + 1n, value.negative, exponent);
  return value.digits[digits] !== undefined && value.digits[digits] >= "5"
    ? [upper, lower]
    : [lower, upper];
}

/** Whether two raw counts of `datatype` are the one value it holds: for a `float32` the one
 * float32, however many digits each spells (fix round 1, M4), and for any other datatype the one
 * double. */
export function sameCount(a: number, b: number, datatype: string): boolean {
  return datatype === "float32" ? Math.fround(a) === Math.fround(b) : a === b;
}

/**
 * How the physical value of the raw count `raw` of a float datatype reads: the shortest decimal
 * whose own raw count (`rawCount`) is `raw`'s value again (`sameCount`) - so that what the grid
 * shows, typed back, sets nothing - never cut short and never with the tail of the double
 * arithmetic. A `float32` reads as the float32 its file's number rounds to: float32 data spelled
 * at double precision, `0.10000000149011612`, reads 0.05 at a factor of 0.5, where it read
 * 0.05000000074505806 (fix round 1, M4). Where no shorter decimal reads back, the exact value.
 */
export function floatReading(raw: number, linear: Linear, datatype: string): Decimal {
  const exact = physicalValue(raw, linear);
  for (let digits = 1; digits < exact.digits.length; digits += 1) {
    for (const candidate of around(exact, digits)) {
      const back = rawCount(candidate, linear, datatype);
      if ("raw" in back && sameCount(back.raw, raw, datatype)) return candidate;
    }
  }
  return exact;
}

/** The exact value of the double `value`, as a decimal: its significand times its power of two,
 * every digit of it - `0.1` is 0.1000000000000000055511151231257827021181583404541015625. */
function exactDecimalOf(value: number): Decimal {
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, value);
  const pattern = view.getBigUint64(0);
  const biased = Number((pattern >> 52n) & 0x7ffn);
  const fraction = pattern & ((1n << 52n) - 1n);
  const significand = biased === 0 ? fraction : fraction | (1n << 52n);
  const power = (biased === 0 ? 1 : biased) - 1075;
  // A negative power of two is that power of five over the same power of ten.
  return power >= 0
    ? normal(significand << BigInt(power), value < 0, 0)
    : normal(significand * 5n ** BigInt(-power), value < 0, power);
}

/** `value` to `digits` significant digits as python's `format` takes them - correctly rounded from
 * the double's exact value, an exact half to the even digit - where `toPrecision` takes an exact
 * half away from zero: 1234567890.125 is 1234567890.12 to twelve, as `round_physical` makes it,
 * and not 1234567890.13 (3:M4). Infinities, NaN and zero pass through. */
export function significant(value: number, digits: number): number {
  if (!Number.isFinite(value) || value === 0) return value;
  const exact = exactDecimalOf(value);
  if (exact.digits.length <= digits) return value;
  const kept = BigInt(exact.digits.slice(0, digits));
  const rest = exact.digits.slice(digits);
  // `rest` ends in no zero, so it is an exact half only as the one digit 5.
  const up = rest > "5" || (rest === "5" && kept % 2n === 1n);
  return doubleOf(normal(up ? kept + 1n : kept, exact.negative, exact.exponent + rest.length));
}
