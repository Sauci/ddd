import type { FilesReply, SourceFile } from "../api/types";
import { cellsOf, rowsOf, selectedIndices } from "../lib/files";
import { also, Cell, Column, LongTable, Row, TableBody, TableHeader } from "../ui/Table";

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
      <LongTable
        aria-label="Files"
        selectionMode="single"
        selectedKeys={selected === undefined ? [] : selectedIndices(rows, selected)}
        onSelectionChange={(keys) => {
          const key = keys === "all" ? undefined : [...keys][0];
          const index = typeof key === "number" ? key : undefined;
          onSelect(index === undefined ? undefined : rows[index]?.key);
        }}
      >
        <TableHeader>
          {/* Widths measured in Chrome (fix round 3) on scratch copies of examples/demo and of a
              generated project of 10,000 declarations, and on this table's stories. Kind and
              Findings are fixed: Kind's words are the file kinds the server's `kind_of` answers,
              "component" the widest at 93px, and Findings a count, six digits taking 66px of its
              80px. Entry and State share the rest, 3fr to 2fr - in a 1280px window, 533px and
              355px, which hold the demo's widest entry (components/user_interface.ddd.json, 270px)
              and State's longest sentence (lib/files.ts's `stateOf`, 196px). A panel beside the
              table leaves it a box of about 552px, 537px once a browser draws the box's own
              vertical scrollbar; a column never goes below its `minWidth`, so Entry keeps 280px
              there, every entry of both projects whole, and State takes what is left - 75px in a
              535px box - its sentences cut with an ellipsis. The floors sum to 520px: beside a
              panel they fit a window down to about 1038px wide - 1082px where a browser draws the
              box's own vertical scrollbar and the page's, 15px each - and narrower, until the panel
              moves under the table at 900px, the box scrolls sideways; with no panel the table fits
              a window down to about 552px (582px). */}
          <Column isRowHeader width="3fr" minWidth={280}>
            Entry
          </Column>
          <Column width={100}>Kind</Column>
          <Column width="2fr" minWidth={60}>
            State
          </Column>
          <Column width={80}>Findings</Column>
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
      </LongTable>
    )
  );
}
