import { describe, expect, test } from "vitest";
import { ApiError, ServerUnreachable } from "../api/client";
import { isStale, panelShows, refusalShown, shownRefusal } from "./refusals";

test("a refusal shows until the revision it was refused at has passed", () => {
  const stored = { text: "A file changed on disk", revision: 7 };
  expect(shownRefusal(stored, 7)).toBe("A file changed on disk");
  expect(shownRefusal(stored, 8)).toBeNull();
});

test("nothing refused shows nothing, whatever the revision", () => {
  expect(shownRefusal(null, 7)).toBeNull();
});

test("a refusal from before the page knew a revision shows until one arrives", () => {
  expect(shownRefusal({ text: "refused", revision: undefined }, undefined)).toBe("refused");
  expect(shownRefusal({ text: "refused", revision: undefined }, 7)).toBeNull();
});

test("an Apply refused for a file changed on disk is stale, and no other refusal is", () => {
  expect(isStale(new ApiError(409, "stale", "a.ddd.json changed on disk"))).toBe(true);
  expect(isStale(new ApiError(409, "invalid", "refused"))).toBe(false);
  expect(isStale(new ServerUnreachable(new Error("refused")))).toBe(false);
  expect(isStale(new Error("stale"))).toBe(false);
});

test("a stale Apply's sentence is shown over any other while its revision stands", () => {
  const stale = { text: "A file changed on disk", revision: 7 };
  expect(refusalShown(stale, null, new Error("asked"), 7)).toBe("A file changed on disk");
  // Over another Apply's refusal too. `useFilesApply` never sets both - setting one clears the
  // other - but the order is the function's own, and this is where it is stated.
  expect(refusalShown(stale, "The change was refused: no", new Error("asked"), 7)).toBe(
    "A file changed on disk",
  );
});

test("once the analysis moves past a stale Apply, why the plan was refused shows again", () => {
  const stale = { text: "A file changed on disk", revision: 7 };
  expect(refusalShown(stale, null, new Error("refused when asked"), 8)).toBe("refused when asked");
});

test("an Apply refused for another reason is shown over why the plan was refused", () => {
  expect(refusalShown(null, "The change was refused: no", new Error("asked"), 7)).toBe(
    "The change was refused: no",
  );
});

test("a plan refused when asked is shown in the server's own words", () => {
  expect(refusalShown(null, null, new Error("units.ddd.json is there already"), 7)).toBe(
    "units.ddd.json is there already",
  );
});

test("nothing refused shows nothing", () => {
  expect(refusalShown(null, null, null, 7)).toBeNull();
});

describe("what a panel shows of the answer about its own entity", () => {
  // `GET /api/unit` and its kind answer from the index the last analysis made: an entity whose
  // file an edit changed since is refused until that edit's analysis lands, in these words.
  const CHANGED =
    "'RPM' is not declared in any file that has not changed since, and pump.ddd.json, " +
    "units.ddd.json changed since it was read";
  const unreadable = new ApiError(409, "unreadable", CHANGED);
  /** What the panel already showed of RPM, and of another unit a query may still hold. */
  const RPM = { unit: "RPM", sites: 2 };
  const RPM_LOWER = { unit: "rpm", sites: 2 };
  const about = (reply: { unit: string }) => reply.unit;

  test.each([true, false])("nothing come yet, it is reading (updating: %s)", (updating) => {
    expect(panelShows({ data: undefined, error: null }, about, "RPM", updating)).toEqual({
      shown: "reading",
    });
  });

  test.each([true, false])("its entity's answer, it shows (updating: %s)", (updating) => {
    expect(panelShows({ data: RPM, error: null }, about, "RPM", updating)).toEqual({
      shown: "reply",
      reply: RPM,
    });
  });

  test.each([true, false])(
    "another entity's answer, kept from a name before, it never shows (updating: %s)",
    (updating) => {
      expect(panelShows({ data: RPM_LOWER, error: null }, about, "RPM", updating)).toEqual({
        shown: "reading",
      });
    },
  );

  test("refused unreadable while updating, it keeps what it showed of its entity under the note", () => {
    expect(panelShows({ data: RPM, error: unreadable }, about, "RPM", true)).toEqual({
      shown: "reply",
      reply: RPM,
    });
  });

  test("refused unreadable while updating with nothing of its entity shown, the note stands alone", () => {
    // A unit renamed to RPM, or a constant just added: its panel had nothing to keep.
    expect(panelShows({ data: undefined, error: unreadable }, about, "RPM", true)).toEqual({
      shown: "updating",
    });
    // Nor does it show the name before's answer, which the query carries over to the new one.
    expect(panelShows({ data: RPM_LOWER, error: unreadable }, about, "RPM", true)).toEqual({
      shown: "updating",
    });
  });

  test.each([undefined, RPM])(
    "refused unreadable once nothing is updating, it shows the refusal whole (shown before: %o)",
    (data) => {
      expect(panelShows({ data, error: unreadable }, about, "RPM", false)).toEqual({
        shown: "refusal",
        refusal: CHANGED,
      });
    },
  );

  test.each([
    [new ApiError(404, "not-found", "'RPM' is not declared in the open project"), true],
    [new ApiError(404, "not-found", "'RPM' is not declared in the open project"), false],
    [new ApiError(400, "bad-request", "unit takes ?name="), true],
    [new ApiError(400, "bad-request", "unit takes ?name="), false],
    [new ApiError(409, "analysing", "the open project has not been analysed yet"), true],
    [new ApiError(409, "analysing", "the open project has not been analysed yet"), false],
    [new ApiError(500, "internal", "something went wrong"), true],
    [new ApiError(500, "internal", "something went wrong"), false],
    [new ServerUnreachable(new Error("refused")), true],
    [new ServerUnreachable(new Error("refused")), false],
  ])(
    "refused for any other reason, it shows the refusal, updating or not (%o, %s)",
    (error, updating) => {
      expect(panelShows({ data: RPM, error }, about, "RPM", updating)).toEqual({
        shown: "refusal",
        refusal: error.message,
      });
    },
  );

  test("the moment the analysis lands, the revision moved and the answer not come, no refusal shows", () => {
    // The query keyed by the new revision starts again with no error, carrying the last answer it
    // had while the next is asked for, or nothing.
    expect(panelShows({ data: RPM, error: null }, about, "RPM", false)).toEqual({
      shown: "reply",
      reply: RPM,
    });
    expect(panelShows({ data: undefined, error: null }, about, "RPM", false)).toEqual({
      shown: "reading",
    });
  });
});
