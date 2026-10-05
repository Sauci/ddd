/**
 * The graph's shape, and how many modules make React Flow cull - the two decisions the main
 * thread needs on every render (`useLayout`, `GraphPage`), kept in a file of their own so that
 * importing them never pulls in `./layout.ts`'s `laidOut` and the dagre it carries (review fix
 * round 1, Minor 2: `import { type Placed } from "./layout"` elsewhere stays type-only and is
 * erased, but a *value* import of anything sharing a module with `laidOut` kept dagre's own
 * `graphlib.Graph` reachable from the main bundle, 15,924 dead bytes of it, even though nothing
 * on the main thread ever called it).
 */
import type { GraphFlow, GraphModule } from "../api/types";

/**
 * One string standing for a graph's shape: the sorted module paths, then the sorted arrows'
 * `from` and `to` pairs. Two calls give the same string for the same modules and arrows
 * regardless of the order either was given in, and a different string the moment a module or an
 * arrow comes or goes - a revision that only changes a module's findings counts or `loaded`, or
 * an arrow's objects, severity or disagreements, carries the same modules and the same arrows,
 * so its shape is unchanged. This is what `useLayout` (`gui/src/app`) compares to decide whether
 * the layout - the one part of drawing the graph dagre's own cost makes too slow for the main
 * thread (Ruling 2) - has to be made again, rather than kept as it was for a revision that moved
 * nothing.
 */
export function shapeOf(modules: readonly GraphModule[], flows: readonly GraphFlow[]): string {
  const paths = modules.map((module) => module.path).sort();
  const arrows = flows.map((flow) => JSON.stringify([flow.from, flow.to])).sort();
  return JSON.stringify([paths, arrows]);
}

/**
 * How many modules a graph needs before drawing every node whole, rather than only the ones in
 * view, costs something a reader would notice (Ruling 2). Below this, React Flow drawing every
 * node regardless of the viewport is free enough that a reader never meets one appear late while
 * panning; `visibleOnly` is what reads this threshold, so nothing else compares against it.
 */
export const VISIBLE_ONLY_ABOVE = 200;

/**
 * Whether the canvas should ask React Flow to draw only the nodes currently in view
 * (`onlyRenderVisibleElements`), rather than every one regardless of the viewport.
 */
export function visibleOnly(count: number): boolean {
  return count > VISIBLE_ONLY_ABOVE;
}
