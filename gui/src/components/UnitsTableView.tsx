import type { UnitsReply } from "../api/types";
import { ROW_HEIGHT } from "../lib/findingsWindow";
import { descriptionOf, findingCheck, statedBy, unitRows } from "../lib/projectUnits";
import { Chip } from "../ui/Chip";
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
    <Virtualizer
      layout={TableLayout}
      layoutOptions={{ rowHeight: ROW_HEIGHT, headingHeight: ROW_HEIGHT }}
    >
      <Table
        aria-label="Units"
        className={also("long")}
        selectionMode="single"
        selectedKeys={new Set(selected === undefined ? [] : [selected])}
        onSelectionChange={(keys) => {
          const key = keys === "all" ? undefined : [...keys][0];
          onSelect(rows.find((row) => row.unit === key)?.unit);
        }}
      >
        <TableHeader>
          {/* Description is the one column left to take the width the other three do not: a
              vocabulary's sentence runs far longer than a unit's own spelling, how it is stated,
              or the one check its findings can ever be (`findingCheck`). */}
          <Column isRowHeader width={96}>
            Unit
          </Column>
          <Column>Description</Column>
          <Column className={also("stated")} width={160}>
            Stated by
          </Column>
          <Column width={160}>Findings</Column>
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
      </Table>
    </Virtualizer>
  );
}

/** React Aria's own class with this table's beside it, since ui.css selects on both: a string
 * would replace React Aria's. */
function also(name: string) {
  return ({ defaultClassName }: { defaultClassName: string | undefined }) =>
    `${defaultClassName ?? ""} ${name}`.trim();
}
