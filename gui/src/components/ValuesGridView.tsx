import {
  type CSSProperties,
  memo,
  type ReactNode,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { TableStateContext } from "react-aria-components";
import type { PlanReply, ValuesReply } from "../api/types";
import { focusCameByTab } from "../app/focus";
import type { WrittenLine } from "../lib/announcing";
import { keptByCell } from "../lib/cellKeys";
import { distinctFindings, keyedFindings } from "../lib/findings";
import { cellId, takesFocusedCell } from "../lib/gridCells";
import { GridStore, gridTexts } from "../lib/gridTexts";
import { marginBelow, scrollFromUnder } from "../lib/heldOffer";
import { type CommaMeaning, commaChoices } from "../lib/numbers";
import {
  cellName,
  columnAxisLabel,
  columnHeader,
  cornerLabel,
  limitsLine,
  noGridNote,
  nothingPasted,
  oneCell,
  pastedValue,
  pasteHint,
  pastes,
  plotDrawn,
  readOnlyNote,
  rowHeader,
  statedNote,
  statedValue,
  type TypedCell,
  wanted,
} from "../lib/objectValues";
import { commaAsked, offerName, offerSentence, typedOffer } from "../lib/typedCells";
import { consequence, NO_UNIT, PLANNING, shownChanges } from "../lib/units";
import { shortValue } from "../lib/variableKeys";
import { Button } from "../ui/Button";
import { PageHeading } from "../ui/PageHeading";
import { Cell, Column, Row, Table, TableBody, TableHeader } from "../ui/Table";
import { UpdatingNote, UpdatingStatus } from "../ui/UpdatingNote";
import { Changes } from "./Changes";
import { FindingChip } from "./FindingChip";
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
  /** What the heading says the page last wrote (`useWritten`, 16:I13): the cells or the table
   * applied, or an undo putting them back - omitted where nothing was, every story's. */
  written?: WrittenLine | null;
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
  /** Whether the offer's plan is asked for and has not come: the offer then says `PLANNING`
   * where its consequence stands, while it says no refusal (`planning`, lib/units.ts). */
  planning?: boolean;
  refusal: string | null;
  /** The value of a pasted block whose comma could be a decimal point or a thousands separator,
   * which is what the block is refused for (`Pasted.ambiguous`); `null` otherwise, and while no
   * block is pasted. */
  pasteAmbiguous?: string | null;
  /** Whether the block pasted had its first row and column taken for a header, which is not
   * written (`Pasted.header`): the sentence over its preview says so (decision 15.1). `false`
   * while no block is pasted. */
  pasteHeader: boolean;
  /** The reader's answer to what such a comma means, typed or pasted: one press. */
  onComma?: (meaning: CommaMeaning) => void;
  changesShown: boolean;
  busy: boolean;
  onPhysical: (physical: boolean) => void;
  /** A cell typed into: its text, and the reading it was typed in. */
  onTyped: (cell: TypedCell) => void;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  onBack: () => void;
  /** The clipboard's text, from a paste anywhere in the grid - but one value pasted into a cell,
   * which sets that cell as typed (`onTyped`, `pastedValue`). The component reads the event and
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

interface CellFieldProps {
  reply: ValuesReply;
  row: number;
  column: number;
  physical: boolean;
  disabled: boolean;
  /** Where the field reads its text and its column's width from (`GridStore`). */
  store: GridStore;
  onTyped: (cell: TypedCell) => void;
  /** Called with the field once it has the focus. */
  onFocused: (field: HTMLInputElement) => void;
}

/** A grid cell's field. A keystroke draws it again only where it changes the field's own text or
 * its own column's width (`GridStore`): a keystroke typed into one cell draws that cell, not the
 * thousands beside it (15:M8). A move of the focus draws every field, each reading the table's
 * state for the cell it focuses (`TableStateContext`), and so does a draw of the table. On a grid's
 * first entry the table holds no focused cell and moves the focus of a field
 * to its first row, where the keys that follow go; and where it holds one, it gives the focus back
 * to that cell as the focus enters it. So a field taking the focus tells the table that its own
 * cell is the focused one (`gridCells`' `takesFocusedCell`) - unless Tab brought the focus
 * (`focusCameByTab`), where the table's own handling stands: Tab and Shift+Tab give the focus back
 * to the cell it remembers. A field a screen reader or voice control moves the focus to keeps it
 * (16:C1). One value pasted into the field sets its cell as if typed there (`pastedValue`,
 * decision 15.2), where anything more is the grid's table. */
