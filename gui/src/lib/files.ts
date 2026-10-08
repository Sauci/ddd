import type { FilesPlanRequest } from "../api/client";
import type { FilesPlanReply, FilesReply, IncludedEntryReply, SourceFile } from "../api/types";
import { relativeToProject } from "./findings";
import { consequence } from "./units";

/**
 * One row of the Files tab: an entry's own row, or one of a pattern's matched files, indented
 * beneath it - the join of `GET /api/files`' entries with `State.files` on the path, the one
 * decision this tab's table needs made before it can be drawn - `ddd.gui.contract.FilesReply`'s
 * own words for it: "the page joins on the path rather than this repeating them".
 *
 * Never keyed by `key` alone: one file can have two rows of one key - a literal entry and a
 * pattern's child naming the same file (`New file` appends a literal even where a pattern
 * matches the name already) - and an `includes` list that names one entry twice gives two rows
 * of that entry's own key besides. `rowsOf`'s caller keys each row by its position in the array
 * this returns instead, and lets a route's `path` select every row whose `key` matches it, never
 * only the first.
 */
export interface FileRow {
  /** The entry this row is of: a literal's own, a pattern's own, or - for a child row - the
   * pattern that matched the file this row is about. */
  entry: IncludedEntryReply;
  /** The file this very row is about: a literal's own, or one of a pattern's matched files -
   * `null` for a pattern's own row, whose files are its children rather than itself, and for a
   * row naming nothing at all. Also `null` where `State.files` does not hold it: the revision the
   * page holds never read it. Among the ways: the root's own schema failing before its includes
   * are read; a plugin's model raising while the project is read; a pattern matching a file
   * created since; an entry the description gained since, naming a file nothing else brought in,
   * the entries being read off the description when asked (`IncludedEntryReply.files`). That is a
   * row naming a file all the same, told apart from a row naming nothing by `entry.names` or
   * `entry.files` alone - never by whether this is `null`, which the two can share. */
  file: SourceFile | null;
  /** What a plan to act on this very row is asked with: a literal's or a pattern's own key
   * (`IncludedEntryReply.key`) for their own row, and a matched file's own absolute path (one of
   * the pattern's `files`) for one of its children - the same path a literal entry naming that
   * file would itself carry as its own key. Asking to remove a child is judged by that very rule
   * (`ddd.file_plans.remove_plan`, `_brought_by`): refused, naming the pattern, where no literal
   * also names the file; reaching that literal instead where one does - never a refusal this
   * join invented on a key of its own. */
  key: string;
  /** How many findings this row carries: the entry's own (`IncludedEntryReply.findings` - what a
   * row naming nothing carries, having no `SourceFile` of its own to count) plus, where this row
   * is about a file, that file's own total across every severity; for a pattern's own row, its
   * entry's findings plus the sum of every child's. A file `State.files` lacks counts as none of
   * its own, not an error. */
  findings: number;
  /** Whether this is one of a pattern's matched files, drawn indented beneath its own row -
   * `false` for a literal's row, a pattern's own row, and a row naming nothing. */
  child: boolean;
}

/** The Files tab's rows: `reply`'s entries, each joined to `files` (`State.files`) by path, in
 * the description's own order - a literal's row first, then a pattern's own row immediately
 * followed by one row per file it matched. */
export function rowsOf(reply: FilesReply, files: readonly SourceFile[]): FileRow[] {
  const byPath = new Map(files.map((file) => [file.path, file] as const));
  const rows: FileRow[] = [];
  for (const entry of reply.entries) {
    if (entry.names) {
      const file = byPath.get(entry.key) ?? null;
      rows.push({
        entry,
        file,
        key: entry.key,
        findings: entry.findings + totalOf(file),
        child: false,
      });
      continue;
    }
    if (entry.files.length === 0) {
      rows.push({ entry, file: null, key: entry.key, findings: entry.findings, child: false });
      continue;
    }
    const children = entry.files.map((path) => byPath.get(path) ?? null);
    const broughtIn = children.reduce((sum, file) => sum + totalOf(file), 0);
    rows.push({
      entry,
      file: null,
      key: entry.key,
      findings: entry.findings + broughtIn,
      child: false,
    });
    entry.files.forEach((path, index) => {
      rows.push({
        entry,
        file: children[index] ?? null,
        key: path,
        findings: totalOf(children[index] ?? null),
        child: true,
      });
    });
  }
  return rows;
}

