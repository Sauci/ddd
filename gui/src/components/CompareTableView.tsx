import type { FindingRow } from "../lib/findings";
import { Chip } from "../ui/Chip";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";

export interface CompareTableViewProps {
  rows: readonly FindingRow[];
  /** The key of the row whose panel is open, or `undefined`. */
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
}

/** The Compare tab's table of findings, worst first: every row a comparison answers, drawn whole
 * - its findings come in one reply, as the Findings tab's did before that tab drew a window of
 * its rows (`FindingsTableView`). A picture of its props. */
export function CompareTableView({ rows, selected, onSelect }: CompareTableViewProps) {
  return (
    <Table
      aria-label="Findings"
      selectionMode="single"
      selectedKeys={new Set(selected === undefined ? [] : [selected])}
      onSelectionChange={(keys) => {
        const key = keys === "all" ? undefined : [...keys][0];
        onSelect(rows.find((row) => row.key === key)?.key);
      }}
    >
      <TableHeader>
        <Column isRowHeader>Check</Column>
        <Column>Message</Column>
        <Column>File</Column>
      </TableHeader>
      <TableBody items={rows}>
        {(row) => (
          <Row id={row.key} className={also(row.finding.severity === "error" ? "has-error" : "")}>
            <Cell>
              <Chip tone={toneOf(row.finding.severity)}>{row.finding.check}</Chip>
            </Cell>
            <Cell>{row.finding.message}</Cell>
            <Cell className={also("quiet")}>{row.file}</Cell>
          </Row>
        )}
      </TableBody>
    </Table>
  );
}

/** The chip's tone for a severity; `info` is the quiet one the design system calls neutral. */
function toneOf(severity: FindingRow["finding"]["severity"]) {
  return severity === "error" ? "error" : severity === "warning" ? "warning" : "neutral";
}

/** React Aria's own class with this table's beside it, since ui.css selects on both. */
function also(name: string) {
  return ({ defaultClassName }: { defaultClassName: string | undefined }) =>
    `${defaultClassName ?? ""} ${name}`.trim();
}
