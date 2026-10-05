/**
 * "Updating the findings…" where findings are listed - a panel's, the values grid's, a
 * component's - while they may be about to change (spec 6): an edit is waiting for its analysis,
 * or an analysis runs. Plain text, said quietly and read where a reader reaches it; a screen
 * reader is told of the update once, as it starts, by the heading's `UpdatingStatus`. Its line is
 * held whether or not anything updates, empty while nothing does (Ruling T12b-1, as Ruling T8-3
 * holds the heading's), and its words never wrap onto a second (`ui.css`): their coming and going
 * never move what is below them - in a panel, an offer and its Apply under a reader's pointer.
 */
export function UpdatingNote({ updating }: { updating: boolean }) {
  return <p className="updating-note">{updating ? "Updating the findings…" : ""}</p>;
}

/**
 * The heading's "Updating the findings…" (spec 6): of a screen's status regions, the one that
 * says its findings are updating - in the project's heading, a component's and the values grid's.
 * It stays in the heading whether or not anything updates, empty while nothing does, and its words
 * arrive when an update starts - the change a screen reader announces. Last in the heading's row,
 * it needs no room of its own and takes what its line has left, cut short rather than wrapped:
 * where none is left - beside the open Undo strip's own line - it shows nothing, and is still
 * heard. Its words coming and going never change the heading's height (`ui.css`).
 */
export function UpdatingStatus({ updating }: { updating: boolean }) {
  return (
    <p className="updating-status" role="status">
      {updating ? "Updating the findings…" : ""}
    </p>
  );
}