/** A file's findings, of every severity, added together - `0` for a file `State.files` does not
 * hold, which is not the same as a file with nothing filed on it, but counts the same here: a
 * row unable to read a count reads as none rather than as an error the reader must puzzle out. */
function totalOf(file: SourceFile | null): number {
  return file === null ? 0 : file.findings.error + file.findings.warning + file.findings.info;
}

/** The four cells a row of the Files tab draws (design §2) - the table's own picture of a row,
 * decided here so `FilesTableView` only draws it, never chooses it. */
export interface FileCells {
  /** A row's own line shows the entry as `includes` spells it (`IncludedEntryReply.entry`) - the
   * same text whether it names a file, a pattern, or nothing. A child shows the file it is about
   * instead, by its path relative to the project's own directory, or by its base name where a
   * pattern reaches outside that directory (`relativeToProject`, `lib/findings.ts`) - spec §2's
   * "beneath it every file it matched" is a file, not the component or vocabulary it happens to
   * declare, which is why this is never `file?.name`: two rows of one file (a literal and a
   * pattern's child) must read as the one file they are, and a matched file's own declared name is
   * not always there to read besides (`file` is `null` where the revision has not read it yet). */
  entry: string;
  /** The file's own kind, or blank where the row has none: a pattern's own row, an entry naming
   * nothing, and a file the last analysis did not read alike - none has a `SourceFile` to read a
   * kind off. */
  kind: string;
  /** What `stateOf` answers (this file, below) - "names no file", "not read by the last
   * analysis", "did not load", or blank. */
  state: string;
  /** The row's own finding count, or blank where it carries none - `SharedTableView`'s own rule
   * for its own Findings column, a zero count being noise in a column scanned for the ones that
   * are not. */
  findings: string;
}

/** A row's four cells, the one decision `FilesTableView` needs made for it before it can draw a
 * row - `rowsOf`'s join already answered everything this reads. */
export function cellsOf(row: FileRow, project: string): FileCells {
  return {
    entry: row.child ? relativeToProject(row.key, project) : row.entry.entry,
    kind: row.file?.kind ?? "",
    state: stateOf(row),
    findings: row.findings === 0 ? "" : String(row.findings),
  };
}

/** The State cell alone (`FileCells.state`'s own doc says what each answer means).
 *
 * A loaded file's own row and a pattern's own row both draw blank, for two different reasons -
 * the first has nothing wrong to report, the second has no file of its own to report anything
 * about - so the two are answered by different branches below, even though both return "".
 *
 * The two remaining branches fall through to "not read by the last analysis": a literal entry's
 * own row whose file `State.files` lacks (`!row.child && row.entry.names`), and a pattern's child
 * row whose matched file it lacks (`row.child`) - whatever kept the revision the page holds from
 * reading it (`FileRow.file` gives ways it happens: a root whose read stopped at its own schema,
 * a plugin's model raising, a pattern matching a file created since, an entry the description
 * gained since). Both are a row naming a file all the same, never a row naming nothing - which is
 * why the check above this, `!row.entry.names && row.entry.files.length === 0`, is exactly
 * `rowsOf`'s own test for that (`IncludedEntryReply.names` is false for a pattern, matching files
 * or not, and for a plain path naming no file - `names` alone never tells a pattern apart from a
 * row naming nothing, `files` is what does), read first so a row naming nothing is never mistaken
 * for one merely unread. */
function stateOf(row: FileRow): string {
  if (row.file !== null) return row.file.loaded ? "" : "did not load";
  if (!row.entry.names && row.entry.files.length === 0) return "names no file";
  if (!row.child && !row.entry.names) return "";
  return "not read by the last analysis";
}

/** Every position in `rows` whose own `key` is `selected` - a route's own `path` selects every
 * row of that key, which can be more than one (a literal entry and a pattern's child naming the
 * same file, `FileRow.key`'s own doc) - so `FilesTableView` marks every position this answers,
 * never only the first. Empty where no row carries `selected` at all, which is not an error: a
 * sub-project's own entry, named by a route this table has no row for. */
export function selectedIndices(rows: readonly FileRow[], selected: string): number[] {
  return rows.flatMap((row, index) => (row.key === selected ? [index] : []));
}

// --- The three actions (design §3) ------------------------------------------------------------
//
// New file, Add and Remove each ask `GET /api/files-plan` as the reader types or selects, and show
// the plan or the server's refusal in its own words: nothing below judges a name, a path or a
// removal. What is decided here is what to ask, what the Remove panel is called, and what a
// preview draws beside the plan's lines - the server's own sentences as they come, the errors it
// lists as it lists them, and `kept_by` put into words.

