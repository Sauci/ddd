import type { State } from "../api/types";
import { useUpdating } from "../app/updating";
import { tableLine } from "../lib/findings";
import { shownPath } from "../lib/paths";
import { Button } from "../ui/Button";
import { also, Cell, Column, LongTable, Row, TableBody, TableHeader } from "../ui/Table";

interface Props {
  state: State;
  onComponent: (file: string) => void;
}

/**
 * The open project's `Table` tab: its components and how many findings each has. The project's
 * name is the heading above the tabs, so this screen and the canvas share it. A row's counts are
 * not marked while the findings update: the line above them is, and the heading says so.
 */
export function ProjectPage({ state, onComponent }: Props) {
  const updating = useUpdating();
  const components = state.files.filter((file) => file.kind === "component");
  return (
    <>
      <p className="summary">{tableLine(state.counts, updating)}</p>
      <LongTable
        aria-label="Components"
        // A press anywhere in a row opens its component, not only a press on the Name button, and
        // so does Enter on a focused row (fix round 1, Minor 4). A press on a row selects no text:
        // React Aria's `usePress` takes it, and turns text selection off on the row from the
        // press's start to its end (`usePress.mjs`, `disableTextSelection`), so a mouse dragged
        // across a File cell selects none of its path - as a press on a row of the Files tab, which
        // selects that row and opens its Remove panel, selects none of its entry. The Name
        // button's own `onPress` does not also fire the row's: `usePress` stops a press event from
        // propagating past whichever element handles it first, by default, and a `Button` never
        // opts out of that (`usePress.mjs`'s own `shouldStopPropagation`) - so the two never fire
        // together over one click.
        onRowAction={(key) => onComponent(String(key))}
      >
        <TableHeader>
          {/* Widths measured in Chrome (fix round 3, addendum) on scratch copies of examples/demo,
              of a generated project of 10,000 declarations and of examples/vocabulary. Errors and
              Warnings are fixed at 70px and 90px, just above their headers - 58px and 79px, wider
              than any count - Errors with a `minWidth` of its own, as React Aria floors a column
              with none at 75px. Component and File share the rest, 1fr to 3fr: in a 1280px window
              227px for names of at most 101px (UserInterface), and 681px for paths of at most 321px
              (subsystems/logging/event_logger.ddd.json), each path relative to the project's
              directory (`shownPath`) with the absolute one in its title. A column never goes below
              its `minWidth`: in a narrower window Component keeps 110px, which holds every name of
              the three projects - a longer one is cut with an ellipsis, never wrapped (ui.css says
              how, for a name that is a button) - and File takes what is left: 265px in a 535px box,
              where the demo's two longest paths are cut with an ellipsis, and 75px at the least.
              This table never sits beside a panel; its floors, 345px, fit a window down to about
              377px wide - 407px where a browser draws the box's own vertical scrollbar and the
              page's, 15px each - and narrower, the box scrolls sideways. */}
          <Column isRowHeader width="1fr" minWidth={110}>
            Component
          </Column>
          <Column width={70} minWidth={70}>
            Errors
          </Column>
          <Column width={90}>Warnings</Column>
          <Column width="3fr" minWidth={75}>
            File
          </Column>
        </TableHeader>
        <TableBody items={components}>
          {(file) => (
            <Row id={file.path} className={also(file.findings.error > 0 ? "has-error" : "")}>
              <Cell>
                <Button variant="link" onPress={() => onComponent(file.path)}>
                  {file.name ?? file.path}
                </Button>
              </Cell>
              <Cell>{file.findings.error}</Cell>
              <Cell>{file.findings.warning}</Cell>
              {/* The path relative to the project's directory (`shownPath`, Ruling T9-5), the
                  absolute one in its title. On a span: React Aria's `Cell` hands its element no
                  `title` (`filterDOMProps` passes on only `dir`, `lang`, `hidden`, `inert` and
                  `translate` of the global attributes), so the title shows over the path's text. */}
              <Cell className={also("path")}>
                <span title={file.path}>{shownPath(state.project, file.path)}</span>
              </Cell>
            </Row>
          )}
        </TableBody>
      </LongTable>
    </>
  );
}
