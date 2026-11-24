import type { State } from "../api/types";

/** Whether a state holds an analysed revision: `0` is the open project's before its first. */
export function analysed(state: Pick<State, "revision">): boolean {
  return state.revision > 0;
}

/** What the page says where a tab's content goes while the project's first analysis is on its
 * way. */
export const ANALYSING = "Analysing the project…";

/** What the page says where a tab's content goes before the project's first analysis has landed:
 * that it is being analysed, or nothing once that analysis failed (`State.failed`) - the banner
 * under the masthead says why, and when it is asked again (`loadBanner`, lib/unloaded.ts) - and
 * nothing once ddd gui has `stopped`, which its own banner says: no analysis is on its way then,
 * as the banner of a failed one promises no other once stopped. Said to be under way, a first
 * analysis that failed read as analysing for good, the next poll asking for another that fails
 * again. */
export function beforeAnalysis(failed: string | null, stopped: boolean): string | null {
  return failed === null && !stopped ? ANALYSING : null;
}

/** Whether the findings on screen may be about to change (spec §6): an analysis is asked for or
 * running, or the page's own last edit is newer than the revision it holds - which covers the
 * moment between an edit's answer and the state saying it is being analysed. Never before the
 * project's first analysis has landed: there is no finding on screen to update, and the page says
 * "Analysing the project…" instead. */
export function updatingOf(
  state: Pick<State, "revision" | "analysing" | "edits">,
  ownEdit: number,
): boolean {
  return analysed(state) && (state.analysing || ownEdit > state.edits);
}
