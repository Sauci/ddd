import { ServerUnreachable } from "../api/client";
import type { State } from "../api/types";

export interface Follow {
  getState: (after: number | null, signal: AbortSignal) => Promise<State>;
  onState: (state: State) => void;
  onStopped: (stopped: boolean) => void;
  signal: AbortSignal;
  retryMs?: number;
  sleep?: (ms: number, signal: AbortSignal) => Promise<void>;
}

/**
 * Keeps a page on the newest revision: asks for anything newer than the revision it has - which
 * the server answers when there is one, or after waiting - and asks again. A server that stops
 * answering is reported once and retried; when it answers again that is reported too. Any other
 * failure ends the follow with it.
 */
export async function followRevisions(follow: Follow): Promise<void> {
  const { getState, onState, onStopped, signal } = follow;
  const retryMs = follow.retryMs ?? 2000;
  const sleep = follow.sleep ?? wait;
  let after: number | null = null;
  let stopped = false;
  while (!signal.aborted) {
    try {
      const state = await getState(after, signal);
      if (stopped) {
        stopped = false;
        onStopped(false);
      }
      if (after === null || state.revision > after) onState(state);
      after = state.revision;
    } catch (error) {
      if (signal.aborted) return;
      if (!(error instanceof ServerUnreachable)) throw error;
      if (!stopped) {
        stopped = true;
        onStopped(true);
      }
      await sleep(retryMs, signal);
    }
  }
}

/** Resolves after `ms`, or as soon as `signal` is aborted. */
export function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }
    let timer: ReturnType<typeof setTimeout> | undefined;
    const done = (): void => {
      clearTimeout(timer);
      signal.removeEventListener("abort", done);
      resolve();
    };
    timer = setTimeout(done, ms);
    signal.addEventListener("abort", done, { once: true });
  });
}
