/**
 * The graph's layout, made off the main thread (design doc §6, Ruling 2): dagre's own cost -
 * measured while planning at 173 to 266 ms for 1,200 components and 475 to 1,164 ms for 3,333 -
 * is well over the 100 ms a stall may last, so it never runs on the thread that draws the page or
 * answers typing. `useLayout` (`gui/src/app/useLayout.ts`) is this worker's only reader: one
 * message in, `{ modules, flows }`, one answer out, always naming the shape it laid out
 * (`LayoutAnswer`, `gui/src/lib/layoutAnswers.ts`) beside `placed`, `placed` with `ranksOnly`, or
 * `error`.
 *
 * Glue only (review fix round 2, New Important 1): whether dagre's own layout stands or `ranked`
 * replaces it is `layoutOf`'s decision (`gui/src/lib/layout.ts`), under Vitest; this file only
 * calls it and turns what comes back into a message. `shapeOf` itself can still throw before
 * either is reached - defensively, on modules or flows malformed enough that even sorting them
 * fails - and that throw is not this file's to catch either; it reaches `useLayout`'s `onerror`
 * the same as a worker that fails to start at all (`layoutAnswers.ts`'s own doc on `WORKER_
 * FAILED`).
 *
 * Vite 8 builds this file as an IIFE by default (`worker.format`), not an ES module - what makes
 * it a *module worker* is the construction `useLayout` uses to load it, `new Worker(new URL(...),
 * { type: "module" })`, which is also what gets it built and served as a file of its own rather
 * than inlined: the page's content security policy allows that, and refuses one made from a
 * `blob:`.
 *
 * Typed against the global `self`/`addEventListener`/`postMessage` the page's own "DOM" library
 * already gives every file here (`tsconfig.json`), not the separate "webworker" library - the
 * two cannot both be in scope at once, and adding a second tsconfig for one file was not worth
 * it: `self`'s "message" event is typed `MessageEvent` under "DOM" too, since a window can
 * receive one from another window the same way a worker receives one from the thread that made
 * it, and `postMessage`'s "DOM" signature accepts a lone message with no target origin.
 */
import type { GraphFlow, GraphModule } from "../api/types";
import { layoutOf } from "../lib/layout";
import type { LayoutAnswer } from "../lib/layoutAnswers";
import { shapeOf } from "../lib/shape";

interface LayoutRequest {
  modules: GraphModule[];
  flows: GraphFlow[];
}

self.addEventListener("message", (event: MessageEvent<LayoutRequest>) => {
  const { modules, flows } = event.data;
  const shape = shapeOf(modules, flows);
  try {
    const { placed, ranksOnly } = layoutOf(modules, flows);
    self.postMessage({ shape, placed, ranksOnly } satisfies LayoutAnswer);
  } catch (error) {
    // A layout `layoutOf` could not make at all - a `RangeError` is already `ranksOnly` by the
    // time it gets here - says so, rather than leaving the canvas on this shape empty for good
    // (Step 2).
    const message = error instanceof Error ? error.message : String(error);
    self.postMessage({ shape, error: message } satisfies LayoutAnswer);
  }
});
