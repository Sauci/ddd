import { describe, expect, test } from "vitest";
import {
  ambiguousComma,
  COMMA_BOTH_WAYS,
  commaChoices,
  countText,
  type Decimal,
  decimalOfDouble,
  decimalText,
  doubleOf,
  floatReading,
  jsonNumber,
  type Linear,
  MIXES,
  notANumber,
  notDecimal,
  pastedComma,
  physicalValue,
  rawCount,
  readNumber,
  significant,
  singleOf,
  spelledNumber,
  typedComma,
} from "./numbers";

/** What `text` reads as, spelled as a sentence spells it, or the sentence it is refused with. */
function read(text: string, meaning?: "decimal" | "grouping"): string {
  const reading = readNumber(text, meaning);
  return "decimal" in reading ? decimalText(reading.decimal) : reading.refusal;
}

describe("the one grammar every field reads a number by", () => {
  test.each([
    // An optional sign, digits with an optional fraction or a fraction alone, an optional
    // exponent, the white space around it no part of it.
    { text: "12", reads: "12" },
    { text: "-12", reads: "-12" },
    { text: "+12", reads: "12" },
    { text: " 12 ", reads: "12" },
    { text: "\t7.25\n", reads: "7.25" },
    { text: "007", reads: "7" },
    { text: "7.", reads: "7" },
    { text: ".5", reads: "0.5" },
    { text: "-.5", reads: "-0.5" },
    { text: "1.250", reads: "1.25" },
    { text: "1e3", reads: "1000" },
    { text: "1E3", reads: "1000" },
    { text: "1.5e-3", reads: "0.0015" },
    { text: "2.5e+2", reads: "250" },
    { text: "1e21", reads: "1e+21" },
    { text: "0", reads: "0" },
    { text: "-0", reads: "0" },
    { text: "0.000", reads: "0" },
    { text: "18446744073709551615", reads: "18446744073709551615" },
  ])("'$text' is $reads", ({ text, reads }) => {
    expect(read(text)).toBe(reads);
  });

  test.each([
    // Every spelling of a number in another notation, in the one sentence, whatever the field:
    // `Number` reads the first nine, and python's `float` the rest.
    "0x10",
    "0X1F",
    "-0x10",
    "0b101",
    "0B1",
    "0o17",
    "0O17",
    "0x8000000000000001",
    `0b1${"0".repeat(52)}1`,
    "Infinity",
    "-Infinity",
    "+Infinity",
    "infinity",
    "inf",
    "-inf",
    "NaN",
    "nan",
    "1_000",
    "1_000.5",
    "1e1_0",
    "0x_1f",
    "_1",
  ])("'%s' is refused as no number in decimal notation", (text) => {
    expect(readNumber(text)).toEqual({ refusal: notDecimal(text), ambiguous: false });
    expect(notDecimal(text)).toBe(`'${text}' is not a number in decimal notation`);
  });

  test.each([
    "",
    "  ",
    "abc",
    "7abc",
    "1 234",
    "1.2.3",
    "--1",
    "+-1",
    "1e",
    "1e+",
    ".",
    "e5",
    "0x",
    "_",
    "Inf1",
  ])("'%s' is no number at all", (text) => {
    expect(readNumber(text)).toEqual({ refusal: notANumber(text), ambiguous: false });
    expect(notANumber(text)).toBe(`'${text}' is not a number`);
  });

  test("the sentence quotes what was typed, white space and all", () => {
    expect(readNumber(" 0x10 ")).toEqual({
      refusal: "' 0x10 ' is not a number in decimal notation",
      ambiguous: false,
    });
  });

  test("a number is held as its digits, not as the double nearest them", () => {
    expect(readNumber("-1.250")).toEqual({
      decimal: { negative: true, digits: "125", exponent: -2 },
    });
    expect(readNumber("9007199254740993")).toEqual({
      decimal: { negative: false, digits: "9007199254740993", exponent: 0 },
    });
    expect(readNumber("1200")).toEqual({ decimal: { negative: false, digits: "12", exponent: 2 } });
  });
});

