import {
  type CSSProperties,
  type InputHTMLAttributes,
  type ReactNode,
  useContext,
  useLayoutEffect,
  useRef,
} from "react";
import { TableStateContext } from "react-aria-components";
import type { PlanReply, ValuesReply } from "../api/types";
import { keptByCell } from "../lib/cellKeys";
import { distinctFindings, keyedFindings } from "../lib/findings";
import { cellId, takesFocusedCell } from "../lib/gridCells";
import { scrollFromUnder } from "../lib/heldOffer";
import {
  cellText,
  columnAxisLabel,
  columnChars,
  columnHeader,
  cornerLabel,
  elementLabel,
  limitsLine,
  noGridNote,
  pasteHint,
  pastes,
  plotDrawn,
  readOnlyNote,
  rowHeader,
  statedNote,
  type TypedCell,
} from "../lib/objectValues";
import { offerName, offerSentence, typedOffer } from "../lib/typedCells";
import { consequence, NO_UNIT, shownChanges } from "../lib/units";
import { shortValue } from "../lib/variableKeys";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";
import { UpdatingNote, UpdatingStatus } from "../ui/UpdatingNote";
import { Changes } from "./Changes";
import { ValuesPlotView } from "./ValuesPlotView";

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
  /** Drawn under the heading, over the grid: the screen's banner saying its read of the next
   * revision failed, the grid drawn being the last one read (`useKept`) - omitted where nothing
   * failed, which is every story. */
  banner?: ReactNode;
  /** Reading in physical values rather than raw counts. */
  physical: boolean;
  /** Every cell typed into and held, with its text (`typedCells.ts`); none while a pasted table
   * owns the offer, or nothing has been typed. */
  typed: readonly TypedCell[];
  plan: PlanReply | null;
  refusal: string | null;
  changesShown: boolean;
  busy: boolean;
  onPhysical: (physical: boolean) => void;
  /** A cell typed into: its text, and the reading it was typed in. */
  onTyped: (cell: TypedCell) => void;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  onBack: () => void;
  /** The clipboard's text, from a paste anywhere in the grid. The component reads the event and
   * hands over its text; what the text means is the screen's and `pasted`'s business. */
  onPaste: (text: string) => void;
  /** Whether the findings may be about to change (spec 6): the grid says so where it lists them,
   * also while it lists none - an edit may be about to bring the first. */
  updating?: boolean;
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

/** One row of the body: its own header label and id, and which of `reply.rows` it is. */
interface GridRow {
  id: string;
  label: string;
  row: number;
}

/** What a grid cell's field takes: an input's own props but `onFocus`, which is the field's, and
 * `onFocused`, called with the field once it has the focus. */
type CellFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "onFocus"> & {
  cellId: string;
  onFocused: (field: HTMLInputElement) => void;
};

/** A grid cell's field. On a grid's first entry the table holds no focused cell and moves the
 * focus of a field to its first row, where the keys that follow go; so a field taking the focus
 * tells the table that its own cell is the focused one, where the table holds none (`gridCells`'
 * `takesFocusedCell`). Where it holds one, its own handling stands: a click sets the clicked cell,
 * and Tab and Shift+Tab give the focus back to the cell it remembers. */
function CellField(props: CellFieldProps) {
  const { cellId: key, onFocused, ...field } = props;
  const state = useContext(TableStateContext);
  return (
    <input
      {...field}
      onFocus={(event) => {
        const manager = state?.selectionManager;
        if (manager && takesFocusedCell(manager.focusedKey)) manager.setFocusedKey(key);
        onFocused(event.currentTarget);
      }}
    />
  );
}

/** One object's values (spec 5.2), drawn from what the api answered: a picture of its props. It
 * holds no state - the raw/physical toggle, the cells typed into, Show changes and busy all live
 * in the screen behind it. */
