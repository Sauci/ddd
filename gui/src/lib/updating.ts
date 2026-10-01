import type { State } from "../api/types";

/** Whether a state holds an analysed revision: `0` is the open project's before its first. */
export function analysed(state: Pick<State, "revision">): boolean {
  return state.revision > 0;
}

/** Whether the findings on screen may be about to change (spec §6): an analysis is asked for or
 * running, or the page's own last edit is newer than the revision it holds - which covers the
 * moment between an edit's answer and the state saying it is being analysed. */
export function updatingOf(state: Pick<State, "analysing" | "edits">, ownEdit: number): boolean {
  return state.analysing || ownEdit > state.edits;
}
