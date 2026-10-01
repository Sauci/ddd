/**
 * "Updating the findings…" (spec 6): the findings on screen may be about to change - an edit is
 * waiting for its analysis, or an analysis runs. Said quietly - in the project's heading and a
 * component's, and wherever a panel lists findings - as a `status` region: a screen reader hears
 * it arrive without being interrupted.
 */
export function UpdatingNote() {
  return (
    <p className="updating-note" role="status">
      Updating the findings…
    </p>
  );
}
