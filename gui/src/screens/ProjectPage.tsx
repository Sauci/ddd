import type { State } from "../api/types";
import { useUpdating } from "../app/updating";
import { tableLine } from "../lib/findings";
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
          {/* Widths measured in Chrome (fix round 3) on scratch copies of examples/demo and of a
              generated project of 10,000 declarations: no component's name takes more than 101px
              of Component's 240px, and no count more than its header - 58px of Errors' 90px, 80px
              of Warnings' 100px. File is left to take the width the other three do not, 638px in
              a 1280px window: a path runs far longer than a component's own name or either of its
              counts, and it is an absolute one, so how long it runs depends on where the project
              sits on disk - a longer one is cut with an ellipsis. This table never sits beside a
              panel; it fits a window down to about 537px wide - 567px where a browser draws the
              box's own vertical scrollbar and the page's, 15px each - and narrower, the box
              scrolls sideways. */}
          <Column isRowHeader width={240}>
            Component
          </Column>
          <Column width={90}>Errors</Column>
          <Column width={100}>Warnings</Column>
          <Column>File</Column>
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
              <Cell className={also("path")}>{file.path}</Cell>
            </Row>
          )}
        </TableBody>
      </LongTable>
    </>
  );
}