describe("one rule for a comma, typed or pasted", () => {
  test.each([
    // A comma is a decimal point where it cannot group thousands: after a first group of 0, or of
    // more than three digits, or before anything but exactly three digits.
    { text: "1,5", reads: "1.5" },
    { text: "1,25", reads: "1.25" },
    { text: "1,2345", reads: "1.2345" },
    { text: "0,125", reads: "0.125" },
    { text: "-0,125", reads: "-0.125" },
    { text: "00,125", reads: "0.125" },
    { text: "1234,567", reads: "1234.567" },
    { text: ",5", reads: "0.5" },
    { text: "1,50e3", reads: "1500" },
    // Commas group thousands where they cannot be the decimal point: two of them.
    { text: "1,234,567", reads: "1234567" },
    { text: "-12,345,678", reads: "-12345678" },
    // Text holding both: the decimal point is the one written last, and the other groups.
    { text: "1,234.5", reads: "1234.5" },
    { text: "1,234,567.25", reads: "1234567.25" },
    { text: "1.234,5", reads: "1234.5" },
    { text: "1.234.567,25", reads: "1234567.25" },
  ])("'$text' is $reads", ({ text, reads }) => {
    expect(read(text)).toBe(reads);
  });

  test.each([
    // Grouped any other way, it is no number.
    "1,23,456",
    "1,2345,678",
    "01,234,567",
    "1,23.4",
    "1.23,4",
    "0,125.5",
    "1,5,0",
    "1.234.5,6",
  ])("'%s' is grouped no way a number is", (text) => {
    expect(readNumber(text)).toEqual({ refusal: notANumber(text), ambiguous: false });
  });

  test.each(["1,200", "1,500", "-1,500", "+999,999", "1,500e3"])(
    "a comma before exactly three digits, after a group of one to three, could be either: '%s'",
    (text) => {
      expect(readNumber(text)).toEqual({ refusal: ambiguousComma(text), ambiguous: true });
      expect(ambiguousComma(text)).toBe(
        `the comma in '${text}' could be a decimal point or a thousands separator`,
      );
    },
  );

  test("a comma that could be either is read as it is said to be", () => {
    expect(read("1,500", "decimal")).toBe("1.5");
    expect(read("1,500", "grouping")).toBe("1500");
    expect(read("1,500e3", "decimal")).toBe("1500");
    expect(read("1,500e3", "grouping")).toBe("1500000");
  });

  test("and what is said answers only a comma that could be either", () => {
    // A comma the text itself decides is read as it decides, whatever is said.
    expect(read("1,5", "grouping")).toBe("1.5");
    expect(read("1,234,567", "decimal")).toBe("1234567");
    expect(read("1,234.5", "decimal")).toBe("1234.5");
  });
});

describe("pastedComma", () => {
  test("a block in which one value's comma can only be a decimal point reads every comma so", () => {
    // 15:M9: a leading 0 is no grouping, so a comma locale's block of three decimals is one.
    expect(pastedComma(["0,125", "0,250", "0,500"])).toEqual({ meaning: "decimal" });
    expect(pastedComma(["0,5", "1,250", "2"])).toEqual({ meaning: "decimal" });
    expect(pastedComma(["1.234,5", "1,500"])).toEqual({ meaning: "decimal" });
  });

  test("a block in which one value's commas can only group thousands reads every comma so", () => {
    // Fix round 1, M1: a comma that could be either reads as the others show theirs - `1,500`
    // beside `1,234,567` is fifteen hundred, where it was asked about.
    expect(pastedComma(["1,234,567", "1,500"])).toEqual({ meaning: "grouping" });
    expect(pastedComma(["1,234.5", "1,500", "2"])).toEqual({ meaning: "grouping" });
  });

  test("nothing in the block says it, so a comma that could be either stays undecided", () => {
    expect(pastedComma(["1,200", "2", "3"])).toEqual({ meaning: undefined });
    expect(pastedComma(["7.5", "1,500"])).toEqual({ meaning: undefined });
    expect(pastedComma(["12", "9"])).toEqual({ meaning: undefined });
  });

  test("a block writing its decimal point both ways is refused", () => {
    expect(pastedComma(["7.5", "6,5"])).toEqual({ refusal: MIXES });
    expect(pastedComma(["1,234.5", "0,5"])).toEqual({ refusal: MIXES });
    expect(pastedComma(["1.234,5", "7.5"])).toEqual({ refusal: MIXES });
    expect(MIXES).toBe(
      "this mixes '.' and ',' as decimal separators, so it is not clear what it means",
    );
  });

  test("a block writing its comma both ways is refused in words naming no point", () => {
    // M1: `1,234,567` groups thousands with its commas and `0,5` parts a fraction with its own;
    // the block was refused as mixing '.' and ',', and it holds no '.'.
    expect(pastedComma(["1,234,567", "0,5"])).toEqual({ refusal: COMMA_BOTH_WAYS });
    expect(pastedComma(["1.234,5", "1,234,567"])).toEqual({ refusal: COMMA_BOTH_WAYS });
    expect(COMMA_BOTH_WAYS).toBe(
      "this writes ',' both as a decimal separator and as a thousands separator, so it is not " +
        "clear what it means",
    );
  });

  test("a value that is no number says nothing of the block's separators", () => {
    expect(pastedComma(["7,5", "abc.d", "1,2,3"])).toEqual({ meaning: "decimal" });
    expect(pastedComma(["7.5", "1,23,4"])).toEqual({ meaning: undefined });
  });
});

