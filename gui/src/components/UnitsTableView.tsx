import type { UnitsReply } from "../api/types";
import { descriptionOf, findingCheck, statedBy, unitRows } from "../lib/projectUnits";
import { Chip } from "../ui/Chip";
import { also, Cell, Column, LongTable, Row, TableBody, TableHeader } from "../ui/Table";

export interface UnitsTableViewProps {
  units: UnitsReply;
  /** The unit whose panel is open, or `undefined`. */
  selected: string | undefined;
  /** A row selected, or the selected one let go. */
  onSelect: (unit: string | undefined) => void;
}

/** The Units tab's table (spec 5.1), drawn from what the api answered: a picture of its props. */
export function UnitsTableView({ units, selected, onSelect }: UnitsTableViewProps) {
  const rows = unitRows(units.units);
  const hasVocabulary = units.vocabulary !== null;
  return (
    <LongTable
      aria-label="Units"
      selectionMode="single"
      selectedKeys={new Set(selected === undefined ? [] : [selected])}
      onSelectionChange={(keys) => {
        const key = keys === "all" ? undefined : [...keys][0];
        onSelect(rows.find((row) => row.unit === key)?.unit);
      }}
    >
      <TableHeader>
        {/* Widths measured in Chrome (fix round 3) on scratch copies of examples/demo and of a
            generated project of 10,000 declarations, and on this table's stories. Unit and Findings
            are fixed: no unit of either project or the stories takes more than 54px of Unit's 96px
            (a unit is free text, so a longer one is cut with an ellipsis, never wrapped), and
            Findings holds one chip, "unknown-unit" or "duplicate-unit" (`findingCheck`), either
            taking 118px of its 130px. Description and Stated by share the rest, 3fr to 1fr - in a
            1280px window 632px and 210px, which hold the stories' longest description (275px) and
            "1 variable, 1 type" (`statedBy`, 128px). A panel beside the table leaves it a box of
            about 552px, 537px once a browser draws the box's own vertical scrollbar; a column never
            goes below its `minWidth`, so Stated by keeps 135px there and Description takes what is
            left - 174px in a 535px box - a longer sentence cut with an ellipsis. The floors sum to
            461px: beside a panel they fit a window down to about 926px wide - 969px where a browser
            draws the box's own vertical scrollbar and the page's, 15px each - and narrower, until
            the panel moves under the table at 900px, the box scrolls sideways; with no panel the
            table fits a window down to about 493px (523px). */}
        <Column isRowHeader width={96}>
          Unit
        </Column>
        <Column width="3fr" minWidth={100}>
          Description
        </Column>
        <Column className={also("stated")} width="1fr" minWidth={135}>
          Stated by
        </Column>
        <Column width={130}>Findings</Column>
      </TableHeader>
      <TableBody items={rows}>
        {(row) => {
          const check = findingCheck(row);
          const unused = row.variables + row.types + row.members === 0;
          return (
            <Row id={row.unit} className={also(check === null ? "" : "has-error")}>
              <Cell className={also("unit")}>{row.unit}</Cell>
              <Cell className={also(row.files.length === 0 ? "quiet" : "")}>
                {descriptionOf(row, hasVocabulary)}
              </Cell>
              <Cell className={also(unused ? "stated quiet" : "stated")}>{statedBy(row)}</Cell>
              {/* Both checks are errors unless a build lowers them, which the row's count does
                  not say: the panel shows each finding at its own severity. */}
              <Cell>{check !== null && <Chip tone="error">{check}</Chip>}</Cell>
            </Row>
          );
        }}
      </TableBody>
    </LongTable>
  );
}
