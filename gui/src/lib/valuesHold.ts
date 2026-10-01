import type { State, ValuesReply } from "../api/types";

/** What one Apply in the grid wrote: one cell's raw count, or a whole pasted table's, row by row
 * as `ValuesReply.rows` holds them. */
export type Written = { cell: { row: number; column: number }; raw: number } | { rows: number[][] };

/** What an Apply would write: a pasted table's rows, where one was pasted; else the cell being
 * typed into and the raw count its text comes to; `null` while neither makes anything to write. */
export function writtenBy(
  pasted: number[][] | null,
  editing: { row: number; column: number } | null,
  raw: number | null,
): Written | null {
  if (pasted !== null) return { rows: pasted };
  if (editing === null || raw === null) return null;
  return { cell: { row: editing.row, column: editing.column }, raw };
}

/** What the grid holds of one Apply of its own: the number its edit was answered with, the
 * values the grid showed when it was made, and the values it wrote. */
export interface ValuesHold {
  edit: number;
  before: ValuesReply;
  after: ValuesReply;
}

/** The hold of an Apply answered as edit `edit`, made over `before` - what the grid showed -
 * writing `written`. The values written are an array in the file from then on, whatever it stated
 * before: `ddd.object_values.set_cell` writes the whole `init` where the file held one value for
 * every cell, or none. */
export function holdOf(edit: number, before: ValuesReply, written: Written): ValuesHold {
  const rows =
    "rows" in written
      ? written.rows
      : before.rows.map((cells, row) =>
          row === written.cell.row
            ? cells.map((value, column) => (column === written.cell.column ? written.raw : value))
            : cells,
        );
  return { edit, before, after: { ...before, rows, stated: "array" } };
}

/**
 * Which values the grid shows: what its own Apply wrote, what was there before it, or the
 * server's answer.
 *
 * `GET /api/values` answers from what the last analysis read, and an edit is answered once
 * written, before its analysis (spec 5): for one analysis after an Apply the server still answers
 * the values from before it, as though the Apply had failed. So the grid shows what the Apply
 * wrote until a revision including it - the state's `edits` at its number or past it - has
 * answered; the answer on screen may be an older revision's while the query keyed by the new one
 * is asked, and is not taken until it is that revision's or newer. An undo of that Apply, made in
 * the Undo strip and noted in `undone` (the edit it put back, to the number the undo took), shows
 * the values from before the Apply until a revision including the undo has answered.
 *
 * Any other undo the page made after the hold's last edit - of an edit the grid never held, or
 * no longer holds because a later Apply replaced it - leaves nothing the hold can say of the
 * file, and the grid shows the server's answer, under "Updating the findings…", until that undo's
 * analysis lands: for one analysis, the values it shows may be older than the file's. That is
 * accepted.
 */
export function valuesShown(
  hold: ValuesHold | null,
  undone: ReadonlyMap<number, number>,
  state: Pick<State, "revision" | "edits">,
  served: ValuesReply,
): ValuesReply {
  if (hold === null) return served;
  const undoneAs = undone.get(hold.edit);
  // The hold's own last edit: the undo of its Apply, once there is one, else the Apply.
  const last = undoneAs ?? hold.edit;
  for (const [at, edit] of undone) {
    if (at !== hold.edit && edit > last) return served;
  }
  if (state.edits >= last && served.revision >= state.revision) return served;
  return undoneAs === undefined ? hold.after : hold.before;
}
