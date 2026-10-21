import { ApiError } from "../api/client";

/** A tab's last good answer, and the question it answered: the tab, and anything else its query
 * names but the revision (spec 2026-10-21 §5). */
export interface Kept<T> {
  readonly identity: string;
  readonly data: T;
}

/**
 * What a tab keeps after this render: its query's answer when the answer is its own, not a
 * placeholder carried from the revision before; otherwise what it kept already. The very object
 * it was given while nothing changed, so that `useKept`, which stores it while rendering, stops
 * there.
 */
export function kept<T>(
  data: T | undefined,
  placeholder: boolean,
  identity: string,
  before: Kept<T> | null,
): Kept<T> | null {
  if (data === undefined || placeholder) return before;
  if (before !== null && before.identity === identity && before.data === data) return before;
  return { identity, data };
}

/** Whether a read's error is the server's answer about what was asked - a refusal, such as an
 * object no longer declared, or a shape no grid can draw - rather than a read that failed: no
 * answer at all (`ServerUnreachable`), or the server failing on it (a 5xx). */
export function refusedRead(error: unknown): boolean {
  return error instanceof ApiError && error.status < 500;
}

/**
 * What a screen shows: its query's answer while it holds one - its own, or the revision before's,
 * carried while the next is read - and, once the next read failed and the query holds nothing,
 * the last good answer kept for the same question (P19b-20: React Query serves a placeholder to
 * a pending read alone, so a failed read of a new revision left the screen with nothing to draw
 * but its error). Never over a refusal (`refusedRead`): it says something about what was asked,
 * and an answer kept from before it would show an object the project no longer has. A screen
 * that never had an answer shows nothing, and its error alone, as before. Never another
 * question's answer: the canvas's names its project, a component's its file.
 */
export function shown<T>(
  data: T | undefined,
  identity: string,
  before: Kept<T> | null,
  error: unknown,
): T | undefined {
  if (data !== undefined) return data;
  if (refusedRead(error)) return undefined;
  return before !== null && before.identity === identity ? before.data : undefined;
}
