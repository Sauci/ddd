import { describe, expect, test } from "vitest";
import { PLAN_DELAY_MS, planDelay, sameRequest } from "./typing";

describe("planDelay", () => {
  test("a panel's first plan is asked for at once", () => {
    expect(planDelay(false)).toBe(0);
  });

  test("every later plan waits PLAN_DELAY_MS, long enough to ask once typing pauses", () => {
    expect(planDelay(true)).toBe(PLAN_DELAY_MS);
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