function CellField(props: CellFieldProps) {
  const { reply, row, column, physical, store } = props;
  const key = cellId(row, column);
  const state = useContext(TableStateContext);
  const text = useSyncExternalStore(store.subscribe, () => store.textAt(row, column));
  const chars = useSyncExternalStore(store.subscribe, () => store.charsAt(column));
  return (
    <input
      type="text"
      inputMode="decimal"
      aria-label={cellName(reply, row, column)}
      className={statedValue(reply, row, column) === undefined ? "hollow" : undefined}
      // How many characters this column's fields hold (`gridTexts`), for ui.css to widen them by.
      style={{ "--chars": chars } as CSSProperties}
      value={text}
      disabled={props.disabled}
      onFocus={(event) => {
        const manager = state?.selectionManager;
        if (manager && takesFocusedCell(manager.focusedKey, focusCameByTab())) {
          manager.setFocusedKey(key);
        }
        props.onFocused(event.currentTarget);
      }}
      onChange={(event) => props.onTyped({ row, column, typed: event.target.value, physical })}
      // One value is this cell's: the field takes it whole, as its text, and the grid's own
      // handler around the table, which reads a paste as a table, never sees it. Cancelled, the
      // browser drops nothing into the field. Anything more goes on to that handler.
      onPaste={(event) => {
        const value = pastedValue(event.clipboardData.getData("text/plain"));
        if (value === null) return;
        event.preventDefault();
        event.stopPropagation();
        props.onTyped({ row, column, typed: value, physical });
      }}
      // Enter settles what was typed and nothing more: the preview is already below the grid,
      // and spec 5.3 is explicit that no cell writes on its own - only Apply writes. Taken here
      // all the same, so a habit of finishing a number with Enter reaches neither the table's own
      // keyboard navigation nor anything around it. A key naming one character is the field's
      // own, kept from the table's type-to-find: it would move the focus to a row labelled with
      // that digit and swallow the key (`keptByCell` says which).
      onKeyDown={(event) => {
        if (event.key === "Enter") event.preventDefault();
        if (keptByCell(event)) event.stopPropagation();
      }}
    />
  );
}

interface GridTableProps {
  reply: ValuesReply;
  physical: boolean;
  busy: boolean;
  columnLabels: readonly string[];
  rowLabels: readonly string[];
  store: GridStore;
  onTyped: (cell: TypedCell) => void;
  onFocused: (field: HTMLInputElement) => void;
}

/** The table of fields. Drawn again only when what it is made of changes - the reply, the reading,
 * `busy` - and never for a keystroke, which the fields it holds take from their `store` instead
 * (15:M8): React Aria builds its collection of every row and cell on each draw, a cost that grows
 * with the cells of the grid. */
const GridTable = memo(function GridTable(props: GridTableProps) {
  const { reply, physical, busy, columnLabels, rowLabels, store, onTyped, onFocused } = props;
  // Ids of their own, distinct from either's own label text and from each other's: a map's row
  // and column can both legitimately read "0" (AxisB's first breakpoint, AxisA's), and React
  // Aria's Table keeps rows and columns in one collection keyed by id - a row and a column
  // sharing one made the header lose its own columns entirely, which is what a multi-row grid
  // (AMapWithBothHeaders, the one story more than one row) found and no single-row story could.
  const headerColumns = useMemo<HeaderColumn[]>(
    () => [
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
    ],
    [reply, physical, columnLabels],
  );
  // One row for each the object's shape has, and one column for each (`columnHeader`): what the
  // file does not state is drawn as a hollow cell (`cellName`), where the rows the file wrote and
  // the breakpoints its axis stated drew the grid, values past them unreachable (15:M7).
  const gridRows = useMemo<GridRow[]>(
    () =>
      Array.from({ length: wanted(reply)[0] }, (_, row) => ({
        id: `row:${row}`,
        label: rowLabels[row] ?? "",
        row,
      })),
    [reply, rowLabels],
  );
  return (
    <Table aria-label={`Values of ${reply.name}`}>
      <TableHeader columns={headerColumns}>
        {(column) => <Column isRowHeader={column.isRowHeader}>{column.label}</Column>}
      </TableHeader>
      <TableBody
        items={gridRows}
        dependencies={[reply, physical, busy, store, onTyped, onFocused, headerColumns]}
      >
        {(item) => (
          <Row id={item.id} columns={headerColumns}>
            {(column) => {
              if (column.isRowHeader) return <Cell>{item.label}</Cell>;
              const id = cellId(item.row, column.index);
              return (
                <Cell id={id}>
                  <CellField
                    reply={reply}
                    row={item.row}
                    column={column.index}
                    physical={physical}
                    disabled={reply.file === null || busy}
                    store={store}
                    onTyped={onTyped}
                    onFocused={onFocused}
                  />
                </Cell>
              );
            }}
          </Row>
        )}
      </TableBody>
    </Table>
  );
});

/** One object's values (spec 5.2), drawn from what the api answered: a picture of its props. It
 * holds none of the reader's choices - the raw/physical toggle, the cells typed into, Show changes
 * and busy all live in the screen behind it - only what drawing them takes: the store its fields
 * read their text from (`GridStore`), the screen's latest handler of a cell typed into, and the
 * elements it measures to keep a field clear of the offer. */
