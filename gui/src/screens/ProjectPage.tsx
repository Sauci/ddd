import type { State } from "../api/types";

interface Props {
  name: string;
  state: State | null;
  onComponent: (file: string) => void;
}

/** The open project: its components and how many findings each has. */
export function ProjectPage({ name, state, onComponent }: Props) {
  if (state === null) return <p className="quiet">Checking the project…</p>;
  const components = state.files.filter((file) => file.kind === "component");
  const total = (severity: "error" | "warning") =>
    state.findings.filter((finding) => finding.severity === severity).length;
  return (
    <section>
      <h1>{name}</h1>
      <p className="summary">
        {total("error")} errors, {total("warning")} warnings
      </p>
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
                <button type="button" className="link" onClick={() => onComponent(file.path)}>
                  {file.name ?? file.path}
                </button>
              </td>
              <td>{file.findings.error}</td>
              <td>{file.findings.warning}</td>
              <td className="path">{file.path}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
