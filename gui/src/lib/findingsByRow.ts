import type { ListedFinding } from "../api/types";

/**
 * A file's findings, grouped by the row of `rows` each one is within - the same test `within`
 * (`lib/pointer.ts`) makes of a single pointer and entry, answered for every row at once.
 *
 * `ComponentPage` once asked this per row - `findings.filter((finding) => within(finding.
 * pointer, at))`, `rows.length` of them over the very same `findings` array - which on a file of
 * 3,334 declarations and 4,167 findings cost 13.9 million `within` calls a render, three renders
 * an Apply (Task 11f). This walks each finding's pointer back through its own boundaries once -
 * the pointer itself, then each prefix ending right before a `.` or a `[`, exactly the set of
 * `entry` values `within` would accept for it - and looks each boundary up in a `Set` of `rows`,
 * so the cost is O(findings × a pointer's own depth), never O(rows × findings).
 *
 * A row no finding ever lands on is left out of the answer rather than stored as an empty array:
 * a caller reads `byRow.get(row) ?? []`, which a large file's rows mostly do.
 *
 * Rows never nest on this page - no row's own pointer is itself inside another's - but this
 * function does not lean on that: a finding inside two rows, one nested in the other, is put in
 * both, exactly as asking `findings.filter((finding) => within(finding.pointer, row))` of each
 * separately would answer. Every row's own answer keeps `findings`' own order, worst first,
 * since each finding is visited once, in that order, and offered to every row it falls within.
 */
export function findingsByRow(
  rows: readonly string[],
  findings: readonly ListedFinding[],
): ReadonlyMap<string, ListedFinding[]> {
  const atRow = new Set(rows);
  const byRow = new Map<string, ListedFinding[]>();
  for (const finding of findings) {
    for (const boundary of boundariesOf(finding.pointer)) {
      if (!atRow.has(boundary)) continue;
      const own = byRow.get(boundary);
      if (own === undefined) byRow.set(boundary, [finding]);
      else own.push(finding);
    }
  }
  return byRow;
}

/**
 * Every boundary of `pointer` that `within(pointer, entry)` (`lib/pointer.ts`) would accept as
 * `entry`: `pointer` itself, and each prefix ending right before a `.` or a `[` - the same two
 * characters `within`'s own `startsWith` checks test for. Read directly off the string, rather
 * than through `segments`' own regular expression, so the two can never tokenise one pointer two
 * different ways.
 */
function boundariesOf(pointer: string): string[] {
  const boundaries: string[] = [];
  for (let at = 0; at < pointer.length; at += 1) {
    const char = pointer.charAt(at);
    if (char === "." || char === "[") boundaries.push(pointer.slice(0, at));
  }
  boundaries.push(pointer);
  return boundaries;
}
