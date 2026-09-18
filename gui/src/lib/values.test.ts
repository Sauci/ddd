import { expect, test } from "vitest";
import { asList, asText } from "./values";

test("text is text, anything else is undefined", () => {
  expect(asText("rpm")).toBe("rpm");
  expect(asText(7)).toBeUndefined();
});

test("a list is a list, anything else is empty", () => {
  expect(asList([1, 2])).toEqual([1, 2]);
  expect(asList({ 0: 1 })).toEqual([]);
});
