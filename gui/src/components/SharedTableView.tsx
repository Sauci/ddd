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
  /** Names of files that did not load without saying what kind they are, so this tab
   * cannot claim their entries were its own. */
  untold: readonly string[];
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
  untold,
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
      {/* A file nobody could read says nothing about what kind of file it is, so this tab cannot
          claim its entries were its own - only that whatever is declared there is missing. It is
          the commonest way a file fails, an editor saving it half-written, and both tabs said
          nothing about it until now. */}
      {untold.length > 0 && (
        <Banner tone="warning">
          {untold.join(", ")} did not load, so whatever is declared there is not listed.
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
            <Column>Vocabulary</Column>
            {/* No Description column, unlike TypesTableView: a constant's description is a full
                sentence - the shipped example's is "sample slots of a pressure trend buffer, a
                device wide size no single component owns" - which would dominate every row, where
                the value is short and is what a reader scans a list of constants for (spec 5.1).
                The description is in the panel (Task 8). */}
            {/* States, not Value: the word has to fit a constant's own state ("16") as well as a
                section's ("read-only, align 4"), which Value does not - the same call as the
                Vocabulary rename above, from PR #68: cheap before a second vocabulary ships into
                the word, expensive after. */}
            <Column>States</Column>
            <Column>Used by</Column>
            <Column>Findings</Column>
          </TableHeader>
          <TableBody items={rows}>
            {(row) => (
              <Row id={row.name}>
                <Cell>{row.name}</Cell>
                <Cell>{vocabularyOf(row.kind)}</Cell>
                <Cell>{row.states}</Cell>
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

/** Which vocabulary a row belongs to, from the singular word the server sends for the entry.
 *
 * `Vocabulary` rather than `Kind`, which the Types tab already uses for a different fact - the
 * shape of a type, `scalar` or `external` or `struct`. One header meaning two things on adjacent
 * tabs is cheap to change now and expensive once sections and rasters have shipped and readers
 * have learned it.
 *
 * All three of this tab's kinds pluralise with a plain `s`, and the plural is the vocabulary's own
 * name - the same word the file kind uses. A fourth that does not would need its own answer here. */
function vocabularyOf(kind: string): string {
  return `${kind}s`;
}
