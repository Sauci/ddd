import type { RefusedBuild, SourceFile } from "../api/types";
import { countText } from "./numbers";
import { shownPath, toldApartAll } from "./paths";
import type { Route } from "./route";
import { baseName, FILES_NAMED } from "./units";

/**
 * What the page says of an open project it cannot show whole (16:I9, Review focus 3): the files
 * that did not load, why the last analysis failed, and the build records this DDD cannot use - one
 * banner under the masthead, on every page of the project, and the sentences beside it that name
 * the same files. A file that did not load is in no index, so every page is drawn from the files
 * that did: the Graph without arrows, the Table without its component, a unit counted over fewer
 * places. Said nowhere but on the Findings tab, a reader saw an empty grid under "no dictionary".
 */

/** Words leading to a page: a part of a sentence drawn as a link. */
export interface Lead {
  text: string;
  to: Route;
}

/** A part of a sentence the page draws: words, or words leading to a page. */
export type Part = string | Lead;

/** Each file of `files` that did not load, as every sentence of the page names it - the banner,
 * the Graph's, a removal's and the go-to's: by its own name, and two of one name in different
 * folders by as much of their paths as tells them apart (`toldApartAll`) among those that did not
 * load - as the server's refusals name them (`ddd.gui.api._unread`), so that one file is one name
 * on the page and in a refusal. In the state's order, by path. */
export function unloadedNames(files: readonly Pick<SourceFile, "path" | "loaded">[]): string[] {
  return toldApartAll(files.filter((file) => !file.loaded).map((file) => file.path));
}

/** The parts naming `items`, as every sentence of this interface lists names - "A", "A and B",
 * "A, B and C" - and past one more than `FILES_NAMED`, the first `FILES_NAMED` and how many more
 * there are, as a plan's consequence counts its files (lib/units.ts): named one by one, every file
 * of a project failing at once - its description format moved on - would run to a wall of names on
 * every page. */
function listedParts<T>(
  items: readonly T[],
  named: (item: T) => Part,
  more: (count: number) => Part,
): Part[] {
  const shown =
    items.length <= FILES_NAMED + 1
      ? items.map(named)
      : [...items.slice(0, FILES_NAMED).map(named), more(items.length - FILES_NAMED)];
  return shown.flatMap((part, at) =>
    at === 0 ? [part] : [at === shown.length - 1 ? " and " : ", ", part],
  );
}

/** `names`, as a sentence lists the files that did not load: each up to four, and past four the
 * first three and how many more (`listedParts`). */
export function namedFiles(names: readonly string[]): string {
  return listedParts(
    names,
    (name) => name,
    (count) => `${countText(count)} more`,
  ).join("");
}

/** The banner under the masthead: an error where the last analysis failed - nothing the pages
 * show is of the files as they stand - and a warning otherwise, and its lines, each a sentence. */
export interface LoadBanner {
  tone: "error" | "warning";
  lines: readonly (readonly Part[])[];
}

/** How the terminal ends its line of a build record this DDD cannot use, as `ddd lsp` logs one
 * (`Session._tell_refused`, gui/session.py): what the banner says after the record's reason. */
export const RECORD_IGNORED = "this record is ignored, so its severities apply to no analysis";

/**
 * The banner under the masthead of every page of the open project, or `null` where it has nothing
 * to say - every file loaded, no analysis failed, no record refused, and before the first state.
 * `project` is the project the state followed is of, and `state` its newest analysed revision,
 * `null` before the first; `failed` and `refused` are the newest state's, analysed or not
 * (`useProjectState`), so that a first analysis that failed is said too.
 *
 * Its lines, in order:
 * - why the last analysis failed, and that the next change of a file it reads asks again, as the
 *   poll does (B11-17): over the last analysis that finished, which every page then shows, or
 *   alone where none has;
 * - the project's own description, where it did not load: nothing it includes is read, so no page
 *   has a file of the project to draw;
 * - the other files that did not load, each leading to its finding (`findingsOf`), past four the
 *   rest counted and led to the Files tab, whose rows say of each that it did not load. A file that
 *   does not load stops every check of the project (`checksWaiting`), and the pages show what the
 *   files that loaded declare;
 * - each build record this DDD cannot use, by its path from the project's directory, as the Table
 *   tab's File column names a file (`shownPath`), with its reason, in the terminal's words.
 */
export function loadBanner(
  project: string | null,
  state: { files: readonly SourceFile[] } | null,
  failed: string | null,
  refused: readonly RefusedBuild[],
): LoadBanner | null {
  if (project === null) return null;
  const lines: Part[][] = [];
  if (failed !== null) {
    lines.push([
      state === null
        ? `Analysing the project failed: ${failed}. ddd gui analyses it again when a file it reads changes.`
        : `Analysing the project failed: ${failed}. The pages show the last analysis that finished, and ddd gui analyses the project again when a file it reads changes.`,
    ]);
  }
  // Named as `unloadedNames` names them, told apart among all of them; the project's own
  // description, where it is one of them, in a line of its own.
  const unloaded = (state?.files ?? []).filter((file) => !file.loaded);
  const names = toldApartAll(unloaded.map((file) => file.path));
  const described = unloaded.map((file) => file.path === project);
  for (const name of names.filter((_, at) => described[at])) {
    lines.push([
      findingsOf(name),
      ` did not load, so ${checksWaiting(1)}, and no file it includes is read.`,
    ]);
  }
  const others = names.filter((_, at) => !described[at]);
  if (others.length > 0) {
    lines.push([
      ...listedParts(others, findingsOf, (count) => ({
        text: `${countText(count)} more`,
        to: { page: "project", view: "files" },
      })),
      ` did not load, so ${checksWaiting(others.length)}, and the pages show what the files that loaded declare.`,
    ]);
  }
  for (const entry of refused) {
    lines.push([`${shownPath(project, entry.record)}: ${entry.reason}; ${RECORD_IGNORED}.`]);
  }
  if (lines.length === 0) return null;
  return { tone: failed === null ? "warning" : "error", lines };
}

/** What `count` files that did not load leave of the project's checks: none runs until every file
 * loads. An analysis whose read reported an error goes no further (`_run`, lsp/diagnostics.py), as
 * `ddd check` stops at the read, so the counts every page draws beside the banner are the read's
 * alone - no check said a file that loaded has nothing to fix. */
function checksWaiting(count: number): string {
  return `the project's checks wait until ${count === 1 ? "it does" : "they do"}`;
}

/** A file that did not load, by its name (`unloadedNames`), leading to its finding: the Findings
 * tab, asked for the findings that hold the file's own name - its own, the one saying why it did
 * not load among its errors, and one filed at the entry naming a file that is not there, whose
 * words name it. By the file's own name, the last part of the one telling two apart, which a
 * finding's file name does not hold (`_holds`, gui/api.py): two of one name lead to the findings
 * of both. */
function findingsOf(name: string): Lead {
  return { text: name, to: { page: "project", view: "findings", text: baseName(name) } };
}
