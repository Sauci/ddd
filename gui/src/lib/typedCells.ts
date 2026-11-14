import type { ValuesReply } from "../api/types";
import {
  cellAt,
  cellSentence,
  elementLabel,
  pasteSentence,
  physicalReading,
  type TypedCell,
  typedRaw,
  typedRefusal,
  wanted,
} from "./objectValues";

/** One element the typed cells set: where it is, and the raw count it is set to. */
export interface CellChange {
  row: number;
  column: number;
  raw: number;
}

/** The cells typed into, with `cell` in its place: its earlier text replaced where it was typed
 * into before, else added - in the grid's own order, row by row, whatever order they were typed
 * in. The grid holds every cell typed into until an Apply writes them or a pasted table takes
 * their place, each showing what was typed into it (decision 16.2): a second cell typed used to
 * put the first back as it was, with nothing said. */
export function withTyped(cells: readonly TypedCell[], cell: TypedCell): TypedCell[] {
  const others = cells.filter((held) => held.row !== cell.row || held.column !== cell.column);
  return [...others, cell].sort((a, b) => a.row - b.row || a.column - b.column);
}

/** The value the file holds at a cell, or `undefined` where it holds none there: an object that
 * states nothing, whose zeros are the startup code's, or a row too short to reach the cell. */
function fileValue(reply: ValuesReply, row: number, column: number): number | undefined {
  return reply.stated === "none" ? undefined : reply.rows[row]?.[column];
}

/** Why a cell refuses what was typed into it, or `null`: text that is no number it takes
 * (`typedRefusal`), or a number typed into a cell past the end of the object's shape, which has
 * no element to set - one an axis's breakpoints draw beyond it - in the words the server refuses
 * one with. An emptied cell is nothing typed yet, wherever it is. */
function refusalOf(cell: TypedCell, reply: ValuesReply): string | null {
  const refusal = typedRefusal(cell.typed, reply);
  if (refusal !== null || cell.typed.trim() === "") return refusal;
  const [rows, columns] = wanted(reply);
  if (cell.row < rows && cell.column < columns) return null;
  return `'${cellAt(cell.row, cell.column, reply.shape)}' is past the end of this object`;
}

/** The most cells a sentence names one by one before it counts the rest, as the server names the
 * elements of a table it refuses (`_all_of_them`, object_values.py): the sentence stays one a
 * reader takes in, held at the window's foot over the grid. */
const NAMED = 5;

/** `clauses` as one list, the first five of them and then how many more, each parted from the
 * next by a semicolon: a map's element is named with a comma of its own. */
function listed(clauses: readonly string[]): string {
  const named = clauses.slice(0, NAMED);
  if (clauses.length > NAMED) named.push(`and ${clauses.length - NAMED} more`);
  return named.join("; ");
}

/** What the cells typed into offer: the sentence a cell is refused with, which withholds Apply
 * for them all, or the elements they set - none, where every cell is empty or typed back to its
 * file's value. */
export type TypedOffer =
  | { refusal: string; changes: null }
  | { refusal: null; changes: CellChange[] };

/**
 * What `cells`, typed into the grid of `reply`, offer: together they make one plan, one Apply and
 * one entry in the undo stack (decision 16.2).
 *
 * A refused cell withholds the plan of every other, since one Apply writes them all: one cell
 * alone is refused in its own sentence, as it always was, and among several the cell refused is
 * named, as the server names the elements of a table it refuses.
 *
 * Otherwise each cell sets the raw count its text comes to, read in the reading it was typed in:
 * none where it is empty, which is a cell nothing has been typed into yet, or where the count is
 * the value its file holds there - a cell typed back sets nothing, and drops out of the plan.
 */
