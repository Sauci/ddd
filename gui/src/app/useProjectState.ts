import { useEffect, useState, useSyncExternalStore } from "react";
import { getState } from "../api/client";
import type { RefusedBuild, State } from "../api/types";
import { analysed, updatingOf } from "../lib/updating";
import { ownEdits } from "../state/edits";
import { followStates } from "../state/revisions";

/** No build record refused: one array for every state that refuses none, and before the first. */
const NONE: readonly RefusedBuild[] = [];

/**
 * The open project as the server last said it is, and whether the server stopped answering.
 *
 * Every state is followed, the one before the project's first analysis included; `state` is the
 * last of them once it holds an analysed revision, and `null` before - no screen draws, or asks
 * the server anything, until there is one. `project` is the project the last state followed is of,
 * analysed or not, and `null` before the first: what the page names (`projectName`,
 * lib/session.ts), and how it learns that another page opened another project. `failed` and
 * `refused` are the last state's too, analysed or not - why the last analysis failed and the build
 * records this DDD cannot use - so that the banner under the masthead says a first analysis that
 * failed, which no analysed state carries (`loadBanner`, lib/unloaded.ts). `updating` says the
 * findings on screen may be about to change, from the last state followed and the page's own last
 * edit. `stopped` is whether ddd gui has stopped answering, and `failure` why it fails the follow
 * while it is asked again - each lifted at its next answer (`followStates`) - or the refusal that
 * ended the follow, which nothing lifts.
 */
export function useProjectState(open: boolean): {
  state: State | null;
  project: string | null;
  failed: string | null;
  refused: readonly RefusedBuild[];
  updating: boolean;
  stopped: boolean;
  failure: string | null;
} {
  const [latest, setLatest] = useState<State | null>(null);
  const [stopped, setStopped] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const ownEdit = useSyncExternalStore(ownEdits.subscribe, ownEdits.newest);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    followStates({
      getState: (after, signal) => getState(after, signal),
      onState: setLatest,
      onStopped: setStopped,
      onFailed: setFailure,
      signal: controller.signal,
    }).catch((error: unknown) =>
      setFailure(error instanceof Error ? error.message : String(error)),
    );
    return () => controller.abort();
  }, [open]);
  return {
    state: latest !== null && analysed(latest) ? latest : null,
    project: latest === null ? null : latest.project,
    failed: latest === null ? null : latest.failed,
    refused: latest === null ? NONE : latest.refused,
    updating: latest !== null && updatingOf(latest, ownEdit),
    stopped,
    failure,
  };
}
