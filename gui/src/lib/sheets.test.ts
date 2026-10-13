import { describe, expect, test } from "vitest";
import { sheetLoaded, sheetsToAskAgain } from "./sheets";

describe("sheetLoaded", () => {
  test("a link holding no sheet did not load", () => {
    expect(sheetLoaded(null)).toBe(false);
  });

  test("a sheet whose rules cannot be read did not load, as Chromium leaves one that failed", () => {
    const refused = {
      get cssRules(): unknown {
        throw new DOMException("Cannot access rules", "SecurityError");
      },
    };
    expect(sheetLoaded(refused)).toBe(false);
  });

  test("a sheet whose rules can be read loaded", () => {
    expect(sheetLoaded({ cssRules: [] })).toBe(true);
  });
});

describe("sheetsToAskAgain", () => {
  test("asks for nothing when every stylesheet loaded", () => {
    expect(sheetsToAskAgain([{ href: "/a.css", loaded: true }])).toEqual([]);
  });

  test("asks again for each stylesheet that failed, in the page's order", () => {
    expect(
      sheetsToAskAgain([
        { href: "/a.css", loaded: false },
        { href: "/b.css", loaded: true },
        { href: "/c.css", loaded: false },
      ]),
    ).toEqual(["/a.css", "/c.css"]);
  });

  test("asks once for an address two failed links name", () => {
    expect(
      sheetsToAskAgain([
        { href: "/a.css", loaded: false },
        { href: "/a.css", loaded: false },
      ]),
    ).toEqual(["/a.css"]);
  });
});
