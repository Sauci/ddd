import type { SharedReply } from "../api/types";
import { tabTitle } from "../lib/shared";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";

export interface SharedTableViewProps {
  reply: SharedReply;
  /** The entry whose panel is open, as the address names it. */
  selected: string | undefined;
  onSelect: (name: string | undefined) => void;
  /** The names of the constants files that did not load, which declare entries this list cannot
   * show (spec 5.4). A *file*'s own `kind` is `"constants"` (plural); an *entry*'s `kind` is
   * `"constant"` (singular) - `SharedPage` filters `State.files` by the file's word, never the
   * server's own answer, so there is only the one place the two can be swapped. Empty when every
   * file loaded. */
  unreadable: readonly string[];
  /** Pressed only where the table is absent, because the project declares nothing. `SharedPage`
   * opens the add form beside the table on it, blank. */
  onDeclare: () => void;
}

/** The Shared files tab's table (spec 5.1): a picture of its props. One table for every kind the
 * tab holds - constants today, sections and rasters later (design §2) - each entry's own `kind`
 * told apart in its own column rather than by a table per kind. */
export function SharedTableView({
  reply,
  selected,
  onSelect,
  unreadable,
  onDeclare,
}: SharedTableViewProps) {
  const rows = reply.entries;
  return (
    <>
      {/* One unreadable file does not blank the others: a constant declared inline still lists,
          and the banner says which file's own constants are missing from the count and the rows
          below it - a table that silently omitted them would read as a project that declares
          nothing (spec 5.4). */}
      {unreadable.length > 0 && (
        <Banner tone="warning">
          {unreadable.join(", ")} did not load, so the constants declared there are not listed.
        </Banner>
      )}
      <p className="summary">{tabTitle(rows)}</p>
      {rows.length === 0 ? (
        <Button variant="primary" onPress={onDeclare}>
          Declare a constant
        </Button>
      ) : (
        <Table
          aria-label="Shared files"
          selectionMode="single"
          selectedKeys={selected === undefined ? [] : [selected]}
          onSelectionChange={(keys) => {
            const key = keys === "all" ? undefined : [...keys][0];
            onSelect(typeof key === "string" ? key : undefined);
          }}
        >
          <TableHeader>
            <Column isRowHeader>Name</Column>
            <Column>Kind</Column>
            {/* No Description column, unlike TypesTableView: a constant's description is a full
                sentence - the shipped example's is "sample slots of a pressure trend buffer, a
                device wide size no single component owns" - which would dominate every row, where
                the value is short and is what a reader scans a list of constants for (spec 5.1).
                The description is in the panel (Task 8). */}
            <Column>Value</Column>
            <Column>Used by</Column>
            <Column>Findings</Column>
          </TableHeader>
          <TableBody items={rows}>
            {(row) => (
              <Row id={row.name}>
                <Cell>{row.name}</Cell>
                <Cell>{row.kind}</Cell>
                <Cell>{row.value}</Cell>
                <Cell>{used(row.uses)}</Cell>
                <Cell>{row.findings === 0 ? "" : String(row.findings)}</Cell>
              </Row>
            )}
          </TableBody>
        </Table>
      )}
    </>
  );
}

/** "2 places", and nothing at all where a constant is named nowhere - a count of zero is noise in
 * a column a reader scans for the ones that are used. Not imported from TypesTableView's own
 * `used`: each table draws its own count from its own row shape, the way the design keeps every
 * table's facts concrete rather than sharing them through an abstraction built to fit whichever
 * table came first (design §2). */
function used(count: number): string {
  return count === 0 ? "" : `${count} place${count === 1 ? "" : "s"}`;
}
