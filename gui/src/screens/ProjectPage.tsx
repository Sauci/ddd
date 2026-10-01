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
        // A row opens its component on a press anywhere in it, not only on the Name button, and
        // on Enter too (fix round 1, Minor 4). Accepted as it reaches every press rather than only
        // the button's own (fix round 2, New Minor 5): it also keeps a mouse from selecting a
        // path's own text in the row that names it - a reader wanting to copy one does it from the
        // Files tab, where no row press opens anything. The Name button's own `onPress` does not
        // also fire the row's: React Aria's own `usePress` stops a press event from propagating
        // past whichever element handles it first, by default, and a `Button` never opts out of
        // that (`usePress.mjs`'s own `shouldStopPropagation`) - so the two never fire together over
        // one click.
        onRowAction={(key) => onComponent(String(key))}
      >
        <TableHeader>
          <Column isRowHeader width={240}>
            Component
          </Column>
          <Column width={90}>Errors</Column>
          <Column width={100}>Warnings</Column>
          {/* File is left to take the width the other three do not: a path runs far longer
              than a component's own name or either of its counts. */}
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
