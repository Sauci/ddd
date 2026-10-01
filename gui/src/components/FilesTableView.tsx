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
          {/* Every column is a share of the box's own width (`fr`, the same unit CSS Grid and
              Flexbox use), not a fixed pixel count (fix round 2, New Important 2): a fixed column
              never grows, so at full width - plenty of room - Kind, State and Findings stayed
              exactly as narrow as the floor below needs them to be beside a panel, clipping their
              own longest word even where nothing crowded them (measured: State's own longest
              sentence, "not read by the last analysis", FilesTableView.tsx:45 below, clipped at
              1280px wide under the fixed 150px fix round 1 gave it). `minWidth` is each column's
              own floor instead, sized so the four sum to at most 535px - what a panel beside this
              table leaves once a headed browser's own vertical scrollbar (15-17px of the 552px
              box; a headless one, Docker's own screenshot gate among them, draws none) is taken
              from it. Below about a 1077px viewport, even full width does not leave every column
              its own floor; `.long`'s own horizontal scroll is the accepted floor there, not
              fixed by this table's own widths (fix round 2, New Important 2d). */}
          <Column isRowHeader width="5fr" minWidth={220}>
            Entry
          </Column>
          <Column width="1fr" minWidth={70}>
            Kind
          </Column>
          {/* State's own longest sentence, "not read by the last analysis" (lib/files.ts's own
              `stateOf`): the one other column besides Entry given more than a 1fr share, so it
              has room to read whole at full width instead of only beside a panel. */}
          <Column width="4fr" minWidth={150}>
            State
          </Column>
          <Column width="1fr" minWidth={70}>
            Findings
          </Column>
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
