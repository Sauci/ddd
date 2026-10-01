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
        {/* Unit alone keeps a fixed width: its own vocabulary is short and bounded (%, Hz, RPM,
            degC, …), so it never benefits from more room, at full width or beside a panel. The
            other three are shares of the box's own width (`fr`) instead of fixed pixels (fix
            round 2, New Important 2): a fixed column never grows, so at full width - plenty of
            room - a vocabulary's own sentence clipped under a fixed Description width sized only
            for beside a panel. `minWidth` is each column's own floor, sized so Unit's own fixed
            96px plus the other three's floors sum to at most 535px, what a panel beside this
            table leaves once a headed browser's own vertical scrollbar is taken from the 552px
            box (a headless one, Docker's own screenshot gate among them, draws none). Below about
            a 1077px viewport, even full width does not leave every column its own floor; `.long`'s
            own horizontal scroll is the accepted floor there (fix round 2, New Important 2d). */}
        <Column isRowHeader width={96} minWidth={96}>
          Unit
        </Column>
        <Column width="4fr" minWidth={180}>
          Description
        </Column>
        {/* `2fr`, not `1fr`: measured, "1 variable, 1 type" (`statedBy`, lib/projectUnits.ts) still
            clipped at full width under a `1fr` share, Description's own `4fr` leaving it only
            121px of the 972px the two share there with Findings. */}
        <Column className={also("stated")} width="2fr" minWidth={110}>
          Stated by
        </Column>
        <Column width="1fr" minWidth={90}>
          Findings
        </Column>
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
