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
  /** The first revision the page saw include the hold's last edit - the Apply, or the undo of it
   * once there is one - and which edit that was; `null` until one has. An answer of that revision
   * or a later one includes what the hold says, and from then on is shown in its place: the hold
   * has ended, and an answer kept on screen at a later landing is never covered up again. */
  landed: { edit: number; revision: number } | null;
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
  return { edit, before, after: { ...before, rows, stated: "array" }, landed: null };
}

/** The hold's own last edit: the undo of its Apply, once one is noted in `undone`, else the
 * Apply. */
function lastOf(hold: ValuesHold, undone: ReadonlyMap<number, number>): number {
  return undone.get(hold.edit) ?? hold.edit;
}

/** The hold as it stands once `state` has come: stamped with the state's revision the first time
 * it includes the hold's last edit, and otherwise the very same hold, so that the page can tell
 * nothing changed. An undo of the Apply noted after the stamp is the hold's last edit from then
 * on, and the hold waits for the first revision including it. */
export function holdAfter(
  hold: ValuesHold | null,
  undone: ReadonlyMap<number, number>,
  state: Pick<State, "revision" | "edits">,
): ValuesHold | null {
  if (hold === null) return null;
  const last = lastOf(hold, undone);
  if (state.edits < last || hold.landed?.edit === last) return hold;
  return { ...hold, landed: { edit: last, revision: state.revision } };
}

/** Whether an Apply may be planned over `shown`, the values the grid shows: only once they are the
 * answer of the revision the page holds, or of a newer one. Not over an older revision's answer,
 * kept on screen while the page's own is asked for, nor over what the grid holds of an Apply the
 * page's revision does not include yet: an Apply planned over either would hold those values as
 * its values from before. */
export function appliesOver(shown: ValuesReply, state: Pick<State, "revision">): boolean {
  return shown.revision >= state.revision;
}

/**
 * Which values the grid shows: what its own Apply wrote, what was there before it, or the
 * server's answer.
 *
 * `GET /api/values` answers from what the last analysis read, and an edit is answered once
 * written, before its analysis (spec 5): for one analysis after an Apply the server still answers
 * the values from before it, as though the Apply had failed. So the grid shows what the Apply
 * wrote until an answer of a revision including it has come: of the first revision the page saw
 * include it (`landed`, which `holdAfter` stamps), or, the moment that revision arrives, of the
 * state's own. An older revision's answer, kept on screen while the query keyed by the new one
 * is asked, is not taken in its place. Once an answer including the Apply has been, the hold has
 * ended, and the answers of every later landing - kept ones too - are shown as they come. An undo
 * of that Apply, made in the Undo strip and noted in `undone` (the edit it put back, to the number
 * the undo took), shows the values from before the Apply the same way, until an answer including
 * the undo has come.
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
  const last = lastOf(hold, undone);
  for (const [at, edit] of undone) {
    if (at !== hold.edit && edit > last) return served;
  }
  const landed =
    hold.landed?.edit === last ? hold.landed.revision : state.edits >= last ? state.revision : null;
  if (landed !== null && served.revision >= landed) return served;
  return last === hold.edit ? hold.after : hold.before;
}
