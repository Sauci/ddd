import { ApiError } from "../api/client";

/** What a panel refused, and the revision it was refused at. */
export interface Refused {
  text: string;
  revision: number | undefined;
}

/**
 * The refusal a panel shows: the one stored, until the analysis has moved past the revision it
 * was refused at.
 *
 * A stale refusal is the reason this exists. The server refuses an edit whose file changed on
 * disk, and the panel says the files are shown as they are - but the analysis that noticed the
 * change has not finished yet, so everything on screen, the fingerprints included, is still the
 * revision that was refused. Choosing again straight away sends those same fingerprints and is
 * refused a second time. Holding the sentence until the next revision arrives makes it true:
 * the watcher answers within a second, and what comes back is a panel that can be applied.
 */
export function shownRefusal(stored: Refused | null, revision: number | undefined): string | null {
  if (stored === null) return null;
  return stored.revision === revision ? stored.text : null;
}

/** Whether an Apply was refused because a file changed on disk since its plan was made - the one
 * refusal a panel holds until the analysis moves on (`shownRefusal`), where every other is cleared
 * by the reader's next choice. The server's own code for it, `ddd.editing.STALE`: never a word of
 * the sentence, which the server may reword. */
export function isStale(error: Error): boolean {
  return error instanceof ApiError && error.code === "stale";
}

/**
 * The one refusal an action shows, of the three it can have at once: an Apply refused as stale,
 * while the revision it was refused at stands; else an Apply refused for another reason; else why
 * its plan was refused when asked for, in the server's own words.
 *
 * An Apply's comes first because it is the newer answer: its plan was shown and could be applied,
 * so the plan itself was not refused when the Apply was. A stale Apply's gives way to the plan's
 * own refusal once the analysis has moved past it - the plan is asked for again at the new
 * revision, and what it answers then is what is true.
 */
export function refusalShown(
  stale: Refused | null,
  refused: string | null,
  asked: Error | null,
  revision: number | undefined,
): string | null {
  return shownRefusal(stale, revision) ?? refused ?? asked?.message ?? null;
}
