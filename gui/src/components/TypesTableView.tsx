import type { TypesReply } from "../api/types";
import { typeRows, typesTitle } from "../lib/projectTypes";
import { Banner } from "../ui/Banner";
import { Cell, Column, LongTable, Row, TableBody, TableHeader } from "../ui/Table";

export interface TypesTableViewProps {
  types: TypesReply;
  /** The type whose panel is open, as the address names it. */
  selected: string | undefined;
  onSelect: (name: string | undefined) => void;
  /** The names of the types files that did not load, which declare types this list cannot show
   * (spec 5.4). Empty when every file loaded. */
  unreadable: readonly string[];
  /** Names of files that did not load without saying what kind they are, so this tab
   * cannot claim their entries were its own. */
  untold: readonly string[];
}

/** The Types tab's table (spec 5.1): a picture of its props. */
export function TypesTableView({
  types,
  selected,
  onSelect,
  unreadable,
  untold,
}: TypesTableViewProps) {
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
      {/* A file nobody could read says nothing about what kind of file it is, so this tab cannot
          claim its entries were its own - only that whatever is declared there is missing. It is
          the commonest way a file fails, an editor saving it half-written, and both tabs said
          nothing about it until now. */}
      {untold.length > 0 && (
        <Banner tone="warning">
          {untold.join(", ")} did not load, so whatever is declared there is not listed.
        </Banner>
      )}
      <p className="summary">{typesTitle(types)}</p>
      {rows.length > 0 && (
        <LongTable
          aria-label="Types"
          selectionMode="single"
          selectedKeys={selected === undefined ? [] : [selected]}
          onSelectionChange={(keys) => {
            const key = keys === "all" ? undefined : [...keys][0];
            onSelect(typeof key === "string" ? key : undefined);
          }}
        >
          <TableHeader>
            {/* Widths measured in Chrome (fix round 3) on a scratch copy of examples/demo and on
                this table's stories (a generated project declares no types). Kind is fixed at
                90px: its words are `KIND_WORDS`' and "unknown", the widest at 79px. The other
                four share the rest - Type 2fr, Description 5fr, Used by and Findings 1fr each -
                in a 1280px window 217px for Type, 544px for Description, which hold the demo's
                widest type (SensorDiagnosis_t, 137px) and its longest description (475px). A
                panel beside the table leaves it a box of about 552px, 537px once a browser draws
                the box's own vertical scrollbar; a column never goes below its `minWidth`, so
                Type keeps 150px there, Used by and Findings 80px, and Description takes what is
                left - 135px in a 535px box - its sentences cut with an ellipsis. The floors sum to
                500px: beside a panel they fit a window down to about 1000px wide - 1044px where a
                browser draws the box's own vertical scrollbar and the page's, 15px each - and
                narrower, until the panel moves under the table at 900px, the box scrolls
                sideways; with no panel the table fits a window down to about 532px (562px). */}
            <Column isRowHeader width="2fr" minWidth={150}>
              Type
            </Column>
            <Column width={90}>Kind</Column>
            <Column width="5fr" minWidth={100}>
              Description
            </Column>
            <Column width="1fr" minWidth={80}>
              Used by
            </Column>
            <Column width="1fr" minWidth={80}>
              Findings
            </Column>
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
        </LongTable>
      )}
    </>
  );
}

/** "3 places", and nothing at all where a type is named nowhere - a count of zero is noise in a
 * column a reader scans for the ones that are used. */
function used(count: number): string {
  return count === 0 ? "" : `${count} place${count === 1 ? "" : "s"}`;
}