/** The kind of file New file asks a second name for, in the word `ddd.file_plans.CREATABLE`
 * spells it with, which `FilesReply.creatable` sends: `create` takes `component` as well, "a new
 * component's own name" (`CreateFile`, the server's model of its query), and `create_plan` ignores
 * it for every other kind. A server renaming the kind would stop the field being drawn, and its
 * own refusal - "a new component needs a name, besides its file's" - would say what is missing. */
const COMPONENT_KIND = "component";

/** Whether New file asks for a component's name beside the file's, the kind field holding
 * `kind`. Compared exactly, as `create_plan` compares a kind with `CREATABLE`: text naming no
 * kind the server creates - "Component" among it - asks for nothing more, and the server refuses
 * the kind in its own words. */
export function asksComponentName(kind: string): boolean {
  return kind === COMPONENT_KIND;
}

/** The plan New file asks for as its three fields stand, or `null` while the kind or the file's
 * name is still empty: `create` takes both (`CreateFile`), and answers a missing or empty one 400
 * - a mistake about the request, not a refusal a reader could act on, as `constantAdd`'s own doc
 * (`lib/shared.ts`) says of `add`'s.
 *
 * Everything else is sent as typed, and the server judges it once the reader pauses (debounced,
 * spec §6, `FilesPage.tsx`'s own `useDebounced`): a kind it creates no file of, a name
 * `FILE_NAME` does not take, a file there already, a component's name unusable or taken - each
 * refused in its own words, none of them restated here. Nothing is trimmed, since "  " is a name
 * the server refuses in words where the page would say nothing.
 *
 * `component` travels for a component alone (`asksComponentName`), and travels empty too: the
 * server answers an empty one with "a new component needs a name, besides its file's", which is
 * what a reader who has not reached that field yet needs to be told. For every other kind it is
 * left out rather than sent to be ignored, so the request says what the plan is made from. */
export function fileCreate(kind: string, name: string, component: string): FilesPlanRequest | null {
  if (kind === "" || name === "") return null;
  if (asksComponentName(kind)) return { action: "create", kind, name, component };
  return { action: "create", kind, name };
}

/** The plan Add asks for as its field stands, or `null` while it is empty - `add`'s one parameter,
 * which the server answers 400 for empty, as `fileCreate`'s are. Sent exactly as typed, since that
 * is the text `add_plan` appends to the includes: relative to the description or absolute, as an
 * entry may be written. Where it leads - outside what `ddd gui` serves, to no file, to one the
 * project has already - the server says. */
export function fileAdd(path: string): FilesPlanRequest | null {
  return path === "" ? null : { action: "add", path };
}

/** What the Remove panel is about: the row a route's `path` selects, and the plan asked for it. */
export interface FileRemoval {
  /** The panel's title: the first row of that key in `rowsOf`'s list - the description's own
   * order - named as the table's own Entry cell names it (`cellsOf`). Two rows can share a key, a
   * literal entry and a pattern's child naming one file, and either can come first: the child,
   * where the pattern is listed before the literal. Both name the one file the panel is about. */
  title: string;
  /** Asked with the row's key, one for every row sharing it: the server takes out every entry of
   * that key (`remove_plan`), refuses a file only a pattern brings in, naming the pattern, and
   * judges what is left - the page asks, and never decides on its own that Remove is possible. */
  request: Extract<FilesPlanRequest, { action: "remove" }>;
}

/** The Remove panel for `selected`, the route's own `path`, or `null` where nothing is selected
 * or no row carries that key - a sub-project's `include-empty` routes to such a key, naming a
 * place only that sub-project's own table would list - so that no panel opens and nothing is
 * asked for a row the reader cannot see. */
export function fileRemoval(
  rows: readonly FileRow[],
  selected: string | undefined,
  project: string,
): FileRemoval | null {
  const row = rows.find((candidate) => candidate.key === selected);
  if (row === undefined) return null;
  return { title: cellsOf(row, project).entry, request: { action: "remove", path: row.key } };
}

/** Whether the Remove panel asks its plan now (P18b-10, spec §7). Its plan re-analyses the
 * project, running its plugins, so the row the page was loaded with - one a link from elsewhere
 * can name, or a bookmark, a typed address or a reload - waits for the reader's press; a row the
 * reader reached within the page, by the table, a link of its own, or a move back or forward from
 * another route (`arrivedAfter`, `lib/route.ts`), asks at once. */