describe("typedComma", () => {
  test("values typed together read a comma as a decimal point where one of them shows it", () => {
    expect(typedComma(["0,5", "1,250"])).toBe("decimal");
    expect(typedComma(["1,250"])).toBeUndefined();
    expect(typedComma(["7.5", "1,250"])).toBeUndefined();
    expect(typedComma([])).toBeUndefined();
  });

  test("and as thousands separators where one shows them to be, none showing both (M1)", () => {
    expect(typedComma(["1,234,567", "1,500"])).toBe("grouping");
    expect(typedComma(["1,234.5", "1,500"])).toBe("grouping");
    // Shown both ways, nothing decides: a cell that could be either is asked about.
    expect(typedComma(["0,5", "1,234,567", "1,500"])).toBeUndefined();
  });
});

describe("decimalText", () => {
  test.each([
    // As `String` spells the double of the same value, whatever the scale.
    1500, 1.5, 0.001, 0.000001, 1e-7, 1.25e-7, 123456789012345680000, 1e21, 1.5e21, -2.5, 0,
  ])("%d is spelled as String spells it", (value) => {
    const reading = readNumber(String(value));
    expect("decimal" in reading && decimalText(reading.decimal)).toBe(String(value));
  });
});

describe("doubleOf", () => {
  test("is the double nearest the digits", () => {
    const reading = (text: string) => {
      const read = readNumber(text);
      if (!("decimal" in read)) throw new Error(`${text} reads as no number`);
      return read.decimal;
    };
    expect(doubleOf(reading("-1.25"))).toBe(-1.25);
    expect(doubleOf(reading("0"))).toBe(0);
    expect(doubleOf(reading("9007199254740993"))).toBe(2 ** 53);
    expect(doubleOf(reading("1e400"))).toBe(Number.POSITIVE_INFINITY);
  });

  test("an exponent past every double is an infinity or a zero on its side, never NaN (M2)", () => {
    // The digits were spelled with their exponent, which from 1e21 on `String` writes `1e+21` -
    // and `Number` reads `1e1e+21` as NaN, which a cell then sent as a count.
    expect(doubleOf(decimal("1e1000000000000000000000"))).toBe(Number.POSITIVE_INFINITY);
    expect(doubleOf(decimal("-1e1000000000000000000000"))).toBe(Number.NEGATIVE_INFINITY);
    expect(doubleOf(decimal("1e-1000000000000000000000"))).toBe(0);
    expect(Object.is(doubleOf(decimal("-1e-1000000000000000000000")), -0)).toBe(true);
  });
});

describe("an exponent past 10^15", () => {
  test("is held at it, as far past every datatype and spelled as a number json reads (M2)", () => {
    // `decimalText` wrote 1e1000000000000000000000 as `1e+1e+21`, no number at all, which a
    // size sent as its json.
    expect(read("1e1000000000000000000000")).toBe("1e+1000000000000000");
    expect(read("-1e-1000000000000000000000")).toBe("-1e-1000000000000000");
    expect(read("2.5e99")).toBe("2.5e+99");
  });
});

describe("commaChoices", () => {
  test("each answer says the number the text then reads as", () => {
    expect(commaChoices("1,500")).toEqual([
      { meaning: "decimal", label: "A decimal point: 1.5" },
      { meaning: "grouping", label: "A thousands separator: 1500" },
    ]);
  });

  test("a text no meaning reads as a number is named as it stands", () => {
    expect(commaChoices("abc")).toEqual([
      { meaning: "decimal", label: "A decimal point: abc" },
      { meaning: "grouping", label: "A thousands separator: abc" },
    ]);
  });
});

