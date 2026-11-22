import type { FindingRow } from "../lib/findings";
import { Chip } from "../ui/Chip";
import { also, Cell, Column, LongTable, Row, TableBody, TableHeader } from "../ui/Table";

export interface CompareTableViewProps {
  rows: readonly FindingRow[];
  /** The key of the row whose panel is open, or `undefined`. */
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
}

/** The Compare tab's table of findings, worst first: every row a comparison answers, of which only
 * the rows in view are drawn (`LongTable`), as every long table but the Findings tab's is - its
 * findings come in one reply, so no page of them is asked for as the reader scrolls, and a verdict
 * filing thousands drew every one into the document, each key and each selection then waiting on
 * all of them. A picture of its props. */
export function CompareTableView({ rows, selected, onSelect }: CompareTableViewProps) {
  return (
    <LongTable
      aria-label="Findings"
      selectionMode="single"
      selectedKeys={new Set(selected === undefined ? [] : [selected])}
      onSelectionChange={(keys) => {
        const key = keys === "all" ? undefined : [...keys][0];
        onSelect(rows.find((row) => row.key === key)?.key);
      }}
    >
      <TableHeader>
        {/* Widths measured in Chrome on this tab's stories, in a 1280 by 720 window. Check is the
            Findings tab's 168px (`.findings-window`, ui.css), which holds the widest chip here,
            changed-interface at 118px. File keeps 232px: the baseline's sensor_hub.ddd.json and
            its cell's padding, beside a panel, where the table's box is 552px. Message takes the
            rest, 152px there and 600px in the 1068px box with no panel - a longer message cut
            with an ellipsis, never wrapped, and read whole in the panel its row opens. The floors
            sum to 500px, which a box beside a panel holds down to a window about 1000px wide (at
            996px the box is 498px), and narrower, until the panel moves under the table at 900px,
            the box scrolls sideways. */}
        <Column isRowHeader width={168}>
          Check
        </Column>
        <Column width="2fr" minWidth={100}>
          Message
        </Column>
        <Column width="1fr" minWidth={232}>
          File
        </Column>
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
    </LongTable>
  );
}

/** The chip's tone for a severity; `info` is the quiet one the design system calls neutral. */
function toneOf(severity: FindingRow["finding"]["severity"]) {
  return severity === "error" ? "error" : severity === "warning" ? "warning" : "neutral";
}
