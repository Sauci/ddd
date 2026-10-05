import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphFlow, GraphModule } from "../api/types";
import type { Placed } from "../lib/layout";
import {
  INITIAL_LAYOUT_STATE,
  type LayoutAnswer,
  type LayoutState,
  WORKER_FAILED,
  withAnswer,
} from "../lib/layoutAnswers";
import { shapeOf } from "../lib/shape";

/**
 * The graph's layout, made once per shape and off the main thread (design doc §6, Ruling 2): one
 * worker for the page's whole life, asked again only when `shapeOf` changes - never for a
 * revision that only changes a module's findings counts or `loaded`, or a flow's objects,
 * severity or disagreements.
 *
 * Glue only (Global Constraints: "no decision may live in a .tsx file... a src/app hook is glue
 * only"): `shapeOf` and `withAnswer` are `gui/src/lib`'s own, under the Vitest gate. This hook
 * decides nothing - it only tracks which shape it currently wants (`wanted`, written by the
 * posting effect and read by the worker's handlers to tell a stale answer from the one they are
 * waiting for) and which `modules`/`flows` go with it (`latest`, read by that same effect so it
 * does not also have to depend on `modules`/`flows` themselves - depending on them would repost
 * on every revision whose *shape* did not change, exactly the layout this hook exists to avoid
 * making again).
 */
export function useLayout(
  modules: readonly GraphModule[],
  flows: readonly GraphFlow[],
): { placed: Placed[] | null; ranksOnly: boolean; error: string | null } {
  const [state, setState] = useState<LayoutState>(INITIAL_LAYOUT_STATE);
  const worker = useRef<Worker | null>(null);
  // Memoised (review fix round 1, Minor 5): `shapeOf` walks every module and arrow, building a
  // string of up to a few megabytes on a large project, and this hook's caller re-renders on
  // every hover and keystroke over the canvas - recomputing it only when `modules`/`flows`
  // themselves have a new identity (a new revision) keeps that walk off those renders.
  const shape = useMemo(() => shapeOf(modules, flows), [modules, flows]);
  // Mirrors this render's own `modules`/`flows`, written unconditionally below rather than read
  // from the posting effect's own closure: that effect runs only when `shape` changes, and
  // depending it on `modules`/`flows` as well would also re-run it, and so re-post, for a
  // revision whose shape did not change. Writing a ref during render is safe here because
  // nothing this render returns reads it back; only the effect below does.
  const latest = useRef({ modules, flows });
  latest.current = { modules, flows };
  // The shape currently wanted: written by the posting effect at the moment it posts, read by
  // the worker's handlers (attached once, on mount) to bind an answer to the request it belongs
  // to - comparing the answer's own echoed shape against this, rather than trusting the order
  // answers arrive in, which a worker remade mid-flight (StrictMode's double mount) cannot be
  // trusted to preserve (`withAnswer`'s own doc, `gui/src/lib/layoutAnswers.ts`).
  const wanted = useRef(shape);

  useEffect(() => {
    const created = new Worker(new URL("./layoutWorker.ts", import.meta.url), {
      type: "module",
    });
    worker.current = created;
    created.onmessage = (event: MessageEvent<LayoutAnswer>) => {
      setState((current) => withAnswer(current, event.data, wanted.current));
    };
    // A worker that fails to start, or dies - including a stale URL from before a rebuild
    // answering something that is not JavaScript at all (Minor 3) - fires this instead of ever
    // answering a message; without it the page is left on "Laying the project out…" for good.
    created.onerror = () => {
      setState((current) =>
        withAnswer(current, { shape: wanted.current, error: WORKER_FAILED }, wanted.current),
      );
    };
    return () => {
      created.terminate();
      worker.current = null;
    };
  }, []);

  useEffect(() => {
    wanted.current = shape;
    worker.current?.postMessage({
      modules: latest.current.modules,
      flows: latest.current.flows,
    });
  }, [shape]);

  return { placed: state.placed, ranksOnly: state.ranksOnly, error: state.error };
}
