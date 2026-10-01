/**
 * The newest edit or undo this page wrote, by the number the server answered it with
 * (`EditReply.edit`, `UndoReply.edit`): what says whether the revision on screen has caught up
 * with the page's own change, in the moment before the state says it is being analysed.
 * One per page, beside the client that notes into it; a test makes its own.
 */
export class OwnEdits {
  #newest = 0;
  readonly #listeners = new Set<() => void>();

  /** Notes an edit written; listeners hear of it only when it is newer than every one before. */
  readonly wrote = (edit: number): void => {
    if (edit <= this.#newest) return;
    this.#newest = edit;
    for (const listener of this.#listeners) listener();
  };

  readonly newest = (): number => this.#newest;

  /** For `useSyncExternalStore`: answers the function that stops the listening. */
  readonly subscribe = (listener: () => void): (() => void) => {
    this.#listeners.add(listener);
    return () => {
      this.#listeners.delete(listener);
    };
  };
}

export const ownEdits = new OwnEdits();
