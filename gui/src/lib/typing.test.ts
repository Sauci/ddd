import { describe, expect, test } from "vitest";
import { atOnce, gated, PLAN_DELAY_MS, planDelay, planShown, sameRequest } from "./typing";

describe("planDelay", () => {
  test("a debounced value's first plan is asked for at once, not only a panel's very first", () => {
    expect(planDelay(false)).toBe(0);
  });

  // Pinned by the literal, not by the constant: comparing against `PLAN_DELAY_MS` itself is true
  // whatever that constant is set to, and so catches nothing (review fix round 1, Important 4).
  test("every later plan waits exactly 250 ms - long enough to ask once typing pauses, short enough that the preview follows", () => {
    expect(PLAN_DELAY_MS).toBe(250);
    expect(planDelay(true)).toBe(250);
  });
});

describe("sameRequest", () => {
  test("two requests built the same way, down to the same key order, are the same request", () => {
    const asked = { action: "set", name: "RPM", key: "value", raw: "1" };
    const typed = { action: "set", name: "RPM", key: "value", raw: "1" };
    expect(sameRequest(asked, typed)).toBe(true);
    // Not the same object - a fresh literal each render - so this is `JSON.stringify` at work,
    // never reference equality.
    expect(asked).not.toBe(typed);
  });

  test("text the reader has since typed past is not the same request", () => {
    expect(
      sameRequest(
        { action: "set", name: "RPM", key: "value", raw: "1" },
        { action: "set", name: "RPM", key: "value", raw: "12" },
      ),
    ).toBe(false);
  });

  test("a different action, or a different request shape entirely, is never the same", () => {
    expect(sameRequest({ action: "remove", name: "RPM" }, { action: "add", name: "RPM" })).toBe(
      false,
    );
  });

  test("nothing asked for yet and nothing typed yet are the same nothing", () => {
    expect(sameRequest(null, null)).toBe(true);
  });

  test("asked for nothing, typed into since, is not the same - and the other way about", () => {
    expect(sameRequest(null, { action: "remove", name: "RPM" })).toBe(false);
    expect(sameRequest({ action: "remove", name: "RPM" }, null)).toBe(false);
  });
});

describe("atOnce", () => {
  test("a null value - nothing to ask for, or a gate closing - takes effect at once", () => {
    expect(atOnce(null, true)).toBe(true);
    expect(atOnce(null, false)).toBe(true);
  });

  test("a discrete commit takes effect at once, whatever it carries", () => {
    expect(atOnce({ action: "set", name: "RPM", key: "value", raw: "1" }, false)).toBe(true);
  });

  test("only text actually typed waits", () => {
    expect(atOnce({ action: "set", name: "RPM", key: "value", raw: "1" }, true)).toBe(false);
  });
});

describe("planShown", () => {
  const request = { action: "set", name: "RPM", key: "value", raw: "1" };
  const changed = { action: "set", name: "RPM", key: "value", raw: "12" };
  const plan = { revision: 7, changes: [{ file: "a.ddd.json" }] };
  const refused = { message: "units.ddd.json is there already" };

  test("the debounced request's own answer, settled and not a placeholder, is shown", () => {
    expect(
      planShown(request, request, { data: plan, error: null, isPlaceholderData: false }),
    ).toEqual({ plan, refusal: null, pending: false });
  });

  test("why the current request's own fetch was refused is shown, pending or not", () => {
    expect(
      planShown(request, request, { data: undefined, error: refused, isPlaceholderData: false }),
    ).toEqual({ plan: null, refusal: refused.message, pending: true });
  });

  test("still loading - no data and no refusal yet - is pending, with nothing to draw", () => {
    expect(
      planShown(request, request, { data: undefined, error: null, isPlaceholderData: false }),
    ).toEqual({ plan: null, refusal: null, pending: true });
  });

  test("a reply for text the reader has since typed past is never shown, whatever it answers - a refusal included", () => {
    expect(
      planShown(request, changed, { data: plan, error: refused, isPlaceholderData: false }),
    ).toEqual({ plan: null, refusal: null, pending: true });
  });

  test("a placeholder - an earlier request's answer, kept while this one loads - is never shown, even where it is the request the fields now say", () => {
    expect(
      planShown(request, request, { data: plan, error: null, isPlaceholderData: true }),
    ).toEqual({ plan: null, refusal: null, pending: true });
  });
});

// Ruling T12b-1: the gate after the debounce, never before it - the values grid's
// `appliesOver` closing as a revision lands and opening once an answer of it has come must not
// run the debounce again, with nothing typed: the cell typed before it is asked for at once.
describe("gated", () => {
  const typed = { at: [0, 1], raw: 1200 };

  test("closed, nothing is asked for, whatever was typed", () => {
    expect(gated(typed, typed, false)).toBeNull();
  });

  test("open, the debounced request is asked for at once, once it is what the fields say", () => {
    // A fresh object of the same content, as a screen builds its request every render.
    expect(gated(typed, { at: [0, 1], raw: 1200 }, true)).toBe(typed);
  });

  test("open while the fields have moved past the debounced request, nothing is asked for", () => {
    expect(gated(typed, { at: [0, 1], raw: 12000 }, true)).toBeNull();
  });

  test("nothing typed is nothing asked, open or not", () => {
    expect(gated(null, null, true)).toBeNull();
    expect(gated(null, null, false)).toBeNull();
  });
});
