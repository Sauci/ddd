import { describe, expect, test } from "vitest";
import { ApiError, ServerUnreachable } from "../api/client";
import {
  heldOf,
  isStale,
  offerShown,
  STALE as PAGE_STALE,
  type PanelShows,
  panelReads,
  panelShows,
  type Refused,
  refusalOf,
  refusalOfOffer,
  refusalSentence,
  refusalShown,
} from "./refusals";

/** What a panel says when its Apply is refused because a file changed under its preview. */
const STALE =
  "A file changed on disk, so nothing was written. The page now shows the files as they are.";

test("the page's own sentence for an Apply refused because a file changed on disk", () => {
  // Said by every panel but the variable panel and the Findings tab, which say what they show in
  // words of their own: the Units, Types and Shared files tabs' panels, the Files tab, the values
  // grid and the declare panel.
  expect(PAGE_STALE).toBe(STALE);
});

test("an Apply refused is said in the page's own sentence where a file changed on disk, else in the server's words", () => {
  expect(refusalOf(new ApiError(409, "stale", "a.ddd.json changed on disk"))).toBe(STALE);
  expect(refusalOf(new ApiError(409, "invalid", "'rpm' is no unit"))).toBe(
    "The change was refused: 'rpm' is no unit",
  );
  expect(refusalOf(new ServerUnreachable(new Error("refused")))).toBe(
    "The change was refused: ddd gui is not answering",
  );
});

test("an Apply refused for a file changed on disk is stale, and no other refusal is", () => {
  expect(isStale(new ApiError(409, "stale", "a.ddd.json changed on disk"))).toBe(true);
  expect(isStale(new ApiError(409, "invalid", "refused"))).toBe(false);
  expect(isStale(new ServerUnreachable(new Error("refused")))).toBe(false);
  expect(isStale(new Error("stale"))).toBe(false);
});

test("an Apply refused is said in the panel's own sentence where a file changed on disk", () => {
  // The panel's sentence says what it now shows; any other refusal is said in the server's words.
  expect(refusalSentence(new ApiError(409, "stale", "a.ddd.json changed on disk"), STALE)).toBe(
    STALE,
  );
  expect(refusalSentence(new ApiError(409, "invalid", "'rpm' is no unit"), STALE)).toBe(
    "The change was refused: 'rpm' is no unit",
  );
  expect(refusalSentence(new Error("there is nothing to change"), STALE)).toBe(
    "The change was refused: there is nothing to change",
  );
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

test("a panel of several writes holds the sentence of the write it was refused for, and of no other", () => {
  const held: Refused<string> = { about: "rename", text: STALE };
  expect(heldOf(held, "rename")).toBe(STALE);
  expect(heldOf(held, "remove")).toBeNull();
  expect(heldOf(null, "rename")).toBeNull();
});

describe("what a panel offers of one write beside the refusal it says", () => {
  /** A plan as `planShown` hands it over: the revision's answer for the write as it stands. */
  const PLAN = { changes: [{ file: "units.ddd.json" }] };
  const PLAN_REFUSED = "units.ddd.json changed since the project was analysed";

  test("nothing refused, the plan is offered", () => {
    expect(offerShown(null, { plan: PLAN, refusal: null, pending: false })).toEqual({
      plan: PLAN,
      refusal: null,
      pending: false,
    });
  });

  test("beside a refusal held of its Apply, the plan asked for again is offered under the sentence", () => {
    // The plan of the files as they now are, which a stale refusal's sentence says the panel shows:
    // one press away, never withdrawn until the reader chooses again.
    expect(offerShown(STALE, { plan: PLAN, refusal: null, pending: false })).toEqual({
      plan: PLAN,
      refusal: STALE,
      pending: false,
    });
  });

  test("beside its plan's own refusal, nothing is offered to apply, not even an answer kept from before", () => {
    // A plan asked for again and refused leaves the answer before it in the query's hands, its
    // fingerprints no longer the files': an Apply drawn from it would only be refused.
    expect(offerShown(null, { plan: PLAN, refusal: PLAN_REFUSED, pending: false })).toEqual({
      plan: null,
      refusal: PLAN_REFUSED,
      pending: false,
    });
  });

  test("a refusal held of its Apply is said over its plan's own, and nothing is offered while that stands", () => {
    expect(offerShown(STALE, { plan: PLAN, refusal: PLAN_REFUSED, pending: false })).toEqual({
      plan: null,
      refusal: STALE,
      pending: false,
    });
  });

  test("whether the plan may still change is the plan's own", () => {
    expect(offerShown(STALE, { plan: null, refusal: null, pending: true })).toEqual({
      plan: null,
      refusal: STALE,
      pending: true,
    });
  });
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

describe("what a panel shows once it reads the project's units beside its entity", () => {
  // The unit, type and variable panels read `GET /api/units` for what their choosers list.
  const RPM = { unit: "RPM", sites: 2 };
  const reply: PanelShows<typeof RPM> = { shown: "reply", reply: RPM };
  const UNITS = { units: [], vocabulary: null };
  const failed = new ApiError(500, "internal", "ddd gui failed on this request");

  test.each([
    { shown: "reading" } as const,
    { shown: "updating" } as const,
    { shown: "refusal", refusal: "'RPM' is not declared in the open project" } as const,
  ])("what it shows short of its entity's answer stands, whatever the units' read: %o", (shows) => {
    expect(panelReads(shows, { data: undefined, error: failed })).toEqual(shows);
    expect(panelReads(shows, { data: UNITS, error: null })).toEqual(shows);
  });

  test("its entity's answer and the units', it shows the answer", () => {
    expect(panelReads(reply, { data: UNITS, error: null })).toEqual(reply);
  });

  test("its entity's answer, the units on their way, it is reading", () => {
    expect(panelReads(reply, { data: undefined, error: null })).toEqual({ shown: "reading" });
  });

  test("its entity's answer, the units' read failed with nothing to draw from, it says so in its place", () => {
    // Where it once said it was reading, for good.
    expect(panelReads(reply, { data: undefined, error: failed })).toEqual({
      shown: "refusal",
      refusal: "ddd gui failed on this request",
    });
  });

  test("its entity's answer, the units' read failed over an answer the query still holds, it draws from that", () => {
    expect(panelReads(reply, { data: UNITS, error: failed })).toEqual(reply);
  });
});