describe("jsonNumber", () => {
  test.each([
    // As json spells a number, whole or fractional as it was written, in its own digits.
    { text: "2", json: "2" },
    { text: "2.0", json: "2.0" },
    { text: "7.", json: "7.0" },
    { text: ".5", json: "0.5" },
    { text: "-.5", json: "-0.5" },
    { text: "+5", json: "5" },
    { text: "007.50", json: "7.50" },
    { text: "0", json: "0" },
    { text: "00", json: "0" },
    { text: "1E+3", json: "1e+3" },
    { text: "1,5", json: "1.5" },
    { text: "1.234,5", json: "1234.5" },
  ])("'$text' is $json", ({ text, json }) => {
    expect(jsonNumber(text)).toEqual({ json });
    expect(JSON.parse(json)).toBe(Number(json));
  });

  test("a comma that could be either is read as it is said to be, and refused until it is", () => {
    expect(jsonNumber("1,500", "grouping")).toEqual({ json: "1500" });
    expect(jsonNumber("1,500")).toEqual({ refusal: ambiguousComma("1,500"), ambiguous: true });
    expect(jsonNumber("0x10")).toEqual({ refusal: notDecimal("0x10"), ambiguous: false });
  });
});

describe("spelledNumber", () => {
  test("a number is read as readNumber reads it, and spelled as jsonNumber spells it", () => {
    // What a range's bound is weighed by, and the text it is sent as (3:I1).
    expect(spelledNumber("+1E3")).toEqual({ decimal: decimal("1000"), json: "1e3" });
    expect(spelledNumber("1,500", "decimal")).toEqual({ decimal: decimal("1.5"), json: "1.500" });
    expect(spelledNumber("1,500")).toEqual({ refusal: ambiguousComma("1,500"), ambiguous: true });
    expect(spelledNumber("0x10")).toEqual({ refusal: notDecimal("0x10"), ambiguous: false });
  });
});

/** `text` read as a decimal, for a test that knows it is one. */
function decimal(text: string): Decimal {
  const read = readNumber(text);
  if (!("decimal" in read)) throw new Error(`${text} reads as no number`);
  return read.decimal;
}

/** A linear conversion of `factor` and `offset`, as the reply's doubles spell them. */
function linear(factor: number, offset = 0): Linear {
  return { factor: decimalOfDouble(factor), offset: decimalOfDouble(offset) };
}

