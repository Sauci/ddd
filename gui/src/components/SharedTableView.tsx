import type { SharedReply } from "../api/types";
import { rowKey, type SharedSelection, selectionAt, tabTitle, vocabularyOf } from "../lib/shared";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { Cell, Column, LongTable, Row, TableBody, TableHeader } from "../ui/Table";

export interface SharedTableViewProps {
  reply: SharedReply;
  /** The entry whose panel is open, as the address names it: its vocabulary as well as its name,
   * since a name alone can belong to a row of either (`SharedSelection`'s own doc). `undefined`
   * where nothing is selected, and where the address names an entry of a kind this page cannot
   * route to - no row is marked then, which is also what a name nothing declares looks like. */
  selected: SharedSelection | undefined;
  onSelect: (selected: SharedSelection | undefined) => void;
  /** The names of the files, of this tab's own kinds, that did not load - which declare entries
   * this list cannot show (spec 5.4). A *file*'s own `kind` is the plural word (`"constants"`,
   * `"sections"`); an *entry*'s `kind` is the singular (`"constant"`, `"section"`) - `SharedPage`
   * filters `State.files` by the file's word, never the server's own answer, so there is only the
   * one place the two can be swapped. Empty when every file loaded. */
  unreadable: readonly string[];
  /** Names of files that did not load without saying what kind they are, so this tab
   * cannot claim their entries were its own. */
  untold: readonly string[];
  /** Pressed only where the table is absent, because the project declares nothing. `SharedPage`
   * opens the add form beside the table on it, with its chooser unset - which is why the button
   * names no vocabulary: the reader picks one there, out of every vocabulary the tab holds, where
   * part 13's button could only ever have meant the one. */
  onDeclare: () => void;
}

/** The Shared files tab's table (spec 5.1): a picture of its props. One table for every kind the
 * tab holds - a constant's, a section's and a raster's alike - each entry's own `kind` told apart
 * in its own column rather than by a table per kind. A raster's row needed no change here to
 * draw: the table already takes a vocabulary generically, through `vocabularyOf` below and
 * `row.states` composed on the server, so a third kind was a data change and not a code one
 * (design §5, "the table gains raster rows... through code that already takes a vocabulary"). */
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
          and the banner says which file's own entries are missing from the count and the rows
          below it - a table that silently omitted them would read as a project that declares
          nothing (spec 5.4). Says "entries", not a vocabulary's own word: `unreadable` names a
          failed file of any kind this tab holds - three of them now (ruling 7, task 7 fix round 1),
          and naming the wrong one would send the reader to fix a file that was never broken. */}
      {unreadable.length > 0 && (
        <Banner tone="warning">
          {unreadable.join(", ")} did not load, so the entries declared there are not listed.
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
          Declare an entry
        </Button>
      ) : (
        <LongTable
          aria-label="Shared files"
          selectionMode="single"
          selectedKeys={selected === undefined ? [] : [rowKey(selected.kind, selected.name)]}
          onSelectionChange={(keys) => {
            const key = keys === "all" ? undefined : [...keys][0];
            onSelect(typeof key === "string" ? selectionAt(key) : undefined);
          }}
        >
          <TableHeader>
            {/* Widths measured in Chrome (fix round 3) on this table's stories and on a scratch
                copy of examples/vocabulary - neither examples/demo nor a generated project
                declares a shared entry. Vocabulary is fixed at 95px, its header the widest of its
                words at 90px. The other four share the rest - Name and States 2fr each, Used by
                and Findings 1fr each - in a 1280px window 324px for Name and 325px for States,
                which hold the widest name (PRESSURE_CELLS, 128px) and the longest states
                ("read-write, align 4", 135px). A panel beside the table leaves it a box of about
                552px, 537px once a browser draws the box's own vertical scrollbar; a column never
                goes below its `minWidth`, so Used by and Findings keep 80px there and Name and
                States share what is left - 140px each in a 535px box, which still holds both. The
                floors sum to 495px: beside a panel they fit a window down to about 991px wide -
                1034px where a browser draws the box's own vertical scrollbar and the page's, 15px
                each - and narrower, until the panel moves under the table at 900px, the box
                scrolls sideways; with no panel the table fits a window down to about 527px
                (557px). */}
            <Column isRowHeader width="2fr" minWidth={140}>
              Name
            </Column>
            <Column width={95}>Vocabulary</Column>
            {/* No Description column, unlike TypesTableView: an entry's description is a full
                sentence - the shipped example's is "sample slots of a pressure trend buffer, a
                device wide size no single component owns" - which would dominate every row, where
                what a reader scans this list for is an entry's States, not a paragraph explaining
                it (spec 5.1). The description is in the panel (Task 8). */}
            {/* States, not Value: the word has to fit a constant's own state ("16") as well as a
                section's ("read-only, align 4"), which Value does not - the same call as the
                Vocabulary rename above, from PR #68: cheap before a second vocabulary ships into
                the word, expensive after. */}
            <Column width="2fr" minWidth={100}>
              States
            </Column>
            <Column width="1fr" minWidth={80}>
              Used by
            </Column>
            <Column width="1fr" minWidth={80}>
              Findings
            </Column>
          </TableHeader>
          <TableBody items={rows}>
            {/* Keyed by vocabulary and name, not by name alone: a section's name is a linker
                string, so a project may declare a constant and a section spelling it the same
                way, and two rows under one id are one row to React Aria - the second would lose
                its selection to the first (fix round 1). */}
            {(row) => (
              <Row id={rowKey(row.kind, row.name)}>
                <Cell>{row.name}</Cell>
                <Cell>{vocabularyOf(row.kind)}</Cell>
                <Cell>{row.states}</Cell>
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

/** "2 places", and nothing at all where an entry is named nowhere - a count of zero is noise in
 * a column a reader scans for the ones that are used. Not imported from TypesTableView's own
 * `used`: each table draws its own count from its own row shape, the way the design keeps every
 * table's facts concrete rather than sharing them through an abstraction built to fit whichever
 * table came first (design §2). */
function used(count: number): string {
  return count === 0 ? "" : `${count} place${count === 1 ? "" : "s"}`;
}
