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
 * (`useProjectState`), so that a first analysis that failed is said too. `stopped` is whether
 * ddd gui has stopped answering: no line then says what ddd gui will do, only what the last state
 * the page read holds, under the masthead's "ddd gui has stopped".
 *
 * Its lines, in order:
 * - why the last analysis failed, and, while ddd gui runs, that it tries again about every second
 *   (`failureLine`): over the last analysis that finished, which every page then shows, or alone
 *   where none has;
 * - the project's own description, where nothing past it was read: no file it includes is read, so
 *   no page has a file of the project to draw;
 * - the other files that did not load, each leading to its finding (`findingsOf`), past four the
 *   rest counted and led to the Files tab, whose rows say of each that it did not load. A file that
 *   does not load stops every check of the project (`checksLeft`), and the pages show what the
 *   files that loaded declare;
 * - each build record this DDD cannot use, by its path from the project's directory, as the Table
 *   tab's File column names a file (`shownPath`), with its reason, in the terminal's words.
 */
export function loadBanner(
  project: string | null,
  state: { files: readonly SourceFile[] } | null,
  failed: string | null,
  refused: readonly RefusedBuild[],
  stopped: boolean,
): LoadBanner | null {
  if (project === null) return null;
  const lines: Part[][] = [];
  if (failed !== null) lines.push([failureLine(failed, state !== null, stopped)]);
  // Named as `unloadedNames` names them, told apart among all of them; the project's own
  // description in a line of its own where nothing past it was read: it did not parse, or did not
  // match its shape, and the state lists it alone. Listed with the files it includes, it read and
  // matched its shape, and holds an entry naming several files of which the loader could not read
  // one (`_unloaded`, gui/session.py): every other file it includes was read then.
  const listed = state?.files ?? [];
  const unloaded = listed.filter((file) => !file.loaded);
  const names = toldApartAll(unloaded.map((file) => file.path));
  const alone = listed.length === 1;
  const described = unloaded.map((file) => alone && file.path === project);
  for (const name of names.filter((_, at) => described[at])) {
    lines.push([
      findingsOf(name),
      ` did not load, so ${checksLeft(1, stopped)}, and no file it includes is read.`,
    ]);
  }
  const others = names.filter((_, at) => !described[at]);
  if (others.length > 0) {
    lines.push([
      ...listedParts(others, findingsOf, (count) => ({
        text: `${countText(count)} more`,
        to: { page: "project", view: "files" },
      })),
      ` did not load, so ${checksLeft(others.length, stopped)}, and the pages show what the files that loaded declare.`,
    ]);
  }
  for (const entry of refused) {
    lines.push([`${shownPath(project, entry.record)}: ${entry.reason}; ${RECORD_IGNORED}.`]);
  }
  if (lines.length === 0) return null;
  return { tone: failed === null ? "warning" : "error", lines };
}

/** What the pages show while the last analysis failed and an earlier one stands. */
const LAST_SHOWN = "The pages show the last analysis that finished";

/** Why the last analysis failed, in the words the terminal prints it in, over the last analysis
 * that finished (`standing`) or alone where none has; and, while ddd gui runs, that it tries again
 * about every second until one succeeds (B11-32). A failure leaves every file it read stamped
 * unknown (`Session._finished`, gui/session.py), so each poll, a second after the last
 * (`poll_interval`), asks for another analysis, a file changed on disk or none - which the
 * heading's "Updating the findings…" shows coming and going. Stopped, ddd gui tries nothing
 * again. */
function failureLine(failed: string, standing: boolean, stopped: boolean): string {
  const said = `Analysing the project failed: ${failed}.`;
  if (stopped) return standing ? `${said} ${LAST_SHOWN}.` : said;
  return standing
    ? `${said} ${LAST_SHOWN}, and ddd gui tries again about every second, until one succeeds.`
    : `${said} ddd gui tries again about every second, until an analysis succeeds.`;
}

/** What `count` files that did not load leave of the project's checks: none runs until every file
 * loads. An analysis whose read reported an error goes no further (`_run`, lsp/diagnostics.py), as
 * `ddd check` stops at the read, so the counts every page draws beside the banner are the read's
 * alone - no check said a file that loaded has nothing to fix. While ddd gui runs, they wait until
 * the files load; stopped, nothing runs once they do, and the banner says only that none ran. */
function checksLeft(count: number, stopped: boolean): string {
  if (stopped) return "the project's checks did not run";
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
