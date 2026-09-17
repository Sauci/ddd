import { expect, test } from "vitest";
import type { Finding } from "../api/types";
import { keyedFindings } from "./findings";

const finding = (overrides: Partial<Finding> = {}): Finding => ({
  file: "/p/a.ddd.json",
  check: "definition-mismatch",
  severity: "error",
  message: "'ValueA' is declared differently",
  pointer: "component.interface[0].definition",
  notes: [],
  ...overrides,
});

// Destructuring keyedFindings' result by position would run into noUncheckedIndexedAccess
// (its length is not known statically), so tests read the keys through map() instead.
const keysOf = (findings: Finding[]): string[] => keyedFindings(findings).map(([, key]) => key);

test("distinct findings get distinct keys", () => {
  const a = finding({ pointer: "component.interface[0].definition" });
  const b = finding({ pointer: "component.interface[1].definition" });
  const keys = keysOf([a, b]);
  expect(keys[0]).not.toBe(keys[1]);
});

test("two findings equal in all four fields get different keys", () => {
  const keys = keysOf([finding(), finding()]);
  expect(keys[0]).not.toBe(keys[1]);
});

test("a finding keeps its key when a different finding before it in the list disappears", () => {
  const other = finding({ check: "unknown-unit", message: "a different problem" });
  const kept = finding({ pointer: "component.interface[2].definition" });
  const keyWithOther = keysOf([other, kept])[1];
  const keyWithoutOther = keysOf([kept])[0];
  expect(keyWithoutOther).toBe(keyWithOther);
});
