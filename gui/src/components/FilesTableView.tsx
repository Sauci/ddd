import type { FilesReply, SourceFile } from "../api/types";
import { rowsOf } from "../lib/files";
import { baseName } from "../lib/units";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";

export interface FilesTableViewProps {
  reply: FilesReply;
  /** Every file the last analysis read (`State.files`), joined to `reply`'s entries by path -
   * `rowsOf` (lib/files.ts, Task 6) is the one join this tab needs, and the one decision it
   * makes; this view only draws what it answers. */
  files: readonly SourceFile[];
  /** The row's key the address names (`Route`'s own `path`), or `undefined` for the bare tab.
   * One key can belong to more than one row - a literal entry and a pattern's child naming the
   * same file (`FileRow.key`'s own doc, lib/files.ts) - so every row whose `key` matches this is
   * marked, never only the first. A `path` no row carries (a sub-project's own entry, out of this
   * tab's reach) marks nothing, which is not an error. */
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
}

/** The Files tab's table (design §2): a picture of `rowsOf`'s rows - entry, kind, state and
 * findings, in that order - a pattern's matched files indented beneath its own row. Rows are keyed
 * by their position in `rowsOf`'s list rather than by their own `key`, since two rows may share
 * one: a literal entry and a pattern's child can both name the same file (Task 4's own ruling,
 * "New file appends a literal even where a pattern matches the name"). Nothing here decides
 * anything `rowsOf` did not already: a sub-project is a row of kind `project`, drawn exactly as
 * any other kind and never expanded; an entry naming nothing shows its own findings and nothing
 * else, `rowsOf` having given it no file to draw a kind or a state from. */
export function FilesTableView({ reply, files, selected, onSelect }: FilesTableViewProps) {
  const rows = rowsOf(reply, files);
  return (
    rows.length > 0 && (
      <Table
        aria-label="Files"
        selectionMode="single"
        selectedKeys={
          selected === undefined
            ? []
            : rows.flatMap((row, index) => (row.key === selected ? [index] : []))
        }
        onSelectionChange={(keys) => {
          const key = keys === "all" ? undefined : [...keys][0];
          const index = typeof key === "number" ? key : undefined;
          onSelect(index === undefined ? undefined : rows[index]?.key);
        }}
      >
        <TableHeader>
          <Column isRowHeader>Entry</Column>
          <Column>Kind</Column>
          <Column>State</Column>
          <Column>Findings</Column>
        </TableHeader>
        <TableBody>
          {rows.map((row, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: a row is its own position in rowsOf's list - two rows may share one `key`
            <Row key={index} id={index} className={also(row.child ? "child" : "")}>
              <Cell>{row.child ? (row.file?.name ?? baseName(row.key)) : row.entry.entry}</Cell>
              <Cell>{row.file?.kind ?? ""}</Cell>
              <Cell>{row.file === null ? "" : row.file.loaded ? "" : "did not load"}</Cell>
              <Cell>{row.findings === 0 ? "" : String(row.findings)}</Cell>
            </Row>
          ))}
        </TableBody>
      </Table>
    )
  );
}

/** React Aria's own class with this table's beside it, since ui.css selects on both (as
 * `FindingsTableView`'s own `also` already does). */
function also(name: string) {
  return ({ defaultClassName }: { defaultClassName: string | undefined }) =>
    `${defaultClassName ?? ""} ${name}`.trim();
}
