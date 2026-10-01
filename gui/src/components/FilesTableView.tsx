import type { FilesReply, SourceFile } from "../api/types";
import { cellsOf, rowsOf, selectedIndices } from "../lib/files";
import { ROW_HEIGHT } from "../lib/findingsWindow";
import {
  Cell,
  Column,
  Row,
  Table,
  TableBody,
  TableHeader,
  TableLayout,
  Virtualizer,
} from "../ui/Table";

export interface FilesTableViewProps {
  reply: FilesReply;
  /** Every file the last analysis read (`State.files`), joined to `reply`'s entries by path -
   * `rowsOf` and `cellsOf` (lib/files.ts) are the two decisions this tab needs made; this view
   * only draws what they answer. */
  files: readonly SourceFile[];
  /** The row's key the address names (`Route`'s own `path`), or `undefined` for the bare tab.
   * One key can belong to more than one row - a literal entry and a pattern's child naming the
   * same file (`FileRow.key`'s own doc, lib/files.ts) - so every row whose `key` matches this is
   * marked, never only the first (`selectedIndices`, lib/files.ts). A `path` no row carries (a
   * sub-project's own entry, out of this tab's reach) marks nothing, which is not an error. */
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
}

/** The Files tab's table (design §2): a picture of `rowsOf`'s rows, each drawn through `cellsOf`
 * (lib/files.ts) - entry, kind, state and findings, in that order - a pattern's matched files
 * indented beneath its own row. Rows are keyed by their position in `rowsOf`'s list rather than by
 * their own `key`, since two rows may share one: a literal entry and a pattern's child can both
 * name the same file (the plan's Rulings 16: New file appends a literal entry even where a
 * pattern already names the file). Nothing here decides anything `rowsOf`, `cellsOf` or
 * `selectedIndices` did not already: a sub-project is a row of kind `project`, drawn exactly as
 * any other kind and never expanded. */
export function FilesTableView({ reply, files, selected, onSelect }: FilesTableViewProps) {
  const rows = rowsOf(reply, files);
  return (
    rows.length > 0 && (
      <Virtualizer
        layout={TableLayout}
        layoutOptions={{ rowHeight: ROW_HEIGHT, headingHeight: ROW_HEIGHT }}
      >
        <Table
          aria-label="Files"
          className={also("long")}
          selectionMode="single"
          selectedKeys={selected === undefined ? [] : selectedIndices(rows, selected)}
          onSelectionChange={(keys) => {
            const key = keys === "all" ? undefined : [...keys][0];
            const index = typeof key === "number" ? key : undefined;
            onSelect(index === undefined ? undefined : rows[index]?.key);
          }}
        >
          <TableHeader>
            {/* Entry is left to take the width the other three do not: a path or a pattern runs
                far longer than its own Kind, the longest State sentence ("not read by the last
                analysis"), or a Findings count. */}
            <Column isRowHeader>Entry</Column>
            <Column width={110}>Kind</Column>
            <Column width={220}>State</Column>
            <Column width={90}>Findings</Column>
          </TableHeader>
          <TableBody>
            {rows.map((row, index) => {
              const cells = cellsOf(row, reply.project);
              return (
                // biome-ignore lint/suspicious/noArrayIndexKey: a row is its own position in rowsOf's list - two rows may share one `key`
                <Row key={index} id={index} className={also(row.child ? "child" : "")}>
                  <Cell>{cells.entry}</Cell>
                  <Cell>{cells.kind}</Cell>
                  <Cell>{cells.state}</Cell>
                  <Cell>{cells.findings}</Cell>
                </Row>
              );
            })}
          </TableBody>
        </Table>
      </Virtualizer>
    )
  );
}

/** React Aria's own class with this table's beside it, since ui.css selects on both (as
 * `FindingsTableView`'s own `also` already does). */
function also(name: string) {
  return ({ defaultClassName }: { defaultClassName: string | undefined }) =>
    `${defaultClassName ?? ""} ${name}`.trim();
}
