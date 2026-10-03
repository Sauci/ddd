import { describe, expect, test } from "vitest";
import type { ListedFinding } from "../api/types";
import { findingsByRow } from "./findingsByRow";
import { pointerOf, within } from "./pointer";

/** A finding at `pointer`, distinguishable from another by `tag` alone - every other field is
 * fixed, since `findingsByRow` groups by `pointer` and nothing else. */
function finding(pointer: string, tag: string): ListedFinding {
  return {
    file: "/p/components/c.ddd.json",
    check: "a-check",
    severity: "warning",
    message: `finding ${tag}`,
    pointer,
    notes: [],
    route: null,
    key: `key-${tag}`,
  };
}

/** The brute-force answer `findingsByRow` must match for one row: every finding `within` it,
 * worst first (the order `findings` is given in, here and there alike). */
function bruteForceRow(row: string, findings: readonly ListedFinding[]): ListedFinding[] {
  return findings.filter((entry) => within(entry.pointer, row));
}

describe("a file's findings, grouped by the row each is within", () => {
  test("a finding on the row itself", () => {
    const at = pointerOf(["component", "interface", 0]);
    const own = finding(at, "own");
    const byRow = findingsByRow([at], [own]);
    expect(byRow.get(at)).toEqual([own]);
  });

  test("one finding under an index, another under a key, both under the same row", () => {
    const at = pointerOf(["component", "interface", 0]);
    const underIndex = finding(`${at}[2]`, "index");
    const underKey = finding(`${at}.unit`, "key");
    const byRow = findingsByRow([at], [underIndex, underKey]);
    expect(byRow.get(at)).toEqual([underIndex, underKey]);
  });

  test("a near-miss prefix does not match: [1] is not a prefix of [12]", () => {
    const row = pointerOf(["component", "interface", 1]);
    const nearMiss = finding(pointerOf(["component", "interface", 12]), "near-miss");
    const byRow = findingsByRow([row], [nearMiss]);
    expect(byRow.get(row) ?? []).toEqual([]);
  });

  test("a near-miss prefix on a key does not match either: unit is not a prefix of units", () => {
    // Unlike [1] against [12] - whose own closing `]` already tells the two apart character for
    // character, whatever matches on - a bare `startsWith` of the row's text, with no delimiter
    // check at all, would wrongly accept this one: "…unit" really is a literal prefix of
    // "…units". A sibling key, not a nested one, so it must not match.
    const at = pointerOf(["component", "interface", 0]);
    const row = `${at}.unit`;
    const sibling = finding(`${at}.units`, "sibling-key");
    const byRow = findingsByRow([row], [sibling]);
    expect(byRow.get(row) ?? []).toEqual([]);
  });

  test("none: every row still answers empty rather than being left out of the map", () => {
    const rows = [
      pointerOf(["component", "interface", 0]),
      pointerOf(["component", "interface", 1]),
    ];
    const byRow = findingsByRow(rows, []);
    for (const row of rows) expect(byRow.get(row) ?? []).toEqual([]);
  });

  test("an empty file: no rows, whatever findings there are", () => {
    const byRow = findingsByRow([], [finding(pointerOf(["component", "interface", 0]), "stray")]);
    expect(byRow.size).toBe(0);
  });

  test("rows never nest on this page, but a finding under both is put in both where they do", () => {
    const outer = pointerOf(["component", "interface", 0]);
    const inner = `${outer}.definition`;
    const underBoth = finding(`${inner}.unit`, "both");
    const byRow = findingsByRow([outer, inner], [underBoth]);
    expect(byRow.get(outer)).toEqual([underBoth]);
    expect(byRow.get(inner)).toEqual([underBoth]);
  });

  test("worst first: a row's findings keep the order they were given in, not sorted again", () => {
    const at = pointerOf(["component", "interface", 0]);
    const error = finding(at, "error-first");
    const warning = finding(at, "warning-second");
    const byRow = findingsByRow([at], [error, warning]);
    expect(byRow.get(at)).toEqual([error, warning]);
  });

  test("a row absent from any finding's boundaries answers via ?? [], not a stored empty array", () => {
    const present = pointerOf(["component", "interface", 0]);
    const absent = pointerOf(["component", "interface", 1]);
    const byRow = findingsByRow([present, absent], [finding(present, "only-present")]);
    expect(byRow.has(absent)).toBe(false);
    expect(byRow.get(absent) ?? []).toEqual([]);
  });

  describe("property: equals the per-row filter, for random rows and findings", () => {
    /** A tiny deterministic PRNG (mulberry32), so this property test explores many shapes of
     * pointer without ever flaking in CI - the same `seed` always walks the same sequence. */
    function mulberry32(seed: number): () => number {
      let state = seed;
      return () => {
        state = (state + 0x6d2b79f5) | 0;
        let t = state;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
    }

    /** The name pool random pointers draw from - "unit" and "units" deliberately both in it, one
     * a literal text-prefix of the other, so some trials probe the same near-miss shape as the
     * dedicated "unit is not a prefix of units" test above, beside the indices below probing the
     * brief's own `[1]`-against-`[12]` shape. "1" and "12" too, keys spelled as numerals (the
     * final review's fix wave, Task 11f's parked minor): a pointer through such a key - `a.1`,
     * `a.12` - reads like an array index without being one, and a key's near miss, `.1` against
     * `.12`, is drawn beside an index's. */
    const NAMES = [
      "component",
      "interface",
      "definition",
      "unit",
      "units",
      "kind",
      "a",
      "b",
      "1",
      "12",
    ];

    /** A random declaration-like pointer segment: a short name, or an index up to 15 - just
     * large enough for a near-miss like `[1]` against `[12]` to turn up on its own. */
    function randomPart(rand: () => number): string | number {
      return rand() < 0.4
        ? Math.floor(rand() * 16)
        : (NAMES[Math.floor(rand() * NAMES.length)] as string);
    }

    /** A random pointer of `depth` to `depth + 2` segments, the first never an index (`pointer.
     * ts`'s own `pointerOf` would still spell one, but no real pointer on this page starts with
     * one). */
    function randomPointer(rand: () => number, depth: number): string {
      const length = depth + Math.floor(rand() * 3);
      const parts: (string | number)[] = [NAMES[Math.floor(rand() * NAMES.length)] as string];
      for (let at = 1; at < length; at += 1) parts.push(randomPart(rand));
      return pointerOf(parts);
    }

    /** One random finding's pointer: exactly one of `rows` a third of the time (the equality
     * branch of `within`), one of `rows` extended by a further name or index a third of the time
     * (its two `startsWith` branches), and a fully independent pointer the rest - almost always a
     * miss, random pointers sharing a prefix only by chance, which exercises the no-boundary-
     * matched path. */
    function randomFindingPointer(rand: () => number, rows: readonly string[]): string {
      const row = rows[Math.floor(rand() * rows.length)] as string;
      const branch = rand();
      if (branch < 1 / 3) return row;
      if (branch < 2 / 3) {
        return rand() < 0.5
          ? `${row}.${randomPointer(rand, 0)}`
          : `${row}[${Math.floor(rand() * 16)}]`;
      }
      return randomPointer(rand, 0);
    }

    test("200 random trials", () => {
      const rand = mulberry32(0xc0ffee);
      for (let trial = 0; trial < 200; trial += 1) {
        const rowCount = 1 + Math.floor(rand() * 5);
        const rows = Array.from({ length: rowCount }, () => randomPointer(rand, 1));
        const findingCount = Math.floor(rand() * 20);
        const findings = Array.from({ length: findingCount }, (_, index) =>
          finding(randomFindingPointer(rand, rows), `t${trial}-f${index}`),
        );
        const byRow = findingsByRow(rows, findings);
        for (const row of rows) {
          expect(byRow.get(row) ?? []).toEqual(bruteForceRow(row, findings));
        }
      }
    });
  });
});
