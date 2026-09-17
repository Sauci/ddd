import { useEffect, useState } from "react";
import { getState } from "../api/client";
import type { State } from "../api/types";
import { followRevisions } from "../state/revisions";

/** The newest revision of the open project, and whether the server stopped answering. */
export function useProjectState(open: boolean): {
  state: State | null;
  stopped: boolean;
  failure: string | null;
} {
  const [state, setState] = useState<State | null>(null);
  const [stopped, setStopped] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    followRevisions({
      getState: (after, signal) => getState(after, signal),
      onState: setState,
      onStopped: setStopped,
      signal: controller.signal,
    }).catch((error: unknown) =>
      setFailure(error instanceof Error ? error.message : String(error)),
    );
    return () => controller.abort();
  }, [open]);
  return { state, stopped, failure };
}
