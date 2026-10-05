/**
 * The newest edit or undo this page wrote, by the number the server answered it with
 * (`EditReply.edit`, `UndoReply.edit`): what says whether the revision on screen has caught up
 * with the page's own change, in the moment before the state says it is being analysed. And
 * which edit each of the page's undos put back, under the number the undo took: what tells the
 * values grid that the edit it holds was undone (`valuesShown`), since the undo is made in the
 * Undo strip, not in the grid. One per page, beside the client that notes into it; a test makes
 * its own.
 */
export class OwnEdits {
  #newest = 0;
  /** A new map at every undo noted, and the same one in between: `useSyncExternalStore` reads
   * a change as a new answer, and would read a new map at every call as a change at every call. */
  #undone: ReadonlyMap<number, number> = new Map();
  readonly #listeners = new Set<() => void>();

  /** Notes an edit written; listeners hear of it only when it is newer than every one before. */
  readonly wrote = (edit: number): void => {
    if (edit <= this.#newest) return;
    this.#newest = edit;
    for (const listener of this.#listeners) listener();
  };

  readonly newest = (): number => this.#newest;

  /** Notes an undo written: `at`, the edit it put back, and `edit`, the number the undo itself
   * took - an edit of its own, noted as `wrote` notes one. Every listener hears of it, whether or
   * not it is the newest: what it put back is news either way. */
  readonly undid = (at: number, edit: number): void => {
    this.#undone = new Map([...this.#undone, [at, edit]]);
    if (edit > this.#newest) this.#newest = edit;
    for (const listener of this.#listeners) listener();
  };

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
