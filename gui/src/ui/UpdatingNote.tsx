/**
 * "Updating the findings…" where findings are listed - a panel's, the values grid's, a
 * component's - while they may be about to change (spec 6): an edit is waiting for its analysis,
 * or an analysis runs. Plain text, said quietly and read where a reader reaches it; a screen
 * reader is told of the update once, as it starts, by the heading's `UpdatingStatus`.
 */
export function UpdatingNote() {
  return <p className="updating-note">Updating the findings…</p>;
}

/**
 * The heading's "Updating the findings…" (spec 6): the screen's one status region, in the
 * project's heading, a component's and the values grid's. It stays in the heading whether or not
 * anything updates, empty while nothing does, and its words arrive when an update starts - the
 * change a screen reader announces. Last in the heading's row, in whatever room the row has left:
 * cut short rather than wrapped, and one line high either way, its words coming and going never
 * change the heading's height (`ui.css`).
 */
export function UpdatingStatus({ updating }: { updating: boolean }) {
  return (
    <p className="updating-status" role="status">
      {updating ? "Updating the findings…" : ""}
    </p>
  );
}
