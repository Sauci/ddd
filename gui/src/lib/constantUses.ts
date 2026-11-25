import type { ConstantUse } from "../api/types";

/**
 * The places that name a constant, one for each: a declaration whose dimension spells the constant
 * and whose condition spells it too is one place, where the server lists each spelling
 * (`ConstantUse`, one for each string naming it). Drawn as it lists them, the Used by table showed
 * the declaration twice, two rows of the same name leading to the same panel. The first spelling of
 * each stands, in the server's order.
 */
export function placesNaming(uses: readonly ConstantUse[]): ConstantUse[] {
  const seen = new Set<string>();
  return uses.filter((use) => {
    const place = JSON.stringify([use.path, use.kind, use.name]);
    if (seen.has(place)) return false;
    seen.add(place);
    return true;
  });
}

/**
 * What stands where a constant's Remove would be while places still name it: not the server's own
 * refusal, but the count that made it refuse, read off the table already on screen - the places
 * (`placesNaming`), where the server counts spellings. "Place", not "shape": a dimension, an axis's
 * size and a condition all spell a constant, and a condition is no shape.
 */
export function constantRemoveBlocked(name: string, places: number): string {
  const named = places === 1 ? "1 place names" : `${places} places name`;
  return `${named} ${name}, so it cannot be removed.`;
}
