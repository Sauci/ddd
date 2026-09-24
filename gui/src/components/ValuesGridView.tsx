import type { ReactNode } from "react";
import type { PlanReply, ValuesReply } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import {
  cellSentence,
  columnAxisLabel,
  columnHeader,
  cornerLabel,
  elementLabel,
  pasteHint,
  pasteSentence,
  physicalOf,
  rawOf,
  readOnlyNote,
  rowHeader,
  typedNumber,
  typedRefusal,
} from "../lib/objectValues";
import { consequence, NO_UNIT, shownChanges } from "../lib/units";
import { shortValue } from "../lib/variableKeys";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";
import { Changes } from "./Changes";

export interface ValuesGridViewProps {
  reply: ValuesReply;
  /** The component the "Back to" link returns to and names - resolved by the screen from
   * `state.files`, since the object's own producer (`reply.owner`) can differ from the file the
   * reader opened the grid from (spec 5.4: AxisA read from UserInterface's page is produced by
   * Controller, and the way back is to UserInterface). */
  backTo: string;
  /** The undo control, drawn in this very heading row beside the back link (spec 5.2's "the undo
   * strip where it always is") rather than in a row of its own - omitted where nothing hosts one,
   * which is every story but the ones about undoing. */
  undoStrip?: ReactNode;
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
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  onBack: () => void;
  /** The clipboard's text, from a paste anywhere in the grid. The component reads the event and
   * hands over its text; what the text means is the screen's and `pasted`'s business. */
  onPaste: (text: string) => void;
}

/** One column of the header row: the corner above the row labels, or one of
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
  const { reply, backTo, undoStrip, physical, editing, plan, refusal, changesShown, busy } = props;
  const columnLabels = columnHeader(reply, physical);
  const rowLabels = rowHeader(reply, physical);
  // Ids of their own, distinct from either's own label text and from each other's: a map's row
  // and column can both legitimately read "0" (AxisB's first breakpoint, AxisA's), and React
  // Aria's Table keeps rows and columns in one collection keyed by id - a row and a column
  // sharing one made the header lose its own columns entirely, which is what a multi-row grid
  // (AMapWithBothHeaders, the one story more than one row) found and no single-row story could.
  const headerColumns: HeaderColumn[] = [
    // The corner names an edge of the grid (spec 5.2): the axis the rows are laid against for
    // a map, the axis the columns are laid against for a single row - `AxisA (Hz)` over
    // `CurveA (ms)`. Blank only where that edge is the plain indices.
    { id: "corner", label: cornerLabel(reply, physical), isRowHeader: true, index: -1 },
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
    reply.unit === "" ? NO_UNIT : reply.unit,
    shortValue("conversion", JSON.stringify(reply.conversion)),
    `${reply.minimum} … ${reply.maximum}`,
  ].join(" · ");
  // What `editing.typed` would write, as a raw count: `null` while nothing is being edited or
  // what is typed is not a number - the same gate the screen itself keys its value-plan query
  // on, so `plan` and this either agree or `plan` is still null.
  const typed = editing === null ? Number.NaN : typedNumber(editing.typed);
  const raw = Number.isNaN(typed)
    ? null
    : physical
      ? rawOf(typed, reply.conversion, reply.datatype)
      : typed;
  // What was typed is refused here rather than by the server, which is never asked for a plan
  // for it, and ahead of whatever refusal came back for an earlier value: that one is about a
  // number no longer in the cell. Where no cell is being typed into - a pasted table owns the
  // offer instead - there is no typed refusal to take priority, so the screen's own refusal (a
  // pasted block's own sentence among them) is what shows.
  const refused = (editing === null ? null : typedRefusal(editing.typed)) ?? refusal;
  const columnAxis = columnAxisLabel(reply, physical);
  const readOnly = readOnlyNote(reply);
  return (
    <section
      onPaste={(event) => {
        // A read-only grid has nothing to paste into, and says so via `readOnly` below rather
        // than by planning a refusal for a table it could never write (spec 4.3).
        if (readOnly !== null) return;
        // A cell is a text field: without this the browser also drops the whole block into
        // whichever one has focus.
        event.preventDefault();
        props.onPaste(event.clipboardData.getData("text/plain"));
      }}
    >
      <div className="heading">
        <h1>{reply.name}</h1>
        {undoStrip}
        <Button variant="link" onPress={props.onBack}>
          Back to {backTo}
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
          {columnAxis !== "" && <p className="values-axis">{columnAxis} →</p>}
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
                            // Enter settles what was typed and nothing more: the preview is
                            // already below the grid, and spec 5.3 is explicit that no cell
                            // writes on its own - only Apply writes. Taken here all the same,
                            // so a habit of finishing a number with Enter reaches neither the
                            // table's own keyboard navigation nor anything around it.
                            onKeyDown={(event) => {
                              if (event.key === "Enter") event.preventDefault();
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
          {readOnly !== null && <p className="quiet">{readOnly}</p>}
          {/* A grid with nothing to write into has nothing to paste into either (spec 4.3) and
              already says so above, so the hint - the only way the feature is discoverable -
              belongs only where a paste would actually land. */}
          {readOnly === null && <p className="quiet values-paste">{pasteHint(reply)}</p>}
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
      {(refused !== null || plan !== null) && (
        // Gated on what there is to show rather than on `editing` alone: a pasted table owns
        // this same section too, with no one cell of its own to name (spec 2: "one edit, one
        // preview, one entry in the undo stack" either way).
        <section
          className="panel-offer"
          aria-label={editing !== null ? "Set the cell" : "Replace the values"}
        >
          {refused !== null && (
            <p className="panel-refusal" role="status">
              {refused}
            </p>
          )}
          {plan !== null && (editing === null || raw !== null) && (
            // What it sets, and the file it lands in - the way `renameConsequence` folds
            // `consequence()` into its own sentence, and for the same reason every sibling
            // write path names its files: an object's numbers live in its producer's file,
            // which need not be the one the reader opened the grid from (spec 5.3's ValueB
            // on Controller, whose numbers are SensorHub's), and learning that should not
            // take opening Show changes. A pasted table names no one cell, so `pasteSentence`
            // takes `cellSentence`'s place - both worth it for the same reason: a reader who
            // pasted physical values and sees raw counts in the hunks is told the two are one
            // change, not two, without opening Show changes to find out.
            <p className="consequence">
              {editing !== null && raw !== null && (
                <>{cellSentence(reply, editing.row, editing.column, raw, physical)}. </>
              )}
              {editing === null && <>{pasteSentence(reply)}. </>}
              {consequence(plan.changes)}
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
