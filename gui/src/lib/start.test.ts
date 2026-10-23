import { expect, test } from "vitest";
import { listHeld } from "./start";

test("the list takes a press before any project was asked to open", () => {
  expect(listHeld("idle")).toBe(false);
});

test("the list is held while a project is opening, and once it is open, until the page leaves it", () => {
  expect(listHeld("pending")).toBe(true);
  // Answered, the session not yet: the page is still the start page, and a press would open
  // another project over the one just opened.
  expect(listHeld("success")).toBe(true);
});

test("an open the server refused gives the list back", () => {
  expect(listHeld("error")).toBe(false);
});
