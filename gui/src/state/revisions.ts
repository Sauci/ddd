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
 * How long the follow waits before asking again when a request goes unanswered, before it says
 * anything: the server is reported stopped only once this second ask goes unanswered too.
 * Reported at the first, one request that failed on its way - its connection refused or reset -
 * left every panel's Apply disabled under "ddd gui has stopped" until the next ask, `retryMs`
 * later, whatever that ask found. A server that has stopped is reported this much later.
 */
const PROMPT_RETRY_MS = 250;

/**
 * Keeps a page on the newest state of the open project: asks for anything newer than the version
 * of the state it has - which the server answers as soon as there is something, or after waiting -
 * and asks again. A state can be new with the same revision: an analysis asked for, an edit
 * written, the undo entry it leaves. A request that goes unanswered is asked again after
 * `PROMPT_RETRY_MS`, and only when that one goes unanswered too is the server reported stopped,
 * once; it is then asked again every `retryMs`, and when it answers that is reported too. An
 * answer starts this over. Any other failure ends the follow with it.
 */
export async function followStates(follow: Follow): Promise<void> {
  const { getState, onState, onStopped, signal } = follow;
  const retryMs = follow.retryMs ?? 2000;
  const sleep = follow.sleep ?? wait;
  let after: number | null = null;
  let unanswered = false;
  let stopped = false;
  while (!signal.aborted) {
    try {
      const state = await getState(after, signal);
      unanswered = false;
      if (stopped) {
        stopped = false;
        onStopped(false);
      }
      if (after === null || state.version > after) onState(state);
      after = state.version;
    } catch (error) {
      if (signal.aborted) return;
      if (!(error instanceof ServerUnreachable)) throw error;
      if (!unanswered) {
        unanswered = true;
        await sleep(PROMPT_RETRY_MS, signal);
        continue;
      }
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