describe("rawCount", () => {
  test.each([
    // 3:M4: an exact half to the even count, as `round_physical` rounds, either side of zero -
    // where `Math.round` made 2.5 3 and -2.5 -2.
    { physical: "2.5", raw: 2 },
    { physical: "3.5", raw: 4 },
    { physical: "-2.5", raw: -2 },
    { physical: "-3.5", raw: -4 },
    { physical: "2.4999999999999999999", raw: 2 },
    { physical: "2.5000000000000000001", raw: 3 },
  ])("$physical counts of the identity is $raw in a sint16", ({ physical, raw }) => {
    expect(rawCount(decimal(physical), null, "sint16")).toEqual({ raw });
  });

  test("a half is weighed on the decimals, not on the double the division makes", () => {
    // 0.25 at 0.1 a count is 2.5 exactly - 2, the even one - where 0.25 / 0.1 in doubles is not.
    expect(rawCount(decimal("0.25"), linear(0.1), "uint8")).toEqual({ raw: 2 });
    expect(rawCount(decimal("0.35"), linear(0.1), "uint8")).toEqual({ raw: 4 });
    expect(rawCount(decimal("10"), linear(0.5, -40), "uint8")).toEqual({ raw: 100 });
  });

  test("a whole count is weighed against 2^53, not the physical value typed", () => {
    // Task 1's n1: 1e16 at a factor of 1000 is 1e13 counts, which a sint64 holds; 10 at a
    // factor of 1e-15 is 1e16, which the page cannot hold every neighbour of.
    expect(rawCount(decimal("1e16"), linear(1000), "sint64")).toEqual({ raw: 1e13 });
    expect(rawCount(decimal("10"), linear(1e-15), "sint64")).toEqual({ past: 1 });
    expect(rawCount(decimal("-10"), linear(1e-15), "sint64")).toEqual({ past: -1 });
    expect(rawCount(decimal("9007199254740992"), null, "uint64")).toEqual({ raw: 2 ** 53 });
  });

  test("a negative factor turns the count over", () => {
    expect(rawCount(decimal("-0.3"), linear(-0.1), "float64")).toEqual({ raw: 3 });
    expect(rawCount(decimal("1"), linear(-0.5), "sint8")).toEqual({ raw: -2 });
    expect(rawCount(decimal("-0.7"), linear(0.1), "float32")).toEqual({ raw: -7 });
  });

  test("a boolean is not rounded, so what is no 0 and no 1 is the server's to refuse", () => {
    expect(rawCount(decimal("0.6"), null, "boolean")).toEqual({ raw: 0.6 });
    expect(rawCount(decimal("1"), linear(0.5), "boolean")).toEqual({ raw: 2 });
  });

  test("a boolean past 2^53 is past it, as a whole count is, and one rounding to zero is so (M2)", () => {
    // 1e400 was sent as Infinity, which the server refused in python's own word for it, `inf`;
    // 1e-400 was sent as 0, a false nobody typed.
    expect(rawCount(decimal("1e400"), null, "boolean")).toEqual({ past: 1 });
    expect(rawCount(decimal("-1e400"), null, "boolean")).toEqual({ past: -1 });
    expect(rawCount(decimal("1e20"), linear(2), "boolean")).toEqual({ past: 1 });
    expect(rawCount(decimal("1e-400"), null, "boolean")).toEqual({ zero: true });
    expect(rawCount(decimal("0"), null, "boolean")).toEqual({ raw: 0 });
    expect(rawCount(decimal("9007199254740992"), null, "boolean")).toEqual({
      raw: 9007199254740992,
    });
  });

  test.each([
    // 15:M5: the float its datatype stores nearest the exact count, as briefly as it reads back -
    // where the double arithmetic planned 2.9999999999999996 and 6.999999999999999.
    { physical: "0.3", factor: 0.1, datatype: "float32", raw: 3 },
    { physical: "0.7", factor: 0.1, datatype: "float32", raw: 7 },
    { physical: "0.3", factor: 0.1, datatype: "float64", raw: 3 },
    { physical: "1", factor: 0.3, datatype: "float64", raw: 3.3333333333333335 },
    { physical: "1", factor: 3, datatype: "float32", raw: 0.33333334 },
    { physical: "0.1", factor: 1, datatype: "float32", raw: 0.1 },
    { physical: "16777217", factor: 1, datatype: "float32", raw: 16777216 },
    { physical: "1.000000059604644775390625", factor: 1, datatype: "float32", raw: 1 },
    // FLT_MAX either side of zero, whatever it is typed as, is the float32's own double: its
    // briefest spelling, 3.4028235e38, is a double past it, which the server refuses as not
    // fitting into float32.
    { physical: "3.4028235e38", factor: 1, datatype: "float32", raw: 3.4028234663852886e38 },
    { physical: "-3.4028235e38", factor: 1, datatype: "float32", raw: -3.4028234663852886e38 },
    {
      physical: "3.4028234663852886e38",
      factor: 1,
      datatype: "float32",
      raw: 3.4028234663852886e38,
    },
    { physical: "1e-45", factor: 1, datatype: "float32", raw: 1e-45 },
    { physical: "5e-324", factor: 1, datatype: "float64", raw: 5e-324 },
    {
      physical: "1.7976931348623157e308",
      factor: 1,
      datatype: "float64",
      raw: 1.7976931348623157e308,
    },
    // Rounded up to the next power of two, and a float32 whose shortest spelling takes all nine
    // digits a float32 needs.
    { physical: "0.99999999999999999", factor: 1, datatype: "float64", raw: 1 },
    { physical: "1.00025465e-36", factor: 1, datatype: "float32", raw: 1.00025465e-36 },
  ])(
    "$physical at $factor a count is $raw in a $datatype",
    ({ physical, factor, datatype, raw }) => {
      expect(rawCount(decimal(physical), linear(factor), datatype)).toEqual({ raw });
    },
  );

  test("a float rounded up to the next power of two past the most its datatype holds is beyond it", () => {
    // Past FLT_MAX by more than half its last unit: the significand rounds up to 2^24, and the
    // power of two it is carried into is past the most a float32 has.
    expect(rawCount(decimal("3.4028236e38"), null, "float32")).toEqual({ beyond: true });
    expect(rawCount(decimal("3.4028235e38"), null, "float32")).toEqual({
      raw: 3.4028234663852886e38,
    });
    expect(rawCount(decimal("-3.4028236e38"), null, "float32")).toEqual({ beyond: true });
  });

  test("a float the datatype cannot hold is said to be beyond it, or to round to zero", () => {
    expect(rawCount(decimal("1e39"), null, "float32")).toEqual({ beyond: true });
    expect(rawCount(decimal("-1e309"), null, "float64")).toEqual({ beyond: true });
    expect(rawCount(decimal("1e-50"), null, "float32")).toEqual({ zero: true });
    expect(rawCount(decimal("1e-400"), null, "float64")).toEqual({ zero: true });
    expect(rawCount(decimal("0"), null, "float64")).toEqual({ raw: 0 });
    expect(rawCount(decimal("-40"), linear(0.5, -40), "float32")).toEqual({ raw: 0 });
  });

  test("an exponent too far to work out digit by digit is held as far out, on its side of zero", () => {
    // M2: a float rounds a tiny one to zero, which it is refused for - it was planned as 0, and one
    // whose exponent reached 1e21 in size was said to be past what the float holds.
    expect(rawCount(decimal("1e-2000"), null, "sint16")).toEqual({ raw: 0 });
    expect(rawCount(decimal("1e-2000"), null, "float64")).toEqual({ zero: true });
    expect(rawCount(decimal("-1e-1000000000000000000000"), null, "float32")).toEqual({
      zero: true,
    });
    expect(rawCount(decimal("1e-1000000000000000000000"), linear(0.5), "uint8")).toEqual({
      raw: 0,
    });
    expect(rawCount(decimal("1e999999"), null, "float64")).toEqual({ beyond: true });
    expect(rawCount(decimal("-1e999999"), null, "sint64")).toEqual({ past: -1 });
    expect(rawCount(decimal("1e1000000000000000000000"), linear(0.5), "uint8")).toEqual({
      past: 1,
    });
  });
});

