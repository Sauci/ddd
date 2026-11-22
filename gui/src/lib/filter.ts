import type { SourceFile, UnitPlace } from "../api/types";
import { countText } from "./numbers";
import { shownPath } from "./paths";
import { baseName } from "./units";

/**
 * The filters of the long tables (16:I14): the Table tab's components, a component's
 * declarations, a unit's places and the Findings tab's findings. A table drawing only the rows in
 * view holds the others nowhere in the document, so the browser's own find cannot reach them; a
 * filter leaves the rows holding what is typed, and a line beside it says how many it leaves of how
 * many. The rows of the first three are the page's, filtered here. The Findings tab's are the
 * server's pages, asked for with the same text (`pageQuery`, lib/findingsWindow.ts).
 *
 * One rule for every table, the Graph's search's and the pickers': a row holds the text where one
 * of its texts contains it, whatever its case. A row the filter leaves is the very row it was, so
 * that it keeps its key, and the table its selection and its focus on it.
 */

/** A row's noun, singular then plural, as the line beside a filter counts the rows it leaves. */
export type Noun = readonly [one: string, many: string];

export const COMPONENTS: Noun = ["component", "components"];
export const DECLARATIONS: Noun = ["declaration", "declarations"];
export const PLACES: Noun = ["place", "places"];
export const FINDINGS: Noun = ["finding", "findings"];

/** What a filter asks for: the text typed without the white space around it, `""` while it holds
 * none. What the Findings tab's filter sends the server, too. */
export function filterText(typed: string): string {
  return typed.trim();
}

/** What a component page's filter holds (16:I14): the text typed into it (`filtering`), on the
 * page of the component it was typed on, and nothing on another's - the page stays drawn from one
 * component to the next, a finding's link or the go-to, and each component starts with no filter
 * of its own. */
export function filterOn(filtering: { file: string; text: string }, file: string): string {
  return filtering.file === file ? filtering.text : "";
}

/** The rows a filter leaves, in their order: each one of whose texts holds what is typed, whatever
 * its case; and every row while nothing is typed - the very list, so that a table handed it draws
 * as it did. */
function filtered<T>(
  rows: readonly T[],
  typed: string,
  texts: (row: T) => readonly string[],
): readonly T[] {
  const wanted = filterText(typed).toLowerCase();
  if (wanted === "") return rows;
  return rows.filter((row) => texts(row).some((text) => text.toLowerCase().includes(wanted)));
}

/** The components the Table tab's filter leaves: each whose name, or file as the table shows it -
 * relative to the project's directory (`shownPath`) - holds the text. A component with no name is
 * named by its path there, and found by it. */
export function componentsShown(
  files: readonly SourceFile[],
  project: string,
  typed: string,
): readonly SourceFile[] {
  return filtered(files, typed, (file) => [file.name ?? file.path, shownPath(project, file.path)]);
}

/** The declarations a component page's filter leaves: each whose name holds the text. Its scope,
 * kind and unit are words most rows share - `in` would find every input - so a name alone is what
 * the filter finds. */
export function declarationsShown<T extends { name: string }>(
  rows: readonly T[],
  typed: string,
): readonly T[] {
  return filtered(rows, typed, (row) => [row.name]);
}

/** The places a unit's filter leaves: each whose name - the variable's, the type's, or the member's
 * as `Type.member` - or file's own name, as the table shows it, holds the text. */
export function placesShown(sites: readonly UnitPlace[], typed: string): readonly UnitPlace[] {
  return filtered(sites, typed, (site) => [site.name, baseName(site.path)]);
}

/** The key a table knows a component by: its Row's id, its file. */
export function componentKey(file: SourceFile): string {
  return file.path;
}

/** The key a component page's table knows a declaration by: its Row's id, the pointer to it. */
export function declarationKey(row: { id: string }): string {
  return row.id;
}

/** The key a unit's table knows a place by: its Row's id, its file and the pointer to its unit. */
export function placeKey(site: UnitPlace): string {
  return `${site.path} ${site.pointer}`;
}

/**
 * How many rows a filtered table puts back at a time, where its filter widened leaves more rows
 * than it draws (16:I14, fix round 1). React Aria builds the rows put back into the table's
 * collection in one commit, which no key typed meanwhile can interrupt: put back at once, a
 * unit's 12,500 places held the key emptying their filter past the 100 ms a key may take. A
 * thousand at a time, each in a commit of its own, the next once the last is drawn.
 */
export const ROWS_PUT_BACK = 1000;

/**
 * The rows a filtered table draws next, on its way to `shown`, the rows its filter leaves: those
 * of `drawn`, the rows it drew last, that the filter still leaves, in their places, and at most
 * `ROWS_PUT_BACK` of those it leaves that `drawn` lacks, the first in `shown`'s order; `shown`
 * itself once it lacks none, the table then drawn whole. Rows the filter no longer leaves are
 * dropped at once: taking rows out of a collection costs little. A row is known by its `key`, the
 * table's id for it, so that the same rows answered anew - a revision landing - put none back.
 */
export function rowsDrawnNext<T>(
  shown: readonly T[],
  drawn: readonly T[],
  key: (row: T) => string,
): readonly T[] {
  if (drawn === shown) return shown;
  const had = new Set(drawn.map(key));
  const next: T[] = [];
  let putBack = 0;
  for (const row of shown) {
    if (had.has(key(row))) {
      next.push(row);
    } else if (putBack < ROWS_PUT_BACK) {
      next.push(row);
      putBack += 1;
    }
  }
  return next.length === shown.length ? shown : next;
}

/** Whether a table's next rows are the very rows it drew, in the same order: a table drawing
 * them again draws nothing new. Rows answered anew are other rows, however alike. */
export function sameRows<T>(drawn: readonly T[], next: readonly T[]): boolean {
  return (
    drawn === next || (drawn.length === next.length && drawn.every((row, at) => row === next[at]))
  );
}

/** Whether a filtered table is drawn: not where the filter leaves none of its rows, which the line
 * beside the filter says - an empty `LongTable` draws a box nothing high, its header cut away. A
 * table with no row of its own, nothing typed, is drawn as it was. */
export function tableDrawn(typed: string, shown: number): boolean {
  return shown > 0 || filterText(typed) === "";
}

/** The line beside a filter: how many rows it leaves of how many the table has - `3 of 1,166
 * components` - or `no component matches`; nothing while nothing is typed. It counts the table's
 * rows, where the line above a table of findings counts the statements they make (decision 14.3),
 * and that line goes on counting the whole project's. */
export function filterLine(
  typed: string,
  shown: number,
  total: number,
  [one, many]: Noun,
): string | null {
  if (filterText(typed) === "") return null;
  if (shown === 0) return `no ${one} matches`;
  return `${countText(shown)} of ${countText(total)} ${total === 1 ? one : many}`;
}
