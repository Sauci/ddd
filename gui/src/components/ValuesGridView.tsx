import type { PlanReply, ValuesReply } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import { cellSentence, columnHeader, physicalOf, rawOf, rowHeader } from "../lib/objectValues";
import { shownChanges } from "../lib/units";
import { shortValue } from "../lib/variableKeys";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";
import { Changes } from "./Changes";

export interface ValuesGridViewProps {
  reply: ValuesReply;
  /** Reading in physical values rather than raw counts. */
  physical: boolean;
  /** The cell being typed into, and its text; `null` when none is. */
  editing: { row: number; column: number; typed: string } | null;
  plan: PlanReply | null;
  refusal: string | null;
  changesShown: boolean;
  busy: boolean;
  onPhysical: (physical: boolean) => void;
  onEditing: (editing: { row: number; column: number; typed: string } | null) => void;
  onEntered: () => void;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  onBack: () => void;
}

/** "element 3", "element 2, 4" - the same one-based phrase `cellSentence` itself builds for the
 * preview, repeated here only to name each cell for a reader who tabs to it directly rather than
 * arrowing through the grid; `cellSentence` is only ever called once, for the cell `editing`
 * names. */
function elementLabel(row: number, column: number, shape: readonly number[]): string {
  return shape.length === 1 ? `element ${column + 1}` : `element ${row + 1}, ${column + 1}`;
}

/** One column of the header row: the blank corner above the row labels, or one of
 * `columnHeader`'s own readings, at `index` into each row's own cells - `-1` for the corner,
 * which no row's cells are ever read at. React Aria's Table wants both the header and every
 * row built from the same `columns`, rather than each row laying out its own cells by a
 * `.map()` React Aria cannot see as one collection with the header's - which is what left a
 * multi-row grid drawing no columns at all until this shape replaced it (measured against
 * AMapWithBothHeaders, the one story more than one row). */
interface HeaderColumn {
  id: string;
  label: string;
  isRowHeader: boolean;
  index: number;
}

/** One row of the body: its own header label and id, its raw cells, and which of `reply.rows`
 * it is. */
interface GridRow {
  id: string;
  label: string;
  cells: number[];
  row: number;
}

/** One object's values (spec 5.2), drawn from what the api answered: a picture of its props. It
 * holds no state - the raw/physical toggle, the cell being typed into, Show changes and busy all
 * live in the screen behind it. */