export function typedOffer(cells: readonly TypedCell[], reply: ValuesReply): TypedOffer {
  const refused = cells.flatMap((cell) => {
    const refusal = refusalOf(cell, reply);
    return refusal === null ? [] : [{ cell, refusal }];
  });
  const [first] = refused;
  if (first !== undefined) {
    const label = (cell: TypedCell) => elementLabel(cell.row, cell.column, reply.shape);
    if (cells.length === 1) return { refusal: first.refusal, changes: null };
    if (refused.length === 1) {
      return {
        refusal: `${label(first.cell)} of '${reply.name}' is refused: ${first.refusal}`,
        changes: null,
      };
    }
    const clauses = refused.map(({ cell, refusal }) => `${label(cell)} because ${refusal}`);
    return {
      refusal: `${refused.length} elements of '${reply.name}' are refused: ${listed(clauses)}`,
      changes: null,
    };
  }
  const changes = cells.flatMap((cell) => {
    const raw = typedRaw(cell.typed, reply, cell.physical);
    if (raw === null || raw === fileValue(reply, cell.row, cell.column)) return [];
    return [{ row: cell.row, column: cell.column, raw }];
  });
  return { refusal: null, changes };
}

/** The sentence above the preview of what the typed cells set: one cell's own (`cellSentence`),
 * or the elements several set, each with what it is set to, in the reading the grid is in. Asked
 * only of at least one change. */
export function changesSentence(
  reply: ValuesReply,
  changes: readonly CellChange[],
  physical: boolean,
): string {
  const [only] = changes;
  if (only !== undefined && changes.length === 1) {
    return cellSentence(reply, only.row, only.column, only.raw, physical);
  }
  const clauses = changes.map(({ row, column, raw }) => {
    const value = physical ? physicalReading(raw, reply) : String(raw);
    return `${elementLabel(row, column, reply.shape)} to ${value}`;
  });
  return `Sets ${changes.length} elements of ${reply.name}: ${listed(clauses)}`;
}

/** The sentence above the preview, whichever offer owns it: what the typed cells set
 * (`changesSentence`), or, where no cell is typed into - `offer` null - a pasted table's
 * (`pasteSentence`). `null` while the typed cells set nothing or one of them is refused: no plan
 * is asked for them then. */
export function offerSentence(
  reply: ValuesReply,
  offer: TypedOffer | null,
  physical: boolean,
): string | null {
  if (offer === null) return pasteSentence(reply);
  if (offer.changes === null || offer.changes.length === 0) return null;
  return changesSentence(reply, offer.changes, physical);
}

/** The plan asked for what the typed cells set: one element's own - a `set` at its pointer, one
 * line of the file (`GET /api/value-plan`) - or, for several, the whole table they make of the
 * values the grid shows, as a pasted table's (`GET /api/values-plan`). */
export type TypedPlan =
  | { cell: { row: number; column: number }; at: string; raw: number }
  | { rows: number[][] };

/** The plan `changes` asks for, or `null` where there is nothing to set. The table holds the
 * object's own shape: a cell its row does not reach is the zero the startup code makes, which is
 * what one cell set there writes too, and a row longer than the shape is cut to it, as a pasted
 * table is. */
export function typedPlan(reply: ValuesReply, changes: readonly CellChange[]): TypedPlan | null {
  const [only] = changes;
  if (only === undefined) return null;
  if (changes.length === 1) {
    const { row, column, raw } = only;
    return { cell: { row, column }, at: cellAt(row, column, reply.shape), raw };
  }
  const set = new Map(changes.map(({ row, column, raw }) => [`${row} ${column}`, raw]));
  const [rows, columns] = wanted(reply);
  return {
    rows: Array.from({ length: rows }, (_, row) =>
      Array.from(
        { length: columns },
        (_, column) => set.get(`${row} ${column}`) ?? reply.rows[row]?.[column] ?? 0,
      ),
    ),
  };
}

/** What the offer's region is called: the one cell or the cells typed into, or a pasted table's
 * values where no cell is. */
export function offerName(typed: number): string {
  if (typed === 0) return "Replace the values";
  return typed === 1 ? "Set the cell" : "Set the cells";
}
