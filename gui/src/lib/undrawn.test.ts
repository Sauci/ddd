import { expect, test } from "vitest";
import { undrawnSentence } from "./undrawn";

test("an error is said by its message, after the line that the page could not be drawn", () => {
  expect(
    undrawnSentence(new TypeError("Cannot read properties of undefined (reading 'kind')")),
  ).toBe("This page could not be drawn: Cannot read properties of undefined (reading 'kind')");
});

test("an error with no message is said by its name", () => {
  expect(undrawnSentence(new RangeError())).toBe("This page could not be drawn: RangeError");
});

test("anything else thrown is said as String writes it", () => {
  expect(undrawnSentence("the reply has no findings")).toBe(
    "This page could not be drawn: the reply has no findings",
  );
  expect(undrawnSentence(undefined)).toBe("This page could not be drawn: undefined");
});
