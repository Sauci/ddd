import { describe, expect, test } from "vitest";
import { ApiError, ServerUnreachable } from "../api/client";
import { isStale, panelShows, type Refused, refusalShown } from "./refusals";

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

test("nothing held and no plan refused, nothing is shown", () => {
  expect(refusalShown(null, null, "rename")).toBeNull();
});

describe("a refusal because a file changed on disk, as the revision the server asked for lands", () => {
  // Refusing an Apply as stale, the server asks for the analysis that reads the file as it is, and
  // that analysis's revision reaches the page within milliseconds, before the refusal or after
  // it. Each revision asks the panel's plan again: the panel has none while it is asked for, then
  // that revision's own answer - here a refusal of its own, so that what is shown says which.
  const held: Refused<string> = { about: "rename", text: STALE };
  const plan8 = "'rpm' is the unit's own spelling";

  test("answered before the new revision, it is shown, still shown once that revision has come, and gone on the reader's next choice", () => {
    // At the revision it was refused at, whose plan the Apply was made from.
    expect(refusalShown(held, null, "rename")).toBe(STALE);
    // The new revision lands: its plan asked for, then answered.
    expect(refusalShown(held, null, "rename")).toBe(STALE);
    expect(refusalShown(held, plan8, "rename")).toBe(STALE);
    // The reader chooses again, and the panel holds no refusal: its plan's own answer is shown.
    expect(refusalShown(null, plan8, "rename")).toBe(plan8);
  });

  test("answered after the new revision, it is shown, still shown as that revision's plan comes, and gone on the reader's next choice", () => {
    // The new revision landed first: its plan asked for, nothing refused yet.
    expect(refusalShown(null, null, "rename")).toBeNull();
    // The refusal is answered, then the new revision's plan.
    expect(refusalShown(held, null, "rename")).toBe(STALE);
    expect(refusalShown(held, plan8, "rename")).toBe(STALE);
    // The reader chooses again.
    expect(refusalShown(null, plan8, "rename")).toBe(plan8);
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
