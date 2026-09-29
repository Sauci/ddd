import type { FilesReply, IncludedEntryReply, SourceFile } from "../api/types";
import { relativeToProject } from "./findings";

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
   * row naming nothing at all. Also `null` where `State.files` does not hold it: the revision
   * never read it, either because the root's own schema failed before its includes were read, or
   * because a pattern matches a file created since. That is a row naming a file all the same,
   * told apart from a row naming nothing by `entry.names` or `entry.files` alone - never by
   * whether this is `null`, which the two can share. */
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
   * instead, named the way an entry would spell it: relative to the project's own directory
   * (`relativeToProject`, `lib/findings.ts`) - spec §2's "beneath it every file it matched" is a
   * file, not the component or vocabulary it happens to declare, which is why this is never
   * `file?.name`: two rows of one file (a literal and a pattern's child) must read as the one
   * file they are, and a matched file's own declared name is not always there to read besides
   * (`file` is `null` where the revision has not read it yet). */
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
 * row whose matched file it lacks (`row.child`) - the two causes Task 6's own ruling names (a root
 * whose read stopped at its own schema before its includes were read; a pattern matching a file
 * created since the revision). Both are a row naming a file all the same, never a row naming
 * nothing - which is why the check above this, `!row.entry.names && row.entry.files.length ===
 * 0`, is exactly `rowsOf`'s own test for that (Task 6: "names is False for every pattern, matching
 * files or not" - `names` alone never tells a pattern apart from a row naming nothing, `files` is
 * what does), read first so a row naming nothing is never mistaken for one merely unread. */
function stateOf(row: FileRow): string {
  if (row.file !== null) return row.file.loaded ? "" : "did not load";
  if (!row.entry.names && row.entry.files.length === 0) return "names no file";
  if (!row.child && !row.entry.names) return "";
  return "not read by the last analysis";
}