describe("physicalValue", () => {
  test.each([
    // The count times the factor, plus the offset, exactly: no tail of the double arithmetic,
    // and none of its digits cut at twelve.
    { raw: 255, factor: 0.03, offset: 0, reads: "7.65" },
    { raw: 3, factor: 0.3, offset: 0, reads: "0.9" },
    { raw: 7, factor: 1.5, offset: 0, reads: "10.5" },
    { raw: 1234567890123, factor: 1, offset: 0, reads: "1234567890123" },
    { raw: 100, factor: 0.5, offset: -40, reads: "10" },
    { raw: -3, factor: 0.25, offset: 0.5, reads: "-0.25" },
    { raw: 80, factor: 0.5, offset: -40, reads: "0" },
  ])("$raw at $factor and $offset reads $reads", ({ raw, factor, offset, reads }) => {
    expect(decimalText(physicalValue(raw, linear(factor, offset)))).toBe(reads);
  });
});

describe("floatReading", () => {
  test.each([
    // The shortest decimal whose own count is the count again.
    { raw: 3, factor: 0.1, datatype: "float32", reads: "0.3" },
    { raw: 7, factor: 0.1, datatype: "float32", reads: "0.7" },
    { raw: 2.9999999999999996, factor: 0.1, datatype: "float64", reads: "0.29999999999999996" },
    { raw: 0.3333333333333333, factor: 1.5, datatype: "float64", reads: "0.5" },
    { raw: 1.23456789012345, factor: 1, datatype: "float64", reads: "1.23456789012345" },
    { raw: -0.1, factor: 3, datatype: "float64", reads: "-0.3" },
  ])("$raw at $factor in a $datatype reads $reads", ({ raw, factor, datatype, reads }) => {
    expect(decimalText(floatReading(raw, linear(factor), datatype))).toBe(reads);
  });

  test("of two decimals as short that both read back, the one nearer the exact value", () => {
    expect(decimalText(floatReading(1.2328999999999999, linear(3.3), "float64"))).toBe(
      "4.0685699999999997",
    );
  });

  test("a count no shorter decimal reads back as reads as its exact value", () => {
    expect(decimalText(floatReading(0, linear(1), "float32"))).toBe("0");
  });

  test("a float32 reads as the float32 its file's number rounds to (fix round 1, M4)", () => {
    // Float32 data written out by a script spells 0.1f at double precision, 0.10000000149011612:
    // at a factor of 0.5 it read 0.05000000074505806, which typed back planned that float32 again.
    expect(decimalText(floatReading(0.10000000149011612, linear(0.5), "float32"))).toBe("0.05");
    // A file stating more digits than a float32 holds reads as the float32 they round to.
    expect(decimalText(floatReading(0.123456789123, linear(1), "float32"))).toBe("0.12345679");
    // A float64 holds every digit of its double, and reads them all.
    expect(decimalText(floatReading(0.10000000149011612, linear(0.5), "float64"))).toBe(
      "0.05000000074505806",
    );
  });
});

