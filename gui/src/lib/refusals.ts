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