export function ValuesGridView(props: ValuesGridViewProps) {
  const { reply, physical, editing, plan, refusal, changesShown, busy } = props;
  const columnLabels = columnHeader(reply, physical);
  const rowLabels = rowHeader(reply, physical);
  // Ids of their own, distinct from either's own label text and from each other's: a map's row
  // and column can both legitimately read "0" (AxisB's first breakpoint, AxisA's), and React
  // Aria's Table keeps rows and columns in one collection keyed by id - a row and a column
  // sharing one made the header lose its own columns entirely, which is what a multi-row grid
  // (AMapWithBothHeaders, the one story more than one row) found and no single-row story could.
  const headerColumns: HeaderColumn[] = [
    { id: "corner", label: "", isRowHeader: true, index: -1 },
    ...columnLabels.map((label, index) => ({
      id: `col:${index}`,
      label,
      isRowHeader: false,
      index,
    })),
  ];
  const gridRows: GridRow[] = reply.rows.map((cells, row) => ({
    id: `row:${row}`,
    label: rowLabels[row] ?? "",
    cells,
    row,
  }));
  const meta = [
    reply.kind,
    reply.datatype,
    reply.unit === "" ? "no unit" : reply.unit,
    shortValue("conversion", JSON.stringify(reply.conversion)),
    `${reply.minimum} … ${reply.maximum}`,
  ].join(" · ");
  // What `editing.typed` would write, as a raw count: `null` while nothing is being edited or
  // what is typed is not a number - the same gate the screen itself keys its value-plan query
  // on, so `plan` and this either agree or `plan` is still null.
  const typed = editing === null ? Number.NaN : Number.parseFloat(editing.typed);
  const raw = Number.isNaN(typed)
    ? null
    : physical
      ? rawOf(typed, reply.conversion, reply.datatype)
      : typed;
  return (
    <section>
      <div className="heading">
        <h1>{reply.name}</h1>
        <Button variant="link" onPress={props.onBack}>
          Back to {reply.owner ?? "component"}
        </Button>
      </div>
      <p className="values-meta">{meta}</p>
      {reply.stated === "text" ? (
        <p className="quiet">{`'${reply.name}' is initialised with text, not with a grid`}</p>
      ) : (
        <>
          <fieldset className="values-toggle" aria-label="Physical or raw">
            <Button
              variant={physical ? "primary" : "secondary"}
              aria-pressed={physical}
              isDisabled={busy}
              onPress={() => props.onPhysical(true)}
            >
              Physical
            </Button>
            <Button
              variant={physical ? "secondary" : "primary"}
              aria-pressed={!physical}
              isDisabled={busy}
              onPress={() => props.onPhysical(false)}
            >
              Raw
            </Button>
          </fieldset>
          <div className="values-table">
            <Table aria-label={`Values of ${reply.name}`}>
              <TableHeader columns={headerColumns}>
                {(column) => <Column isRowHeader={column.isRowHeader}>{column.label}</Column>}
              </TableHeader>
              <TableBody items={gridRows}>
                {(item) => (
                  <Row id={item.id} columns={headerColumns}>
                    {(column) => {
                      if (column.isRowHeader) return <Cell>{item.label}</Cell>;
                      const { row } = item;
                      const at = column.index;
                      const value = item.cells[at] ?? 0;
                      const here = editing !== null && editing.row === row && editing.column === at;
                      const shown = here
                        ? editing.typed
                        : String(physical ? physicalOf(value, reply.conversion) : value);
                      return (
                        <Cell>
                          <input
                            type="text"
                            inputMode="decimal"
                            aria-label={elementLabel(row, at, reply.shape)}
                            className={reply.stated === "none" ? "unstated" : undefined}
                            value={shown}
                            disabled={reply.file === null || busy}
                            onChange={(event) =>
                              props.onEditing({ row, column: at, typed: event.target.value })
                            }
                            onKeyDown={(event) => {
                              if (event.key === "Enter") {
                                event.preventDefault();
                                props.onEntered();
                              }
                            }}
                          />
                        </Cell>
                      );
                    }}
                  </Row>
                )}
              </TableBody>
            </Table>
          </div>
          {reply.stated === "none" && <p className="quiet">Nothing is stated.</p>}
          {reply.stated === "scalar" && <p className="quiet">Stated once, for every cell.</p>}
          {reply.file === null && (
            <p className="quiet">{`nothing produces '${reply.name}', so it has no values to set`}</p>
          )}
        </>
      )}
      {reply.findings.length > 0 && (
        <ul className="panel-findings">
          {keyedFindings(distinctFindings(reply.findings)).map(([finding, key]) => (
            <li key={key}>
              <Chip tone={finding.severity === "error" ? "error" : "warning"}>{finding.check}</Chip>{" "}
              <span className="quiet">{finding.message}</span>
            </li>
          ))}
        </ul>
      )}
      {editing !== null && (
        <section className="panel-offer" aria-label="Set the cell">
          {refusal !== null && (
            <p className="panel-refusal" role="status">
              {refusal}
            </p>
          )}
          {plan !== null && raw !== null && (
            <p className="consequence">
              {cellSentence(reply, editing.row, editing.column, raw, physical)}
            </p>
          )}
          {plan !== null && plan.changes.length > 0 && (
            <>
              {changesShown && <Changes changes={shownChanges(plan.changes)} />}
              <div className="panel-actions">
                <Button variant="link" onPress={() => props.onChangesShown(!changesShown)}>
                  {changesShown ? "Hide changes" : "Show changes"}
                </Button>
                <Button variant="primary" isDisabled={busy} onPress={props.onApply}>
                  Apply to {plan.changes.length} file{plan.changes.length === 1 ? "" : "s"}
                </Button>
              </div>
            </>
          )}
        </section>
      )}
    </section>
  );
}
