import { expect, test } from "vitest";
import { ApiError, ServerUnreachable } from "../api/client";
import { isStale, refusalShown, shownRefusal } from "./refusals";

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
