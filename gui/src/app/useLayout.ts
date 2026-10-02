import { useEffect, useRef, useState } from "react";
import type { GraphFlow, GraphModule } from "../api/types";
import { type Placed, shapeOf } from "../lib/layout";
import type { LayoutAnswer } from "./layoutWorker";

/**
 * The graph's layout, made once per shape and off the main thread (design doc §6, Ruling 2): one
 * worker for the page's whole life, asked again only when `shapeOf` changes - never for a
 * revision that only changes a module's findings counts or `loaded`, or a flow's objects,
 * severity or disagreements. `placed` is the last layout that answered successfully; it stays
 * what it was while the next is made, and is never `null` again once it has answered once, so
 * `GraphPage` can tell "no layout yet" from "the current one, kept while a new one is made" by
 * nothing more than whether this is still `null`. `error` names the last answer that failed
 * instead, beside `placed` rather than in place of it, so a shape dagre cannot lay out (Step 2:
 * it overflows its stack on a long enough chain) never empties a canvas already drawn.
 *
 * Glue only (Global Constraints: "no decision may live in a .tsx file... a src/app hook is glue
 * only"): `shapeOf` is `gui/src/lib/layout.ts`'s own, under the Vitest gate; the one thing this
 * hook decides for itself is which answer a message belongs to, immediately below.
 */
export function useLayout(
  modules: readonly GraphModule[],
  flows: readonly GraphFlow[],
): { placed: Placed[] | null; error: string | null } {
  const [placed, setPlaced] = useState<Placed[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const worker = useRef<Worker | null>(null);
  // `latest` mirrors this render's own `modules`/`flows`, written unconditionally below rather
  // than read from the posting effect's own closure: that effect runs only when `shape` changes,
  // and depending it on `modules`/`flows` as well would also re-run it, and so re-post to the
  // worker, for a revision whose shape did not change - exactly the layout this hook exists to
  // avoid making again. Writing a ref during render is safe here because nothing this render
  // returns reads it back; only a later effect does.
  const latest = useRef({ modules, flows });
  latest.current = { modules, flows };
  // The shape most recently posted (`wanted`), and every shape posted whose answer has not
  // arrived yet, oldest first (`requested`). A worker answers in the order it was asked, so the
  // oldest outstanding entry is always the request this next message answers; comparing it
  // against `wanted` is what lets a message for a shape this hook has since moved past - one
  // superseded by a later post before its own answer arrived - be told apart from the answer to
  // the shape it is currently asking for, and dropped rather than overwriting `placed` or `error`
  // with a layout for a shape no longer on screen.
  const bound = useRef({ wanted: "", requested: [] as string[] });

  useEffect(() => {
    const created = new Worker(new URL("./layoutWorker.ts", import.meta.url), {
      type: "module",
    });
    worker.current = created;
    created.onmessage = (event: MessageEvent<LayoutAnswer>) => {
      const respondingTo = bound.current.requested.shift();
      if (respondingTo !== bound.current.wanted) return;
      if (event.data.placed !== undefined) {
        setPlaced(event.data.placed);
        setError(null);
      } else if (event.data.error !== undefined) {
        setError(event.data.error);
      }
    };
    return () => {
      created.terminate();
      worker.current = null;
    };
  }, []);

  const shape = shapeOf(modules, flows);
  useEffect(() => {
    bound.current.wanted = shape;
    bound.current.requested.push(shape);
    worker.current?.postMessage({
      modules: latest.current.modules,
      flows: latest.current.flows,
    });
  }, [shape]);

  return { placed, error };
}
