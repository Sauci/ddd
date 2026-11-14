/**
 * How the page reads a number, wherever one is typed or pasted: a grid's cells and a pasted block,
 * a range's two fields, a size and a dimension, a constant's value. One grammar, so that no field
 * takes a spelling another refuses, and one rule for a comma, which half the world writes as its
 * decimal point.
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

/** The sentence a pasted block writing its decimal point both ways is refused with. */
export const MIXES =
  "this mixes '.' and ',' as decimal separators, so it is not clear what it means";

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

/** The number a match of `DECIMAL` spells, exactly: its digits stripped of the zeros that say
 * nothing, and the power of ten they are scaled by. */
function decimalOf(match: RegExpExecArray): Decimal {
  const [, sign = "", whole = "", fraction = "", alone = "", power = "0"] = match;
  const after = fraction === "" ? alone : fraction;
  const lead = `${whole}${after}`.replace(/^0+/, "");
  const digits = lead.replace(/0+$/, "");
  if (digits === "") return { negative: false, digits: "", exponent: 0 };
  const exponent = Number(power) - after.length + (lead.length - digits.length);
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
  if ("refusal" in match) return match;
  const [, sign, whole = "", fraction, alone, power] = match;
  const point = fraction ?? alone;
  const json =
    `${sign === "-" ? "-" : ""}${whole.replace(/^0+(?=\d)/, "") || "0"}` +
    `${point === undefined ? "" : `.${point || "0"}`}${power === undefined ? "" : `e${power}`}`;
  return { json };
}

/** What the separators of one number show of themselves: a comma that can only be the decimal
 * point (`decimal`); a point that is the decimal point (`point`), commas grouping thousands before
 * it or not; commas that can only group thousands (`grouping`); one comma that could be either
 * (`ambiguous`); or nothing - no separator, or text that is no number however it is read. */
type Shown = "decimal" | "point" | "grouping" | "ambiguous" | "nothing";

function shown(text: string): Shown {
  const trimmed = text.trim();
  if (!trimmed.includes(",")) {
    return trimmed.includes(".") && DECIMAL.test(trimmed) ? "point" : "nothing";
  }
  if (EITHER.test(trimmed)) return "ambiguous";
  if (!DECIMAL.test(settled(trimmed))) return "nothing";
  if (trimmed.includes(".")) {
    return trimmed.lastIndexOf(",") > trimmed.lastIndexOf(".") ? "decimal" : "point";
  }
  return count(trimmed, ",") > 1 ? "grouping" : "decimal";
}

/** What the comma means in a block pasted from a spreadsheet, which writes every number of a block
 * with the same separators: a decimal point wherever one value shows it to be one - a comma that
 * cannot group thousands - and otherwise nothing said, a comma that could be either being refused
 * until it is said. A block in which one value's comma is a decimal point and another's point is,
 * or another's commas group thousands, writes its decimal point both ways, and nothing can tell
 * which value means what: refused. */
export function pastedComma(
  texts: readonly string[],
): { refusal: string } | { meaning: CommaMeaning | undefined } {
  const all = new Set(texts.map(shown));
  if (all.has("decimal") && (all.has("point") || all.has("grouping"))) return { refusal: MIXES };
  return { meaning: all.has("decimal") ? "decimal" : undefined };
}

/** What the comma means among values typed together - the cells typed into one grid, a range's two
 * fields: a decimal point where one of them shows it to be one. Each typed value is read as it is
 * written beside that, so none of them is refused for another's separators. */
export function typedComma(texts: readonly string[]): CommaMeaning | undefined {
  return texts.some((text) => shown(text) === "decimal") ? "decimal" : undefined;
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

/** The double nearest a decimal, as `Number` reads its digits. */
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
