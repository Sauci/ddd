import type { NumberedWrite, Write } from "../lib/announcing";

/**
 * The newest edit or undo this page wrote, by the number the server answered it with
 * (`EditReply.edit`, `UndoReply.edit`): what says whether the revision on screen has caught up
 * with the page's own change, in the moment before the state says it is being analysed. And
 * which edit each of the page's undos put back, under the number the undo took: what tells the
 * values grid that the edit it holds was undone (`valuesShown`), since the undo is made in the
 * Undo strip, not in the grid. And what that newest write was, where it was told, for the
 * heading's line to say (`writtenSince`, 16:I13). One per page, beside the client that notes into
 * it; a test makes its own.
 */
export class OwnEdits {
  #newest = 0;
  /** The newest write, where it was told what it was; a new object at each, as `#undone` is. */
  #last: NumberedWrite | null = null;
  /** A new map at every undo noted, and the same one in between: `useSyncExternalStore` reads
   * a change as a new answer, and would read a new map at every call as a change at every call. */
  #undone: ReadonlyMap<number, number> = new Map();
  readonly #listeners = new Set<() => void>();

  /** Notes an edit written, and what it was (`written`) where told; listeners hear of it only
   * when it is newer than every one before. */
  readonly wrote = (edit: number, written?: Write): void => {
    if (edit <= this.#newest) return;
    this.#newest = edit;
    this.#last = written === undefined ? null : { edit, write: written };
    for (const listener of this.#listeners) listener();
  };

  readonly newest = (): number => this.#newest;

  /** Notes an undo written: `at`, the edit it put back, and `edit`, the number the undo itself
   * took - an edit of its own, noted as `wrote` notes one, with what it put back (`putBack`) where
   * told. Every listener hears of it, whether or not it is the newest: what it put back is news
   * either way. */
  readonly undid = (at: number, edit: number, putBack?: Write): void => {
    this.#undone = new Map([...this.#undone, [at, edit]]);
    if (edit > this.#newest) {
      this.#newest = edit;
      this.#last = putBack === undefined ? null : { edit, write: putBack };
    }
    for (const listener of this.#listeners) listener();
  };

  /** The newest write, where it was told what it was: what the heading's line says. */
  readonly last = (): NumberedWrite | null => this.#last;

  /** Each edit the page's undos put back, to the number the undo took. */
  readonly undone = (): ReadonlyMap<number, number> => this.#undone;

  /** For `useSyncExternalStore`: answers the function that stops the listening. */
  readonly subscribe = (listener: () => void): (() => void) => {
    this.#listeners.add(listener);
    return () => {
      this.#listeners.delete(listener);
    };
  };
}

export const ownEdits = new OwnEdits();
