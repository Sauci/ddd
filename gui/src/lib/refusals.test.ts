import { describe, expect, test } from "vitest";
import { ApiError, ServerUnreachable } from "../api/client";
import { isStale, panelShows, type Refused, refusalOfOffer, refusalShown } from "./refusals";

/** What a panel says when its Apply is refused because a file changed under its preview. */
const STALE =
  "A file changed on disk, so nothing was written. The page now shows the files as they are.";

test("an Apply refused for a file changed on disk is stale, and no other refusal is", () => {
  expect(isStale(new ApiError(409, "stale", "a.ddd.json changed on disk"))).toBe(true);
  expect(isStale(new ApiError(409, "invalid", "refused"))).toBe(false);
  expect(isStale(new ServerUnreachable(new Error("refused")))).toBe(false);
  expect(isStale(new Error("stale"))).toBe(false);
});

test("a refusal held of a write is shown beside it, over why its plan was refused", () => {
  const held: Refused<string> = { about: "rename", text: STALE };
  expect(refusalShown(held, "'rpm' is the unit's own spelling", "rename")).toBe(STALE);
  expect(refusalShown(held, null, "rename")).toBe(STALE);
});

test("a refusal held of another write is not shown beside this one, which shows its own plan's", () => {
  const held: Refused<string> = { about: "remove", text: "The change was refused: no" };
  expect(refusalShown(held, "'rpm' is the unit's own spelling", "rename")).toBe(
    "'rpm' is the unit's own spelling",
  );
  expect(refusalShown(held, null, "rename")).toBeNull();
});

test("a refusal of an offer is held while the offer is made, and goes with it", () => {
  expect(refusalOfOffer(STALE, true)).toBe(STALE);
  expect(refusalOfOffer(STALE, false)).toBeNull();
  expect(refusalOfOffer(null, true)).toBeNull();
  expect(refusalOfOffer(null, false)).toBeNull();
});

test("nothing held and no plan refused, nothing is shown", () => {
  expect(refusalShown(null, null, "rename")).toBeNull();
});

describe("a refusal held of a write, over each answer a new revision brings its plan", () => {
  // What these pin is the drawing alone: whatever the write's plan answers as a revision lands -
  // nothing while it is asked again, then that revision's own answer, here a refusal of its own -
  // the refusal the panel holds is what is shown, and once the panel holds none, the plan's answer
  // is. They are pure calls, so they cannot tell which reached the page first, the refusal or the
  // revision, nor fail on a screen that lets its refusal go when a revision lands: each screen sets
  // and clears its own, outside this gate. The journeys of a refusal because a file changed on
  // disk are what fail then - in keys, declarations, values, project-units, files, shared and
  // types `.spec.ts`, each waiting for a sign only the analysis the refusal asks for can draw
  // before it looks for the sentence again.
  const held: Refused<string> = { about: "rename", text: STALE };
  const plan8 = "'rpm' is the unit's own spelling";

  test("held, it is shown while the plan is asked again, and over the plan's own refusal once that comes", () => {
    expect(refusalShown(held, null, "rename")).toBe(STALE);
    expect(refusalShown(held, plan8, "rename")).toBe(STALE);
  });

  test("once the panel holds none, the plan's own answer is shown", () => {
    expect(refusalShown(null, plan8, "rename")).toBe(plan8);
    expect(refusalShown(null, null, "rename")).toBeNull();
  });
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
});
