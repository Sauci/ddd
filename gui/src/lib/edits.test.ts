import { expect, test } from "vitest";
import { jsonText, setValue } from "./edits";

test("a string travels as its json text", () => {
  expect(jsonText('say "hi"')).toBe('"say \\"hi\\""');
});

test("setting one value is one change with one operation", () => {
  expect(setValue("/p/a.ddd.json", "abc", "component.name", '"A"')).toEqual({
    changes: [
      {
        file: "/p/a.ddd.json",
        fingerprint: "abc",
        operations: [{ op: "set", pointer: "component.name", raw: '"A"' }],
      },
    ],
  });
});
