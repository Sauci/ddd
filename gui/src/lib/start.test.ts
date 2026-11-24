import { expect, test } from "vitest";
import {
  ALREADY_OPEN,
  isOpen,
  listHeld,
  noProjectSentence,
  UNREAD_HEADING,
  unreadLine,
  unreadShown,
} from "./start";

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

test("a description that could not be read is listed as its path, a colon and the reason", () => {
  const entry = { path: "/work/b/broken.ddd.json", reason: "does not parse: Expecting value" };
  expect(unreadLine(entry)).toBe("/work/b/broken.ddd.json: does not parse: Expecting value");
});

test("the list of them is headed as the reader reads it", () => {
  expect(UNREAD_HEADING).toBe("Project descriptions that could not be read");
});

test("the list is drawn where the walk met a description it could not read, and not otherwise", () => {
  expect(unreadShown([])).toBe(false);
  expect(unreadShown([{ path: "/work/broken.ddd.json", reason: "is not UTF-8 text" }])).toBe(true);
});

test("a start page with no project says no description was found where the walk met none", () => {
  expect(noProjectSentence(0)).toBe(
    "No project description was found here. Start ddd gui with the path of one.",
  );
});

test("a start page with no project says none could be read where the walk met some it could not", () => {
  expect(noProjectSentence(1)).toBe(
    "No project description found here could be read. Each is listed below with why.",
  );
  expect(noProjectSentence(3)).toBe(noProjectSentence(1));
});

test("the project the page has open is the one the list marks, and pressed, is gone to", () => {
  // Opened again, it was analysed anew and its undo list emptied, nothing said.
  expect(isOpen("/work/demo/demo.ddd.json", "/work/demo/demo.ddd.json")).toBe(true);
  expect(ALREADY_OPEN).toBe("Already open");
});

test("every other project the list offers is opened, and none is while none is open", () => {
  expect(isOpen("/work/demo/subsystems/logging/logging.ddd.json", "/work/demo/demo.ddd.json")).toBe(
    false,
  );
  expect(isOpen("/work/demo/demo.ddd.json", null)).toBe(false);
});
