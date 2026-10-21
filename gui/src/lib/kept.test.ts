import { describe, expect, test } from "vitest";
import { ApiError, ServerUnreachable } from "../api/client";
import { type Kept, kept, refusedRead, shown } from "./kept";

const units: Kept<string[]> = { identity: "units", data: ["ms"] };
const failed = new ApiError(500, "internal", "ddd gui failed on this request");
const refused = new ApiError(404, "not-found", "the project declares no 'CurveA'");

describe("refusedRead", () => {
  test("a refusal is the server's answer about what was asked", () => {
    expect(refusedRead(refused)).toBe(true);
    expect(refusedRead(new ApiError(409, "invalid", "x"))).toBe(true);
  });

  test("a read the server failed on, or that got no answer, is no refusal", () => {
    expect(refusedRead(failed)).toBe(false);
    expect(refusedRead(new ServerUnreachable(new TypeError("fetch failed")))).toBe(false);
    expect(refusedRead(null)).toBe(false);
  });
});

describe("kept", () => {
  test("keeps nothing new while the query holds no answer", () => {
    expect(kept(undefined, false, "units", null)).toBeNull();
    expect(kept(undefined, false, "units", units)).toBe(units);
  });

  test("keeps nothing new from a placeholder carried from the revision before", () => {
    expect(kept(["Hz"], true, "units", units)).toBe(units);
  });

  test("keeps the query's own answer, under its question", () => {
    expect(kept(["Hz"], false, "units", null)).toEqual({ identity: "units", data: ["Hz"] });
    expect(kept(["Hz"], false, "types", units)).toEqual({ identity: "types", data: ["Hz"] });
    // The very answer it kept, now asked under another question: kept anew, under that one.
    expect(kept(units.data, false, "types", units)).toEqual({
      identity: "types",
      data: units.data,
    });
  });

  test("answers the very object it kept while nothing changed", () => {
    expect(kept(units.data, false, "units", units)).toBe(units);
  });
});

describe("shown", () => {
  test("shows the query's answer whenever it has one", () => {
    expect(shown(["Hz"], "units", units, null)).toEqual(["Hz"]);
    expect(shown(["Hz"], "types", units, refused)).toEqual(["Hz"]);
  });

  test("shows the answer kept for the same question once a read failed", () => {
    expect(shown(undefined, "units", units, failed)).toEqual(["ms"]);
    expect(shown(undefined, "units", units, null)).toEqual(["ms"]);
  });

  test("never shows a kept answer over a refusal: the refusal is about what was asked", () => {
    expect(shown(undefined, "units", units, refused)).toBeUndefined();
  });

  test("never shows another question's answer", () => {
    expect(shown(undefined, "types", units, failed)).toBeUndefined();
  });

  test("shows nothing where nothing was ever answered", () => {
    expect(shown(undefined, "units", null, failed)).toBeUndefined();
  });
});
