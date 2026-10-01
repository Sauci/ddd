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
        // A row opens the component on Enter too, not only a click on its own Name button (fix
        // round 1, Minor 4): React Aria does not fire this for a click inside a focusable
        // descendant - the Name button's own `onPress` - only for one elsewhere in the row, so
        // the two never fire together over the one click.
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
