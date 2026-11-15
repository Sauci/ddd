import type { PlanReply, ValuesReply } from "../api/types";
import { type CommaMeaning, sameCount } from "./numbers";
import {
  cellAt,
  cellRead,
  cellSentence,
  commaOf,
  elementLabel,
  pasteSentence,
  physicalReading,
  rawText,
  statedValue,
  type TypedCell,
  typedRaw,
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

/** Why a cell refuses what was typed into it, or `null`: text that is no number it takes
 * (`cellRead`), a comma that could be either among it - `ambiguous`, which a choice of what it means
 * answers - or a number typed into a cell past the end of the object's shape, which has no element
 * to set, in the words the server refuses one with. The grid draws the shape's own columns and
 * rows, so a cell past it is one typed while the shape was larger: held through an analysis that
 * shrank it. An emptied cell is nothing typed yet, wherever it is. `typed` is every cell typed
 * into the grid, whose commas are read together (`commaOf`). */
function refusalOf(
  cell: TypedCell,
  typed: readonly TypedCell[],
  reply: ValuesReply,
): { refusal: string; ambiguous: boolean } | null {
  const read = cellRead(cell.typed, reply, cell.physical, commaOf(typed, cell));
  if (read === null) return null;
  if ("refusal" in read) return read;
  const [rows, columns] = wanted(reply);
  if (cell.row < rows && cell.column < columns) return null;
  return {
    refusal: `'${cellAt(cell.row, cell.column, reply.shape)}' is past the end of this object`,
    ambiguous: false,
  };
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
 * for them all - with the text of the first refused for a comma that could be either, which the
 * offer asks the meaning of - or the elements they set: none, where every cell is empty or typed
 * back to its file's value. */
export type TypedOffer =
  | { refusal: string; changes: null; ambiguous: string | null }
  | { refusal: null; changes: CellChange[]; ambiguous: null };

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
 * the value its file holds there - a cell typed back sets nothing, and drops out of the plan. A
 * `float32`'s value is the float32 its file's number rounds to (`sameCount`): typed back in
 * fewer digits than a file spelling it at double precision, it is the same value (fix round 1,
 * M4).
 */
export function typedOffer(cells: readonly TypedCell[], reply: ValuesReply): TypedOffer {
  const refused = cells.flatMap((cell) => {
    const refusal = refusalOf(cell, cells, reply);
    return refusal === null ? [] : [{ cell, ...refusal }];
  });
  const [first] = refused;
  if (first !== undefined) {
    const ambiguous = refused.find((entry) => entry.ambiguous)?.cell.typed ?? null;
    const label = (cell: TypedCell) => elementLabel(cell.row, cell.column, reply.shape);
    if (cells.length === 1) return { refusal: first.refusal, changes: null, ambiguous };
    if (refused.length === 1) {
      return {
        refusal: `${label(first.cell)} of '${reply.name}' is refused: ${first.refusal}`,
        changes: null,
        ambiguous,
      };
    }
    const clauses = refused.map(({ cell, refusal }) => `${label(cell)} because ${refusal}`);
    return {
      refusal: `${refused.length} elements of '${reply.name}' are refused: ${listed(clauses)}`,
      changes: null,
      ambiguous,
    };
  }
  const changes = cells.flatMap((cell) => {
    const raw = typedRaw(cell.typed, reply, cell.physical, commaOf(cells, cell));
    if (raw === null) return [];
    const stated = statedValue(reply, cell.row, cell.column);
    if (stated !== undefined && sameCount(raw, stated, reply.datatype)) return [];
    return [{ row: cell.row, column: cell.column, raw }];
  });
  return { refusal: null, changes, ambiguous: null };
}

/** The cells typed into, each whose comma could be a decimal point or a thousands separator said
 * to be `meaning` - the one press that answers what the offer asked of them; every other cell as
 * it was. */
export function withComma(
  cells: readonly TypedCell[],
  reply: ValuesReply,
  meaning: CommaMeaning,
): TypedCell[] {
  return cells.map((cell) => {
    const read = cellRead(cell.typed, reply, cell.physical, commaOf(cells, cell));
    return read !== null && "ambiguous" in read && read.ambiguous
      ? { ...cell, comma: meaning }
      : cell;
  });
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
    const value = physical ? physicalReading(raw, reply) : rawText(raw, reply.datatype);
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

/** One element a plan is asked to set: where it stands in the grid, its pointer's suffix - `[2]`,
 * or `[1][3]` - and the raw count it is set to. */
export interface PlannedCell {
  row: number;
  column: number;
  at: string;
  raw: number;
}

/** The plan asked for what the typed cells set: one element's own (`GET /api/value-plan`), or
 * several elements', each set where it stands (`GET /api/cells-plan`) - only the cells typed
 * written, never a table of the values the page holds, which spells the numbers nobody typed as
 * the page reads them and outgrows one request for a large block. */
export type TypedPlan = { cell: PlannedCell } | { cells: PlannedCell[] };

/** The plan `changes` asks for, or `null` where there is nothing to set. */
export function typedPlan(reply: ValuesReply, changes: readonly CellChange[]): TypedPlan | null {
  const cells = changes.map(({ row, column, raw }) => ({
    row,
    column,
    at: cellAt(row, column, reply.shape),
    raw,
  }));
  const [only] = cells;
  if (only === undefined) return null;
  return cells.length === 1 ? { cell: only } : { cells };
}

/** The text whose comma the offer asks the meaning of, or `null` where it asks none: the typed
 * cells' (`offer`), or, where no cell is typed into - `offer` null - a pasted block's own
 * (`Pasted.ambiguous`). */
export function commaAsked(offer: TypedOffer | null, pasted: string | null): string | null {
  return offer === null ? pasted : offer.ambiguous;
}

/** The plan as the offer draws it: none for a plan that changes nothing - a table pasted over the
 * values the file writes, spelled as it spells them - which the server answers with no file to
 * change (15:M4): an Apply that wrote the file as it was would only have left an undo behind. */
export function planOffered(plan: PlanReply | null): PlanReply | null {
  return plan !== null && plan.changes.length > 0 ? plan : null;
}

/** What the offer's region is called: the one cell or the cells typed into, or a pasted table's
 * values where no cell is. */
export function offerName(typed: number): string {
  if (typed === 0) return "Replace the values";
  return typed === 1 ? "Set the cell" : "Set the cells";
}
