import type { GraphFlow } from "../api/types";

/**
 * The modules to keep bright when one is hovered: itself, and whatever it produces for or reads
 * from - spec 5.4, "every module and arrow that is not the module or one of its direct
 * neighbours" fades.
 *
 * Direct means one flow away in either direction: a module two steps down a chain is not a
 * neighbour, which is the whole point of the fading on a canvas of two hundred modules.
 */
export function neighboursOf(path: string, flows: readonly GraphFlow[]): Set<string> {
  const near = new Set([path]);
  for (const flow of flows) {
    if (flow.from === path) near.add(flow.to);
    if (flow.to === path) near.add(flow.from);
  }
  return near;
}
