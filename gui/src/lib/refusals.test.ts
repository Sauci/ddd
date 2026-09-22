import { expect, test } from "vitest";
import { shownRefusal } from "./refusals";

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