describe("singleOf", () => {
  test.each([
    // The float32 a file's number rounds to, as briefly as it reads back (M4).
    { raw: 0.10000000149011612, single: 0.1 },
    { raw: 0.1, single: 0.1 },
    { raw: 0.123456789123, single: 0.12345679 },
    { raw: 3, single: 3 },
    { raw: 16777217, single: 16777216 },
    { raw: 1e-46, single: 0 },
    // FLT_MAX either side of zero is its own double: its briefest spelling, 3.4028235e38, is a
    // double past it, which typed back would be refused as not fitting into float32.
    { raw: 3.4028235e38, single: 3.4028234663852886e38 },
    { raw: -3.4028235e38, single: -3.4028234663852886e38 },
    { raw: 3.4028234663852886e38, single: 3.4028234663852886e38 },
    // Past what a float32 holds, the file's number as it stands.
    { raw: 1e39, single: 1e39 },
  ])("$raw is $single", ({ raw, single }) => {
    expect(singleOf(raw)).toBe(single);
  });
});

describe("significant", () => {
  test.each([
    // 3:M4: an exact half to the even digit, as python's `format` and `round_physical` take it,
    // where `toPrecision` takes it away from zero.
    { value: 1234567890.125, digits: 12, rounded: 1234567890.12 },
    { value: -1234567890.125, digits: 12, rounded: -1234567890.12 },
    { value: 1234567890.375, digits: 12, rounded: 1234567890.38 },
    { value: 2.5, digits: 1, rounded: 2 },
    { value: 3.5, digits: 1, rounded: 4 },
    // No half at all: correctly rounded, as both take it.
    { value: 1.2345678901234567, digits: 12, rounded: 1.23456789012 },
    { value: 0.1, digits: 12, rounded: 0.1 },
    { value: 7.6499999999999995, digits: 12, rounded: 7.65 },
    { value: 1200, digits: 12, rounded: 1200 },
    { value: 5e-324, digits: 12, rounded: 5e-324 },
    { value: 1e300, digits: 12, rounded: 1e300 },
  ])("$value to $digits digits is $rounded", ({ value, digits, rounded }) => {
    expect(significant(value, digits)).toBe(rounded);
  });

  test("infinities, NaN and zero pass through", () => {
    expect(significant(Number.POSITIVE_INFINITY, 12)).toBe(Number.POSITIVE_INFINITY);
    expect(significant(Number.NaN, 12)).toBeNaN();
    expect(significant(0, 12)).toBe(0);
  });
});

describe("countText", () => {
  test("a count past a thousand is grouped by commas, three digits to a group", () => {
    expect(countText(1166)).toBe("1,166");
    expect(countText(26218)).toBe("26,218");
    expect(countText(1000000)).toBe("1,000,000");
  });

  test("a count under a thousand is its digits alone", () => {
    expect(countText(0)).toBe("0");
    expect(countText(7)).toBe("7");
    expect(countText(999)).toBe("999");
  });
});

describe("decimalOfDouble", () => {
  test("is the shortest spelling String gives, and nothing for what is no finite number", () => {
    expect(decimalOfDouble(0.1)).toEqual({ negative: false, digits: "1", exponent: -1 });
    expect(decimalOfDouble(-1200)).toEqual({ negative: true, digits: "12", exponent: 2 });
    expect(decimalOfDouble(Number.POSITIVE_INFINITY)).toEqual({
      negative: false,
      digits: "",
      exponent: 0,
    });
  });
});
