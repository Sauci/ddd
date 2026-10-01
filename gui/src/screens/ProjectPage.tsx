import type { State } from "../api/types";
import { useUpdating } from "../app/updating";
import { tableLine } from "../lib/findings";
import { Button } from "../ui/Button";

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
      <table className="components">
        <thead>
          <tr>
            <th scope="col">Component</th>
            <th scope="col">Errors</th>
            <th scope="col">Warnings</th>
            <th scope="col">File</th>
          </tr>
        </thead>
        <tbody>
          {components.map((file) => (
            <tr key={file.path} className={file.findings.error > 0 ? "has-error" : undefined}>
              <td>
                <Button variant="link" onPress={() => onComponent(file.path)}>
                  {file.name ?? file.path}
                </Button>
              </td>
              <td>{file.findings.error}</td>
              <td>{file.findings.warning}</td>
              <td className="path">{file.path}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
