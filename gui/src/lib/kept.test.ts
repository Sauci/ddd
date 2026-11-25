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
    expect(kept(undefined, false, "units", null, null)).toBeNull();
    expect(kept(undefined, false, "units", units, null)).toBe(units);
  });

  test("keeps nothing new from a placeholder carried from the revision before", () => {
    expect(kept(["Hz"], true, "units", units, null)).toBe(units);
  });

  test("keeps the query's own answer, under its question", () => {
    expect(kept(["Hz"], false, "units", null, null)).toEqual({ identity: "units", data: ["Hz"] });
    expect(kept(["Hz"], false, "types", units, null)).toEqual({ identity: "types", data: ["Hz"] });
    // The very answer it kept, now asked under another question: kept anew, under that one.
    expect(kept(units.data, false, "types", units, null)).toEqual({
      identity: "types",
      data: units.data,
    });
  });

  test("answers the very object it kept while nothing changed", () => {
    expect(kept(units.data, false, "units", units, null)).toBe(units);
  });

  test("keeps what it had through a read that failed, which is no refusal", () => {
    expect(kept(undefined, false, "units", units, failed)).toBe(units);
  });

  test("drops what it kept once a read of the question is refused, its query's own answer too", () => {
    // A refusal says the question has no answer: kept for it, nothing at all.
    expect(kept(undefined, false, "units", units, refused)).toEqual({
      identity: "units",
      data: undefined,
    });
    // React Query keeps a key's answer when a read of that same key again is refused.
    expect(kept(["Hz"], false, "units", units, refused)).toEqual({
      identity: "units",
      data: undefined,
    });
    expect(kept(undefined, false, "units", null, refused)).toEqual({
      identity: "units",
      data: undefined,
    });
  });

  test("answers the very object it gave a refusal while the refusal stands, and while a placeholder stands for the next", () => {
    const dropped = kept(undefined, false, "units", units, refused);
    expect(kept(undefined, false, "units", dropped, refused)).toBe(dropped);
    expect(kept(["ms"], true, "units", dropped, null)).toBe(dropped);
  });

  test("keeps the next answer that comes after a refusal", () => {
    const dropped = kept(undefined, false, "units", units, refused);
    expect(kept(["Hz"], false, "units", dropped, null)).toEqual({
      identity: "units",
      data: ["Hz"],
    });
  });
});

describe("shown", () => {
  /** What `kept` holds once a read of the units was refused. */
  const dropped: Kept<string[]> = { identity: "units", data: undefined };

  test("shows the query's answer whenever it has one and its read was not refused", () => {
    expect(shown(["Hz"], false, "units", units, null)).toEqual(["Hz"]);
  });

  test("shows the answer kept for the same question once a read failed", () => {
    expect(shown(undefined, false, "units", units, failed)).toEqual(["ms"]);
    expect(shown(undefined, false, "units", units, null)).toEqual(["ms"]);
  });

  test("shows a placeholder carried from the revision before while the next is asked", () => {
    expect(shown(["ms"], true, "units", units, null)).toEqual(["ms"]);
  });

  test("never shows an answer over a refusal, its query's own included: the refusal is about what was asked", () => {
    expect(shown(undefined, false, "units", units, refused)).toBeUndefined();
    // React Query keeps a key's answer when a read of that same key again is refused.
    expect(shown(["Hz"], false, "types", units, refused)).toBeUndefined();
  });

  test("never shows the answer from before a refusal once the next read fails, nor while it is asked", () => {
    // A refusal on one revision, then a server failure on the next (P19c-15): what was kept from
    // before the refusal is gone, and so is the placeholder React Query carries from it - the last
    // answer it had - while the next read is on its way.
    expect(shown(undefined, false, "units", dropped, failed)).toBeUndefined();
    expect(shown(["ms"], true, "units", dropped, null)).toBeUndefined();
    expect(shown(undefined, false, "units", dropped, null)).toBeUndefined();
  });

  test("shows the next answer that comes after a refusal", () => {
    expect(shown(["Hz"], false, "units", dropped, null)).toEqual(["Hz"]);
  });

  test("never shows another question's answer", () => {
    expect(shown(undefined, false, "types", units, failed)).toBeUndefined();
  });

  test("shows nothing where nothing was ever answered", () => {
    expect(shown(undefined, false, "units", null, failed)).toBeUndefined();
  });
});
