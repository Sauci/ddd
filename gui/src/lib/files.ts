import type { FilesReply, IncludedEntryReply, SourceFile } from "../api/types";

/**
 * One row of the Files tab: an entry's own row, or one of a pattern's matched files, indented
 * beneath it - the join of `GET /api/files`' entries with `State.files` on the path, the one
 * decision this tab's table needs made before it can be drawn (spec §2, "the page joins the two
 * on the path").
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
   * (`IncludedEntryReply.key`) for their own row, and a matched file's own absolute path
   * (one of the pattern's `files`) for one of its children - so a child asked to be removed
   * meets the server's own refusal naming the pattern, rather than a row this join invented one
   * for. */
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
