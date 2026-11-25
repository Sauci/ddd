import { askedAgain, ServerUnreachable } from "../api/client";
import type { State } from "../api/types";
import { askAgainIn, missedSaid, RETRY_MS } from "../lib/asking";

export interface Follow {
  getState: (after: number | null, signal: AbortSignal) => Promise<State>;
  onState: (state: State) => void;
  /** Whether ddd gui has stopped: told once the second ask in a row failed and the last went
   * unanswered, and again once it answers. */
  onStopped: (stopped: boolean) => void;
  /** Why ddd gui failed the long poll where it answered with no state - its own words for a 5xx,
   * or that its answer is not json - told once the second ask in a row failed and the last failed
   * so, and `null` once it answers with a state, or stops. */
  onFailed: (failure: string | null) => void;
  signal: AbortSignal;
  retryMs?: number;
  sleep?: (ms: number, signal: AbortSignal) => Promise<void>;
}

/**
 * Keeps a page on the newest state of the open project: asks for anything newer than the version
 * of the state it has - which the server answers as soon as there is something, or after waiting -
 * and asks again. A state can be new with the same revision: an analysis asked for, an edit
 * written, the undo entry it leaves.
 *
 * An ask that fails so that it is asked again (`askedAgain`, api/client.ts: no answer at all, a
 * 5xx, or an answer that does not parse) is asked again after `PROMPT_RETRY_MS`, saying nothing
 * (lib/asking.ts, decision 15.4); only when that one fails too is it said, once, and from then on
 * the server is asked every `retryMs`. What is said is the last ask's: that the server has stopped,
 * where it went unanswered (`onStopped`), else why it failed, in its own words (`onFailed`) -
 * which says ddd gui runs, so that the one gives way to the other. An answer lifts either, and
 * starts this over. A refusal, a 4xx, ends the follow with it: asked again, it is answered again.
 */
export async function followStates(follow: Follow): Promise<void> {
  const { getState, onState, onStopped, onFailed, signal } = follow;
  const retryMs = follow.retryMs ?? RETRY_MS;
  const sleep = follow.sleep ?? wait;
  let after: number | null = null;
  // How many asks in a row have failed, of whatever kind, and what is said of them.
  let missed = 0;
  let stopped = false;
  let failure: string | null = null;
  const say = (nowStopped: boolean, nowFailure: string | null): void => {
    if (nowStopped !== stopped) {
      stopped = nowStopped;
      onStopped(stopped);
    }
    if (nowFailure !== failure) {
      failure = nowFailure;
      onFailed(failure);
    }
  };
  while (!signal.aborted) {
    try {
      const state = await getState(after, signal);
      missed = 0;
      say(false, null);
      if (after === null || state.version > after) onState(state);
      after = state.version;
    } catch (error) {
      if (signal.aborted) return;
      if (!askedAgain(error)) throw error;
      missed += 1;
      if (missedSaid(missed)) {
        if (error instanceof ServerUnreachable) say(true, null);
        else say(false, error.message);
      }
      await sleep(askAgainIn(missed, retryMs), signal);
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
