import { describe, expect, test } from "vitest";
import {
  ambiguousComma,
  commaChoices,
  decimalText,
  doubleOf,
  jsonNumber,
  MIXES,
  notANumber,
  notDecimal,
  pastedComma,
  readNumber,
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

  test("nothing in the block says it, so a comma that could be either stays undecided", () => {
    expect(pastedComma(["1,200", "2", "3"])).toEqual({ meaning: undefined });
    expect(pastedComma(["7.5", "1,500"])).toEqual({ meaning: undefined });
    expect(pastedComma(["1,234,567", "1,500"])).toEqual({ meaning: undefined });
    expect(pastedComma(["12", "9"])).toEqual({ meaning: undefined });
  });

  test("a block writing its decimal point both ways is refused", () => {
    expect(pastedComma(["7.5", "6,5"])).toEqual({ refusal: MIXES });
    expect(pastedComma(["1,234.5", "0,5"])).toEqual({ refusal: MIXES });
    expect(pastedComma(["1.234,5", "7.5"])).toEqual({ refusal: MIXES });
    expect(pastedComma(["1,234,567", "0,5"])).toEqual({ refusal: MIXES });
    expect(MIXES).toBe(
      "this mixes '.' and ',' as decimal separators, so it is not clear what it means",
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
