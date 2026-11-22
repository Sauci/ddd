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
