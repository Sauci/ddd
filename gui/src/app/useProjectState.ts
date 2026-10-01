import { useEffect, useState, useSyncExternalStore } from "react";
import { getState } from "../api/client";
import type { State } from "../api/types";
import { analysed, updatingOf } from "../lib/updating";
import { ownEdits } from "../state/edits";
import { followStates } from "../state/revisions";

/**
 * The open project as the server last said it is, and whether the server stopped answering.
 *
 * `latest` is every state followed, the one before the project's first analysis included;
 * `state` is `latest` once it holds an analysed revision, and `null` before - no screen draws, or
 * asks the server anything, until there is one. `updating` says the findings on screen may be
 * about to change, from `latest` and the page's own last edit.
 */
export function useProjectState(open: boolean): {
  state: State | null;
  latest: State | null;
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
      signal: controller.signal,
    }).catch((error: unknown) =>
      setFailure(error instanceof Error ? error.message : String(error)),
    );
    return () => controller.abort();
  }, [open]);
  return {
    state: latest !== null && analysed(latest) ? latest : null,
    latest,
    updating: latest !== null && updatingOf(latest, ownEdit),
    stopped,
    failure,
  };
}
