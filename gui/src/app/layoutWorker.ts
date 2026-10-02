/**
 * The graph's layout, made off the main thread (design doc §6, Ruling 2): dagre's own cost -
 * measured while planning at 173 to 266 ms for 1,200 components and 475 to 1,164 ms for 3,333 -
 * is well over the 100 ms a stall may last, so it never runs on the thread that draws the page or
 * answers typing. `useLayout` (`gui/src/app/useLayout.ts`) is this worker's only reader: one
 * message in, `{ modules, flows }`, one answer out, always naming the shape it laid out
 * (`LayoutAnswer`, `gui/src/lib/layoutAnswers.ts`) beside `placed`, `placed` with `ranksOnly`, or
 * `error`.
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
import { laidOut, ranked } from "../lib/layout";
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
    const placed = laidOut(modules, flows, {});
    self.postMessage({ shape, placed } satisfies LayoutAnswer);
  } catch (error) {
    if (error instanceof RangeError) {
      // dagre's own layering recurses, and overflows the stack on a long enough chain of
      // producers and consumers - measured in this worker (review fix round 1, Critical 1) at
      // about 908 modules, roughly half the main thread's own 1,772, since a worker starts with
      // less stack to begin with. `ranked` never recurses, so it has no depth of its own to
      // overflow at any size, and still places every module - quietly marked `ranksOnly` rather
      // than answered as a failure, so GraphPage says so above the canvas, not in the error
      // banner (Step 2's is for a layout that could not be made at all).
      self.postMessage({
        shape,
        placed: ranked(modules, flows),
        ranksOnly: true,
      } satisfies LayoutAnswer);
      return;
    }
    // A layout that fails for any other reason says so, rather than leaving the canvas on this
    // shape empty for good (Step 2).
    const message = error instanceof Error ? error.message : String(error);
    self.postMessage({ shape, error: message } satisfies LayoutAnswer);
  }
});
