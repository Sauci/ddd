import { expect, test } from "vitest";
import { listHeld, UNREAD_HEADING, unreadLine } from "./start";

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

test("a description that could not be read is named by its path and the server's reason", () => {
  expect(
    unreadLine({ path: "/work/b/broken.ddd.json", reason: "does not parse: Expecting value" }),
  ).toBe("/work/b/broken.ddd.json: does not parse: Expecting value");
});

test("the list of them says what it lists", () => {
  expect(UNREAD_HEADING).toBe("Project descriptions that could not be read");
});
