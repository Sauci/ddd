import type { PlannedChange, SettleReply, UnitsReply, VariableReply } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import {
  baseName,
  consequence,
  describe,
  hunkLines,
  pickerSections,
  unitOfDeclaration,
  willChange,
} from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { UnitPicker } from "./UnitPicker";

export interface VariablePanelViewProps {
  variable: VariableReply;
  units: UnitsReply;
  /** What the picker's field reads: what is being typed, else the label of the unit settled on. */
  typed: string;
  /**
   * What narrows the picker's sections: "" unless the reader is typing, even though `typed`
   * shows the unit the panel would settle on - opening the picker must still list everything
   * ("the picker lists the variable's units, then the project's, narrowed by what is typed"),
   * not just what happens to match the unit it shows.
   */
  narrow: string;
  onTyped: (text: string) => void;
  onChosen: (unit: string | null) => void;
  /** The picker's list closed or its field was left: what was typed there is dropped. */
  onPickerClosed: () => void;
  note: string | undefined;
  preview: SettleReply | null;
  /** Why the chosen unit cannot be applied, or why applying it was refused. */
  refusal: string | null;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  busy: boolean;
  /** A new value on every request to focus the picker; `null` asks for no focus. */
  focusPicker: number | null;
  /** "focus" opens the picker's list as it takes the focus, for a story to photograph it open. */
  pickerTrigger?: "input" | "focus" | undefined;
  onClose: () => void;
}

/** One variable's panel, drawn from what the api answered: a picture of its props. */
export function VariablePanelView(props: VariablePanelViewProps) {
  const { variable, units, preview, refusal } = props;
  const changes = preview?.changes ?? [];
  return (
    <Panel title={variable.name} meta={describe(variable.declarations)} onClose={props.onClose}>
      <table className="panel-declarations">
        <thead>
          <tr>
            <th scope="col">Declared by</th>
            <th scope="col">Role</th>
            <th scope="col">Unit</th>
          </tr>
        </thead>
        <tbody>
          {variable.declarations.map((declaration) => {
            const unit = unitOfDeclaration(declaration);
            const changing = preview !== null && willChange(preview, declaration);
            return (
              <tr
                key={`${declaration.path} ${declaration.pointer}`}
                className={changing ? "changing" : undefined}
              >
                <td>{declaration.component}</td>
                <td className="quiet">{declaration.role}</td>
                <td>
                  {unit ?? <span className="quiet">none</span>}
                  {declaration.type !== null && declaration.stated.unit === undefined && (
                    <span className="quiet">, from {declaration.type}</span>
                  )}
                  {changing && <span className="tag">will change</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {variable.findings.length > 0 && (
        <ul className="panel-findings">
          {keyedFindings(distinctFindings(variable.findings)).map(([finding, key]) => (
            <li key={key}>
              <Chip tone={finding.severity === "error" ? "error" : "warning"}>{finding.check}</Chip>{" "}
              <span className="quiet">{finding.message}</span>
            </li>
          ))}
        </ul>
      )}
      <UnitPicker
        name={variable.name}
        sections={pickerSections(variable.name, variable.declarations, units, props.narrow)}
        typed={props.typed}
        onTyped={props.onTyped}
        onPick={props.onChosen}
        onClose={props.onPickerClosed}
        note={props.note}
        isDisabled={props.busy}
        autoFocus={props.focusPicker}
        menuTrigger={props.pickerTrigger}
      />
      {refusal !== null ? (
        <p className="panel-refusal" role="status">
          {refusal}
        </p>
      ) : (
        preview !== null && <p className="consequence">{consequence(changes)}</p>
      )}
      {refusal === null && changes.length > 0 && (
        <>
          {props.changesShown && <Changes changes={changes} />}
          <div className="panel-actions">
            <Button variant="link" onPress={() => props.onChangesShown(!props.changesShown)}>
              {props.changesShown ? "Hide changes" : "Show changes"}
            </Button>
            <Button variant="primary" isDisabled={props.busy} onPress={props.onApply}>
              Apply to {changes.length} file{changes.length === 1 ? "" : "s"}
            </Button>
          </div>
        </>
      )}
    </Panel>
  );
}

/** The lines each file will get, as Show changes prints them. */
function Changes({ changes }: { changes: readonly PlannedChange[] }) {
  return (
    <div className="changes">
      {changes.flatMap((change) =>
        change.hunks.map((hunk) => (
          <pre key={`${change.file} ${hunk.line}`} className="hunk">
            <span className="where">
              {baseName(change.file)}, line {hunk.line}
            </span>
            {hunkLines(hunk).map((line) => (
              <span key={line.key} className={line.sign === "-" ? "removed" : "added"}>
                {line.sign} {line.text}
              </span>
            ))}
          </pre>
        )),
      )}
    </div>
  );
}
