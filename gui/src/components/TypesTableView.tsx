import type { TypesReply } from "../api/types";
import { typeRows, typesTitle } from "../lib/projectTypes";
import { Banner } from "../ui/Banner";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";

export interface TypesTableViewProps {
  types: TypesReply;
  /** The type whose panel is open, as the address names it. */
  selected: string | undefined;
  onSelect: (name: string | undefined) => void;
  /** The names of the types files that did not load, which declare types this list cannot show
   * (spec 5.4). Empty when every file loaded. */
  unreadable: readonly string[];
}

/** The Types tab's table (spec 5.1): a picture of its props. */
export function TypesTableView({ types, selected, onSelect, unreadable }: TypesTableViewProps) {
  const rows = typeRows(types);
  return (
    <>
      {/* One unreadable file does not blank the others: the list shows what loaded, and says
          which file's types are missing from it. */}
      {unreadable.length > 0 && (
        <Banner tone="warning">
          {unreadable.join(", ")} did not load, so the types declared there are not listed.
        </Banner>
      )}
      <p className="summary">{typesTitle(types)}</p>
      {rows.length > 0 && (
        <Table
          aria-label="Types"
          selectionMode="single"
          selectedKeys={selected === undefined ? [] : [selected]}
          onSelectionChange={(keys) => {
            const key = keys === "all" ? undefined : [...keys][0];
            onSelect(typeof key === "string" ? key : undefined);
          }}
        >
          <TableHeader>
            <Column isRowHeader>Type</Column>
            <Column>Kind</Column>
            <Column>Description</Column>
            <Column>Used by</Column>
            <Column>Findings</Column>
          </TableHeader>
          <TableBody items={rows}>
            {(row) => (
              <Row id={row.name}>
                <Cell>{row.name}</Cell>
                <Cell>{row.kindWord}</Cell>
                <Cell>{row.description}</Cell>
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

/** "3 places", and nothing at all where a type is named nowhere - a count of zero is noise in a
 * column a reader scans for the ones that are used. */
function used(count: number): string {
  return count === 0 ? "" : `${count} place${count === 1 ? "" : "s"}`;
}
