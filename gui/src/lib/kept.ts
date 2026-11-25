import { ApiError } from "../api/client";

/** A tab's last good answer, and the question it answered: the tab, and anything else its query
 * names but the revision (spec 2026-10-21 §5). `data` is `undefined` once a read of the question
 * was refused since: a refusal says it has no answer, and nothing from before it is kept. */
export interface Kept<T> {
  readonly identity: string;
  readonly data: T | undefined;
}

/**
 * What a tab keeps after this render: nothing for its question once a read of it was refused
 * (`refusedRead`), not even its query's own answer, which React Query keeps when a read of the
 * same key again is refused (P19c-15: kept, the answer from before the refusal came back under the
 * banner of a server failure on the next revision); else its query's answer when the answer is its
 * own, not a placeholder carried from the revision before; otherwise what it kept already. The
 * very object it was given while nothing changed, so that `useKept`, which stores it while
 * rendering, stops there.
 */
export function kept<T>(
  data: T | undefined,
  placeholder: boolean,
  identity: string,
  before: Kept<T> | null,
  error: unknown,
): Kept<T> | null {
  const same = before !== null && before.identity === identity;
  if (refusedRead(error)) {
    return same && before.data === undefined ? before : { identity, data: undefined };
  }
  if (data === undefined || placeholder) return before;
  if (same && before.data === data) return before;
  return { identity, data };
}

/** Whether a read's error is the server's answer about what was asked - a refusal, such as an
 * object no longer declared, or a shape no grid can draw - rather than a read that failed: no
 * answer at all (`ServerUnreachable`), or the server failing on it (a 5xx). */
export function refusedRead(error: unknown): boolean {
  return error instanceof ApiError && error.status < 500;
}

/**
 * What a screen shows: nothing once its read was refused (`refusedRead`), not even its query's
 * own answer, which React Query keeps when a read of the same key again is refused - a refusal
 * says something about what was asked, and an answer from before it would show an object the
 * project no longer has. Otherwise its query's answer while it holds one - its own, or the
 * revision before's, carried while the next is read - and, once the next read failed and the
 * query holds nothing, the last good answer kept for the same question (P19b-20: React Query
 * serves a placeholder to a pending read alone, so a failed read of a new revision left the
 * screen with nothing to draw but its error). After a refusal, nothing from before it: neither
 * what was kept, which `kept` drops, nor the placeholder React Query carries to the next read -
 * the last answer it had, which is the one from before the refusal. A screen that never had an
 * answer shows nothing, and its error alone, as before. Never another question's answer: the
 * canvas's names its project, a component's its file.
 */
export function shown<T>(
  data: T | undefined,
  placeholder: boolean,
  identity: string,
  before: Kept<T> | null,
  error: unknown,
): T | undefined {
  if (refusedRead(error)) return undefined;
  const same = before !== null && before.identity === identity;
  if (placeholder && same && before.data === undefined) return undefined;
  if (data !== undefined) return data;
  return same ? before.data : undefined;
}
