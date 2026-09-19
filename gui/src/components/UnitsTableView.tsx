import type { UnitsReply } from "../api/types";
import { descriptionOf, findingCheck, statedBy, unitRows } from "../lib/projectUnits";
import { Chip } from "../ui/Chip";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";

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
    <Table
      aria-label="Units"
      selectionMode="single"
      selectedKeys={new Set(selected === undefined ? [] : [selected])}
      onSelectionChange={(keys) => {
        const key = keys === "all" ? undefined : [...keys][0];
        onSelect(rows.find((row) => row.unit === key)?.unit);
      }}
    >
      <TableHeader>
        <Column isRowHeader>Unit</Column>
        <Column>Description</Column>
        <Column className={also("stated")}>Stated by</Column>
        <Column>Findings</Column>
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
              {/* Both checks are errors unless a build lowers them, which the row's count does not
                  say: the panel shows each finding at its own severity. */}
              <Cell>{check !== null && <Chip tone="error">{check}</Chip>}</Cell>
            </Row>
          );
        }}
      </TableBody>
    </Table>
  );
}

/** React Aria's own class with this table's beside it, since ui.css selects on both: a string
 * would replace React Aria's. */
function also(name: string) {
  return ({ defaultClassName }: { defaultClassName: string | undefined }) =>
    `${defaultClassName ?? ""} ${name}`.trim();
}
