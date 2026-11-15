import type { ValuesReply } from "../api/types";
import { cellId } from "./gridCells";
import { cellText, type TypedCell, wanted } from "./objectValues";

/** What the grid's fields show, apart from the cells typed into: the text of every cell the shape
 * has, row by row, as `cellText` reads it of a cell nothing is typed into. */
type Texts = readonly (readonly string[])[];

/** What a reply shows with nothing typed into it, in either reading, and the widths of its
 * columns: worked out once for as long as the page holds the reply, where the grid used to read
 * every cell of it again on every keystroke - twice, once for the field and once for its column's
 * width - and, past the readings the page keeps (`heldReadings`), read each float anew (15:M8). */
interface Shown {
  texts: Texts;
  /** By how many columns `chars` was counted. */
  columns: number;
  chars: readonly number[];
}

const SHOWN = new WeakMap<ValuesReply, { raw?: Shown; physical?: Shown }>();

function shownOf(reply: ValuesReply, physical: boolean, columns: number): Shown {
  const kept = SHOWN.get(reply) ?? {};
  SHOWN.set(reply, kept);
  const key = physical ? "physical" : "raw";
  const known = kept[key];
  if (known?.columns === columns) return known;
  const [rows, width] = wanted(reply);
  const texts =
    known?.texts ??
    Array.from({ length: rows }, (_, row) =>
      Array.from({ length: width }, (_, column) => cellText(reply, [], row, column, physical)),
    );
  const shown = {
    texts,
    columns,
    chars: Array.from({ length: columns }, (_, column) => widest(new Map(), texts, column, rows)),
  };
  kept[key] = shown;
  return shown;
}

/** The text of the field at `row` and `column`: what was typed into it (`held`), else what the
 * reply shows there, else nothing - a cell past the shape, which has no field. */
function fieldText(
  held: ReadonlyMap<string, string>,
  texts: Texts,
  row: number,
  column: number,
): string {
  return held.get(cellId(row, column)) ?? texts[row]?.[column] ?? "";
}

/** The longest text in `column` over the first `rows` rows, `held`'s text for a cell typed into
 * in place of the one the reply shows there. */
function widest(
  held: ReadonlyMap<string, string>,
  texts: Texts,
  column: number,
  rows: number,
): number {
  let longest = 0;
  for (let row = 0; row < rows; row += 1) {
    longest = Math.max(longest, fieldText(held, texts, row, column).length);
  }
  return longest;
}

/** Everything the fields of one grid show: the text of each, and how many characters wide each
 * column is drawn. */
export interface GridTexts {
  /** The text of the cells typed into, by `cellId`: what was typed, in the reading it was typed
   * in, or the count its text comes to in the other (`cellText`). */
  held: ReadonlyMap<string, string>;
  /** The text of every cell the reply shows nothing typed into. */
  texts: Texts;
  /** How many characters wide each of `columns` is: the longest text its fields show, down every
   * row the object's shape has, the numbers held and what is typed alike. A field cut short hides
   * the end of its number with no sign of it, and under right aligned digits a cut number reads as
   * a smaller one - 4000000000 as 400000. Column by column, so that one long number widens its
   * own column and leaves the others as narrow as theirs; counted in characters, which the grid's
   * monospace sets one `ch` apiece. */
  chars: readonly number[];
}

/**
 * What the grid shows of `reply` in the reading asked for, with `typed` typed into it - worked out
 * from what the reply shows (`shownOf`, once) and from the cells typed into alone: a keystroke
 * costs the cells typed into and the columns they are in, not every cell of the grid (15:M8).
 */
export function gridTexts(
  reply: ValuesReply,
  typed: readonly TypedCell[],
  physical: boolean,
  columns: number,
): GridTexts {
  const shown = shownOf(reply, physical, columns);
  const held = new Map(
    typed.map((cell) => [
      cellId(cell.row, cell.column),
      cellText(reply, typed, cell.row, cell.column, physical),
    ]),
  );
  const rows = wanted(reply)[0];
  const typedColumns = new Set(typed.map((cell) => cell.column));
  const chars =
    typedColumns.size === 0
      ? shown.chars
      : shown.chars.map((own, column) =>
          typedColumns.has(column) ? widest(held, shown.texts, column, rows) : own,
        );
  return { held, texts: shown.texts, chars };
}

/** The text of the field at `row` and `column`. */
export function textAt(shown: GridTexts, row: number, column: number): string {
  return fieldText(shown.held, shown.texts, row, column);
}

/**
 * What the fields of a grid read their text and their width from, so that a keystroke draws the
 * field typed into and the columns it changes the width of, and no other: each field subscribes to
 * its own text and its own column's width, and the view hands over what the grid now shows
 * (`update`) once drawn. A field asks for `textAt` and `charsAt`, which are text and a number,
 * equal for a field nothing changed, and so draws nothing again.
 */
export class GridStore {
  private shown: GridTexts;
  private readonly listeners = new Set<() => void>();

  constructor(shown: GridTexts) {
    this.shown = shown;
  }

  /** Takes what the grid now shows, and tells every field if it is not what it showed. */
  update(shown: GridTexts): void {
    if (shown === this.shown) return;
    this.shown = shown;
    for (const listener of [...this.listeners]) listener();
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  textAt(row: number, column: number): string {
    return textAt(this.shown, row, column);
  }

  charsAt(column: number): number {
    return this.shown.chars[column] ?? 0;
  }
}
