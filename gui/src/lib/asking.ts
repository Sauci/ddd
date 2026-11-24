import { askedAgain } from "../api/client";

/**
 * How the page asks again what failed so that it is asked again (`askedAgain`, api/client.ts:
 * no answer at all, a 5xx, or an answer that does not parse), decision 15.4: its long poll
 * (`followStates`, state/revisions.ts) and its ask of the session (`["session"]`, App.tsx), one
 * pace and one rule of what is said for both. Ended at the first such failure, the long poll
 * followed nothing more and the session drew no page, under words that said to ask again.
 */

/**
 * How long the page waits before asking again the first time an ask fails, before it says
 * anything: why it fails is said only once this second ask fails too (`missedSaid`). Said at the
 * first, one request that failed on its way - its connection refused or reset - left every panel's
 * Apply disabled under "ddd gui has stopped" until the next ask, `RETRY_MS` later, whatever that
 * ask found. A server that has stopped is said so this much later.
 */
export const PROMPT_RETRY_MS = 250;

/** How long the page waits before asking again after each later failure in a row: the follow's own
 * pace while ddd gui fails it or does not answer. */
export const RETRY_MS = 2000;

/** How long the page waits to ask again an ask that failed, the `missed`th in a row:
 * `PROMPT_RETRY_MS` after the first, `retryMs` - `RETRY_MS` unless a follow gives its own - after
 * each later one. */
export function askAgainIn(missed: number, retryMs: number = RETRY_MS): number {
  return missed <= 1 ? PROMPT_RETRY_MS : retryMs;
}

/** Whether the page says why its asks fail, `missed` of them in a row: from the second on, the
 * first being asked again at once and said nothing of. */
export function missedSaid(missed: number): boolean {
  return missed > 1;
}

/** A query the page asks again as its long poll is asked again, in React Query's words: asked
 * again for what `askedAgain` says, and never for a refusal; after the same delay, React Query
 * counting the failures in a row before the one that just failed, none at the first. A refusal
 * ends its asking, as it ends the follow. */
export const askingAgain = {
  retry: (_failures: number, error: Error): boolean => askedAgain(error),
  retryDelay: (failures: number): number => askAgainIn(failures + 1),
};

/** What React Query holds of a query asked again (`askingAgain`): whether an ask is on its way or
 * waited for - `"paused"` while a hidden tab waits to be shown - how many in a row have failed,
 * and why the last did; none once one is answered. */
export interface Asked {
  fetchStatus: "fetching" | "paused" | "idle";
  failureCount: number;
  failureReason: Error | null;
}

/**
 * What the page says under its masthead of an ask that fails and is asked again: why the long poll
 * fails (`useProjectState`'s `failure`), as `followStates` says it - or, the follow having ended
 * at a refusal, that refusal - else why its ask of the session (`session`) fails while it is asked
 * again, from the second in a row (`missedSaid`). Nothing of the session's once one of its asks is
 * answered, nor once a refusal ends its asking, which the page says in its own place. One banner,
 * the long poll's first: both are asked again together where the page opens a project.
 */
export function failureSaid(follow: string | null, session: Asked): string | null {
  if (follow !== null) return follow;
  const asking = session.fetchStatus !== "idle";
  return asking && session.failureReason !== null && missedSaid(session.failureCount)
    ? session.failureReason.message
    : null;
}
