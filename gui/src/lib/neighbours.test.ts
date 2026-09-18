import { expect, test } from "vitest";
import type { GraphFlow } from "../api/types";
import { neighboursOf } from "./neighbours";

const flow = (from: string, to: string): GraphFlow => ({
  from,
  to,
  objects: ["Value"],
  severity: null,
  disagreements: [],
});

test("a module with no flows is its own only neighbour", () => {
  expect(neighboursOf("/a.ddd.json", [])).toEqual(new Set(["/a.ddd.json"]));
});

test("a producer keeps itself and everything it produces for", () => {
  const flows = [flow("/a.ddd.json", "/b.ddd.json"), flow("/a.ddd.json", "/c.ddd.json")];
  expect(neighboursOf("/a.ddd.json", flows)).toEqual(
    new Set(["/a.ddd.json", "/b.ddd.json", "/c.ddd.json"]),
  );
});

test("a consumer keeps itself and everything it reads from", () => {
  const flows = [flow("/a.ddd.json", "/c.ddd.json"), flow("/b.ddd.json", "/c.ddd.json")];
  expect(neighboursOf("/c.ddd.json", flows)).toEqual(
    new Set(["/a.ddd.json", "/b.ddd.json", "/c.ddd.json"]),
  );
});

test("a module in the middle of a chain keeps both sides, and not the module two steps away", () => {
  const flows = [
    flow("/a.ddd.json", "/b.ddd.json"),
    flow("/b.ddd.json", "/c.ddd.json"),
    flow("/c.ddd.json", "/d.ddd.json"),
  ];
  expect(neighboursOf("/b.ddd.json", flows)).toEqual(
    new Set(["/a.ddd.json", "/b.ddd.json", "/c.ddd.json"]),
  );
});