export function removalAsked(arrived: boolean, pressed: boolean): boolean {
  return !arrived || pressed;
}

/** What a preview of one of the three actions draws beside the plan's own lines - decided here,
 * so that `FileActionsView` only draws it. */
export interface FilePreview {
  /** Every error the server lists an added file bringing (`BroughtRow`): in its order, none of
   * its list left out, and none framed by a sentence of the page's own. The server counts them
   * place by place, as a removal is judged, so its list can leave out an error taking the place
   * of one the project has (`ddd.gui.api._addition`). `ddd.gui.contract.BroughtError` says why no
   * heading could be trusted: "the count is what is new" - an error listed can be one the project
   * has now, re-worded, or a mirror's words - so a line calling them new errors would be false of
   * some. Empty for New file and Remove, whose plans bring none. */
  brought: BroughtRow[];
  /** Why the change could not be judged - `FilesPlanReply.unjudged`, the server's own sentence,
   * drawn exactly as it comes - or `null` where it was judged, and for New file. No line of the
   * page's own says that a change was, or was not, judged. */
  unjudged: string | null;
  /** For a removal a pattern left keeps the file in all the same, the sentence saying so
   * (`keptBy`); `null` otherwise. */
  kept: string | null;
  /** What the change writes (`consequence`, `lib/units.ts`), as every panel's preview says it. */
  consequence: string;
  /** What the button applying it says: for a removal, what the entry is taken out of - the
   * includes, as the constants panel's own says "Remove from the constants": not the project, which
   * a file a pattern keeps in stays part of (`kept`), and not the disk, which nothing here touches -
   * else the files the edit writes, as every other panel's Apply counts them. `null` where the plan
   * changes nothing: there is nothing to apply, and no button is drawn. */
  apply: string | null;
}

/** One error `FilesPlanReply.brings` lists, as the Add preview draws it. */
export interface BroughtRow {
  /** The error's place in the list: two errors can be worded alike (`new_errors` counts per
   * place, which a `BroughtError` does not carry), so nothing else tells two rows apart. */
  key: string;
  check: string;
  message: string;
  /** The file it is filed on, named as the table names a pattern's child (`relativeToProject`):
   * by its path relative to the description's directory, or by its base name outside it. */
  file: string;
}

/** A plan of New file, Add or Remove as its preview draws it. `removing` is the key a removal was
 * asked with (`FileRemoval.request.path`), and `null` for New file and Add: it is what names the
 * file a pattern keeps in, and what makes the button Remove's. */
export function previewOf(
  plan: FilesPlanReply,
  project: string,
  removing: string | null,
): FilePreview {
  return {
    brought: plan.brings.map((brought, index) => ({
      key: String(index),
      check: brought.check,
      message: brought.message,
      file: relativeToProject(brought.file, project),
    })),
    unjudged: plan.unjudged,
    kept: removing === null ? null : keptBy(plan, removing, project),
    consequence: consequence(plan.changes),
    apply: applyOf(plan, removing),
  };
}

/** `FilePreview.apply`: nothing where the plan changes nothing, Remove's words for a removal, and
 * otherwise the files the edit writes. */
function applyOf(plan: FilesPlanReply, removing: string | null): string | null {
  if (plan.changes.length === 0) return null;
  if (removing !== null) return "Remove from the includes";
  return `Apply to ${plan.changes.length} file${plan.changes.length === 1 ? "" : "s"}`;
}

/** What the Remove preview says where an entry left keeps the file in the project all the same -
 * `FilesPlanReply.kept_by`, of the three values only a files plan carries the one this page frames
 * in words of its own (Rulings 19): `brings` is listed and `unjudged` drawn as they come - or
 * `null` where nothing left brings the file back.
 *
 * "The pattern", because nothing else can keep it: `remove_plan` takes out every entry whose key
 * is the file, and a literal entry's key is always the file it names, so what is left bringing it
 * in is a pattern (`FilePlan.kept_by`'s own docstring: "a pattern, every entry naming the file
 * being taken out"). "Brings it in" is the server's own phrase for a pattern, in the refusals
 * `add_plan` and `remove_plan` make. The file is named as the table names a pattern's child
 * (`relativeToProject`), `key` being the file's own path. */
function keptBy(plan: FilesPlanReply, key: string, project: string): string | null {
  if (plan.kept_by === null) return null;
  return (
    `${relativeToProject(key, project)} stays in the project all the same: the pattern ` +
    `'${plan.kept_by}' brings it in.`
  );
}
