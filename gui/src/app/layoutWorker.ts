/**
 * The graph's layout, made off the main thread (design doc §6, Ruling 2): dagre's own cost -
 * measured while planning at 173 to 266 ms for 1,200 components and 475 to 1,164 ms for 3,333 -
 * is well over the 100 ms a stall may last, so it never runs on the thread that draws the page or
 * answers typing. `useLayout` (`gui/src/app/useLayout.ts`) is this worker's only reader: one
 * message in, `{ modules, flows }`, one answer out, `{ placed }` or `{ error }`.
 *
 * This file is built as a module worker of its own (`new Worker(new URL(...), { type: "module"
 * }))`, the construction `useLayout` uses): the page's content security policy allows a worker
 * the build emits as a file of its own, and refuses one made from a `blob:`.
 *
 * Typed against the global `self`/`addEventListener`/`postMessage` the page's own "DOM" library
 * already gives every file here (`tsconfig.json`), not the separate "webworker" library - the
 * two cannot both be in scope at once, and adding a second tsconfig for one file was not worth
 * it: `self`'s "message" event is typed `MessageEvent` under "DOM" too, since a window can
 * receive one from another window the same way a worker receives one from the thread that made
 * it, and `postMessage`'s "DOM" signature accepts a lone message with no target origin.
 */
import type { GraphFlow, GraphModule } from "../api/types";
import { laidOut, type Placed } from "../lib/layout";

interface LayoutRequest {
  modules: GraphModule[];
  flows: GraphFlow[];
}

export interface LayoutAnswer {
  placed?: Placed[];
  error?: string;
}

self.addEventListener("message", (event: MessageEvent<LayoutRequest>) => {
  const { modules, flows } = event.data;
  try {
    const placed = laidOut(modules, flows, {});
    self.postMessage({ placed } satisfies LayoutAnswer);
  } catch (error) {
    // dagre overflows its stack on a long enough chain of producers and consumers - measured
    // while planning at 1,800 components - and a layout that fails says so, rather than leaving
    // the canvas on this shape empty for good (Step 2).
    const message = error instanceof Error ? error.message : String(error);
    self.postMessage({ error: message } satisfies LayoutAnswer);
  }
});