export function ValuesGridView(props: ValuesGridViewProps) {
  const { reply, backTo, undoStrip, banner, physical, typed, plan, refusal, changesShown, busy } =
    props;
  const columnLabels = useMemo(() => columnHeader(reply, physical), [reply, physical]);
  const rowLabels = useMemo(() => rowHeader(reply, physical), [reply, physical]);
  // What each field shows, and how wide each column is (`gridTexts`): handed to the fields by a
  // store that tells only the ones whose text or width changed, so that a keystroke does not draw
  // the grid again (15:M8).
  const shown = useMemo(
    () => gridTexts(reply, typed, physical, columnLabels.length),
    [reply, typed, physical, columnLabels],
  );
  const [store] = useState(() => new GridStore(shown));
  useLayoutEffect(() => store.update(shown), [store, shown]);
  // The screen's handlers change with every drawing of it; the table is handed ones that do not.
  const typedInto = useRef(props.onTyped);
  useLayoutEffect(() => {
    typedInto.current = props.onTyped;
  });
  const onTyped = useCallback((cell: TypedCell) => typedInto.current(cell), []);
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
  const sentence = offerSentence(reply, offered, physical, props.pasteHeader);
  // The text whose comma could be a decimal point or a thousands separator, typed or pasted: the
  // offer asks which it is, with one press (`commaChoices`).
  const asked = commaAsked(offered, props.pasteAmbiguous ?? null);
  const columnAxis = columnAxisLabel(reply, physical);
  const readOnly = readOnlyNote(reply);
  const stated = statedNote(reply);
  const noGrid = noGridNote(reply);
  // A field under the offer held at the window's foot - the offer drawn over the field being typed
  // into, near the foot, or the focus moved by a key to a field it covers - is scrolled until it
  // stands above it (`scrollFromUnder`): on the field's focus, and after every render, since the
  // offer comes and grows as its plan does.
  const offer = useRef<HTMLElement>(null);
  const reveal = useCallback((field: Element) => {
    if (offer.current === null) return;
    const placed = (node: Element) => node.getBoundingClientRect();
    window.scrollBy(0, scrollFromUnder(placed(field), placed(offer.current)));
  }, []);
  // And a cell keeps the offer's height clear below it (`marginBelow`, ui.css): the table scrolls a
  // cell the keys moved the focus to into view after its field has taken the focus - Ctrl+End to
  // the last cell of a grid taller than the window, which `reveal` found below the window and left
  // there - and stops with it above the offer rather than under it.
  const table = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const field = document.activeElement;
    if (field instanceof HTMLInputElement && field.closest(".values-table") !== null) {
      reveal(field);
    }
    const held = offer.current === null ? null : offer.current.getBoundingClientRect();
    table.current?.style.setProperty("--offer-clear", marginBelow(held));
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
        // without a word by that apply's own `onSuccess` the moment it landed. Nor does a paste of
        // no text at all, nothing or an image alone, which changes nothing - the cell it was
        // pasted into keeping what was typed there - as no text field takes it (`nothingPasted`).
        //
        // The `busy` half is the one arm of this component nothing pins: a journey would have to
        // paste inside the window an apply is in flight, which it cannot open on purpose, and a
        // test that waited for it would be the race this suite refuses to write. It is left here
        // unguarded by any test on purpose, and said so rather than left to be discovered.
        const text = event.clipboardData.getData("text/plain");
        if (nothingPasted(text) || readOnly !== null || noGrid !== null || !pastes(reply) || busy) {
          return;
        }
        // A cell is a text field: without this the browser also drops the whole block into
        // whichever one has focus. One value pasted into a cell never reaches here: the cell's
        // field takes it (`CellField`).
        event.preventDefault();
        props.onPaste(text);
      }}
    >
      <div className="heading">
        <PageHeading>{reply.name}</PageHeading>
        <Button variant="link" onPress={props.onBack}>
          Back to {backTo}
        </Button>
        {/* After the way back, which it would shift as it joins the row once an edit is written,
            and before the status, kept at the row's end for the same reason (16:M23). */}
        {undoStrip}
        <UpdatingStatus updating={props.updating === true} written={props.written ?? null} />
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
          <div ref={table} className={oneCell(reply) ? "values-table values-one" : "values-table"}>
            <GridTable
              reply={reply}
              physical={physical}
              busy={busy}
              columnLabels={columnLabels}
              rowLabels={rowLabels}
              store={store}
              onTyped={onTyped}
              onFocused={reveal}
            />
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
              <FindingChip severity={finding.severity} check={finding.check} />{" "}
              <span className="quiet">{finding.message}</span>
            </li>
          ))}
        </ul>
      )}
      {(refused !== null || plan !== null || props.planning === true) && (
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
          {refused !== null && asked !== null && (
            <div className="panel-actions values-comma">
              {commaChoices(asked).map((choice) => (
                <Button
                  key={choice.meaning}
                  variant="secondary"
                  isDisabled={busy}
                  onPress={() => props.onComma?.(choice.meaning)}
                >
                  {choice.label}
                </Button>
              ))}
            </div>
          )}
          {refused === null && plan === null && props.planning === true && (
            <p className="consequence">{PLANNING}</p>
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