export function ValuesGridView(props: ValuesGridViewProps) {
  const { reply, backTo, undoStrip, banner, physical, typed, plan, refusal, changesShown, busy } =
    props;
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
  const gridRows: GridRow[] = reply.rows.map((_, row) => ({
    id: `row:${row}`,
    label: rowLabels[row] ?? "",
    row,
  }));
  // How many characters each column's fields hold (`columnChars`), for ui.css to widen them by.
  const chars = columnChars(reply, typed, physical, columnLabels.length);
  const meta = [
    reply.kind,
    reply.datatype,
    reply.unit === "" ? NO_UNIT : reply.unit,
    shortValue("conversion", JSON.stringify(reply.conversion)),
    limitsLine(reply),
  ].join(" · ");
  // What the cells typed into offer (`typedOffer`): the elements they set, or the sentence one of
  // them is refused with - found here rather than by the server, which is never asked for a plan
  // of them then, and ahead of whatever refusal came back for earlier text, which is about numbers
  // no longer in the cells. `null` where no cell is typed into: a pasted table owns the offer
  // instead, and the screen's own refusal (a pasted block's own sentence among them) is what shows.
  // The same judgement the screen keys its plan query on, so `plan` and this either agree or
  // `plan` is still null.
  const offered = typed.length === 0 ? null : typedOffer(typed, reply);
  const refused = offered?.refusal ?? refusal;
  const sentence = offerSentence(reply, offered, physical);
  const columnAxis = columnAxisLabel(reply, physical);
  const readOnly = readOnlyNote(reply);
  const stated = statedNote(reply);
  const noGrid = noGridNote(reply);
  // A field under the offer held at the window's foot - the offer drawn over the field being typed
  // into, near the foot, or the focus moved by a key to a field it covers - is scrolled until it
  // stands above it (`scrollFromUnder`): on the field's focus, and after every render, since the
  // offer comes and grows as its plan does.
  const offer = useRef<HTMLElement>(null);
  const reveal = (field: Element) => {
    if (offer.current === null) return;
    const placed = (node: Element) => node.getBoundingClientRect();
    window.scrollBy(0, scrollFromUnder(placed(field), placed(offer.current)));
  };
  useLayoutEffect(() => {
    const field = document.activeElement;
    if (field instanceof HTMLInputElement && field.closest(".values-table") !== null) {
      reveal(field);
    }
  });
  return (
    <section
      onPaste={(event) => {
        // A read-only grid has nothing to paste into, and says so via `readOnly` below rather
        // than by planning a refusal for a table it could never write (spec 4.3); nor has a
        // page that draws no grid at all, and says why (`noGrid`), nor has a scalar's one cell,
        // which no table is pasted into (`pastes`). A grid with
        // an apply in flight takes nothing either: every input and Apply are disabled while
        // `busy`, so a cell cannot be typed into, and a paste taken here would be cleared
        // without a word by that apply's own `onSuccess` the moment it landed.
        //
        // The `busy` half is the one arm of this component nothing pins: a journey would have to
        // paste inside the window an apply is in flight, which it cannot open on purpose, and a
        // test that waited for it would be the race this suite refuses to write. It is left here
        // unguarded by any test on purpose, and said so rather than left to be discovered.
        if (readOnly !== null || noGrid !== null || !pastes(reply) || busy) return;
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
        <UpdatingStatus updating={props.updating === true} />
      </div>
      {banner}
      <p className="values-meta">{meta}</p>
      {noGrid !== null ? (
        <p className="quiet">{noGrid}</p>
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
                      const id = cellId(row, at);
                      return (
                        <Cell id={id}>
                          <CellField
                            cellId={id}
                            onFocused={reveal}
                            type="text"
                            inputMode="decimal"
                            aria-label={elementLabel(row, at, reply.shape)}
                            className={reply.stated === "none" ? "unstated" : undefined}
                            style={{ "--chars": chars[at] } as CSSProperties}
                            value={cellText(reply, typed, row, at, physical)}
                            disabled={reply.file === null || busy}
                            onChange={(event) =>
                              props.onTyped({
                                row,
                                column: at,
                                typed: event.target.value,
                                physical,
                              })
                            }
                            // Enter settles what was typed and nothing more: the preview is
                            // already below the grid, and spec 5.3 is explicit that no cell
                            // writes on its own - only Apply writes. Taken here all the same,
                            // so a habit of finishing a number with Enter reaches neither the
                            // table's own keyboard navigation nor anything around it. A key
                            // naming one character is the field's own, kept from the table's
                            // type-to-find: it would move the focus to a row labelled with
                            // that digit and swallow the key (`keptByCell` says which).
                            onKeyDown={(event) => {
                              if (event.key === "Enter") event.preventDefault();
                              if (keptByCell(event)) event.stopPropagation();
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
          {stated !== null && <p className="quiet">{stated}</p>}
          {readOnly !== null && <p className="quiet">{readOnly}</p>}
          {/* A grid with nothing to write into has nothing to paste into either (spec 4.3) and
              already says so above, so the hint - the only way the feature is discoverable -
              belongs only where a paste would actually land. */}
          {readOnly === null && pastes(reply) && (
            <p className="quiet values-paste">{pasteHint(reply)}</p>
          )}
          {plotDrawn(reply) && <ValuesPlotView reply={reply} physical={physical} />}
        </>
      )}
      <UpdatingNote updating={props.updating === true} />
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
        // Gated on what there is to show rather than on the cells typed alone: a pasted table
        // owns this same section too, with no cell of its own to name (spec 2: "one edit, one
        // preview, one entry in the undo stack" either way). Held at the window's foot while it
        // is drawn (`.values-offer`), however tall the grid and its plot above it are.
        <section
          ref={offer}
          className="panel-offer values-offer"
          aria-label={offerName(typed.length)}
        >
          {refused !== null && (
            <p className="panel-refusal" role="status">
              {refused}
            </p>
          )}
          {plan !== null && sentence !== null && (
            // What it sets, and the file it lands in - the way `renameConsequence` folds
            // `consequence()` into its own sentence, and for the same reason every sibling
            // write path names its files: an object's numbers live in its producer's file,
            // which need not be the one the reader opened the grid from (spec 5.3's ValueB
            // on Controller, whose numbers are SensorHub's), and learning that should not
            // take opening Show changes. The elements the typed cells set, or a pasted table,
            // which names no one cell (`offerSentence`) - both worth it for the same reason: a
            // reader who typed or pasted physical values and sees raw counts in the hunks is
            // told the two are one change, not two, without opening Show changes to find out.
            <p className="consequence">
              {sentence}. {consequence(plan.changes)}
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
