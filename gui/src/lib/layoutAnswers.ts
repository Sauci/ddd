/**
 * What the worker answers, what `useLayout` keeps from it, and what `GraphPage` draws because of
 * it - every one of those three decisions, so that `gui/src/app/useLayout.ts` is glue only
 * (review fix round 1, Important 1 and Minor 6).
 */
import type { Placed } from "./layout";

/**
 * One message back from the layout worker, always naming the shape it was asked to lay out.
 * `useLayout` compares this against the shape it currently wants (`withAnswer`, below) rather
 * than trusting the order answers arrive in, which a worker remade mid-flight (StrictMode) can
 * no longer be trusted to preserve on its own.
 *
 * `placed` is set whether dagre made the layout or the no-recursion fallback did (`ranksOnly`
 * true, Critical 1); `error` is set instead when neither could - dagre failed with something
 * other than a stack overflow, or the fallback itself somehow did.
 */
export interface LayoutAnswer {
  shape: string;
  placed?: Placed[];
  ranksOnly?: boolean;
  error?: string;
}

/** What `useLayout` keeps: the last layout that succeeded, independent of whether the most
 * recent answer was itself a success. */
export interface LayoutState {
  placed: Placed[] | null;
  ranksOnly: boolean;
  error: string | null;
}

export const INITIAL_LAYOUT_STATE: LayoutState = { placed: null, ranksOnly: false, error: null };

/**
 * Shown quietly above the canvas, never a `Banner`, when the worker could not lay the graph out
 * with dagre and fell back to ranking it by hand (Critical 1: dagre overflows its stack on a
 * long enough chain - about 908 modules deep in the worker). The words a reader sees for this,
 * decided here rather than in `GraphPage.tsx`.
 */
export const RANKS_ONLY_NOTE =
  "Laid out in ranks only: the project is too large for the full layout.";

/**
 * Shown as the error banner when the worker itself fails, rather than a layout it tried and
 * could not make (Minor 3): it never started, it died, or a rebuild served while the page was
 * open left a stale worker URL answering something that is not JavaScript at all. Without this,
 * "Laying the project out…" stays up for good.
 */
export const WORKER_FAILED = "The layout worker stopped; reload the page to try again.";

/**
 * `state` with `answer` applied, or `state` unchanged when `answer` is not for `wanted` - the
 * shape `useLayout` is currently asking for. A worker answers in the order it is asked, but a
 * later shape can be posted before an earlier one's answer arrives; comparing the answer's own
 * echoed shape against `wanted`, rather than trusting arrival order, is what drops that stale
 * answer instead of overwriting `state` with a layout for a shape no longer on screen - correctly
 * even across a worker remade mid-flight, since nothing here depends on how many messages were
 * sent or in what order they come back, only on what shape this one answer says it is for.
 *
 * A successful answer - `placed`, with or without `ranksOnly` - replaces `placed` and clears
 * `error`: the one thing newly landing is allowed to say is "here is what to draw now", whether
 * dagre made it or the fallback did. A failed answer only sets `error`, leaving `placed` and
 * `ranksOnly` exactly as they were, so a layout that fails after one that succeeded never empties
 * the canvas (Step 2) - only `layoutScreen`'s choice of what else to show beside it changes.
 */
export function withAnswer(state: LayoutState, answer: LayoutAnswer, wanted: string): LayoutState {
  if (answer.shape !== wanted) return state;
  if (answer.placed !== undefined) {
    return { placed: answer.placed, ranksOnly: answer.ranksOnly ?? false, error: null };
  }
  if (answer.error !== undefined) return { ...state, error: answer.error };
  return state;
}

/**
 * What `GraphPage` draws for one `LayoutState` - the choice Minor 6 found sitting in
 * `GraphPage.tsx` itself, untested: waiting for the first layout, that first one's own error
 * alone, or the canvas - which independently may carry the error banner for a *later* layout
 * that failed, the ranks-only note for one the fallback made, both, or neither. `GraphPage` reads
 * this tag and these two fields; it decides nothing about when either applies.
 */
export type LayoutScreen =
  | { readonly kind: "waiting" }
  | { readonly kind: "failed"; readonly message: string }
  | {
      readonly kind: "drawn";
      readonly placed: Placed[];
      readonly errorMessage: string | null;
      readonly note: string | null;
    };

export function layoutScreen(state: LayoutState): LayoutScreen {
  if (state.placed === null) {
    return state.error === null ? { kind: "waiting" } : { kind: "failed", message: state.error };
  }
  return {
    kind: "drawn",
    placed: state.placed,
    errorMessage: state.error,
    note: state.ranksOnly ? RANKS_ONLY_NOTE : null,
  };
}
