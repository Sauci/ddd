import type { SettleReply, UnitsReply, VariableReply } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import { consequence } from "../lib/units";
import { describeVariable } from "../lib/variableKeys";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";
import { KeyChooser, type KeyChooserProps } from "./KeyChooser";
import { VariableKeysTable } from "./VariableKeysTable";

export interface VariablePanelViewProps
  extends Omit<KeyChooserProps, "keyName" | "variable" | "units"> {
  variable: VariableReply;
  units: UnitsReply;
  /** The key whose chooser is open, or `undefined` - the panel then shows the table alone. */
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
  preview: SettleReply | null;
  /** Why the chosen value cannot be applied, or why applying it was refused. */
  refusal: string | null;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  onClose: () => void;
}

/** One variable's panel, drawn from what the api answered: a picture of its props. */
export function VariablePanelView(props: VariablePanelViewProps) {
  const { variable, units, preview, refusal, selected } = props;
  const changes = preview?.changes ?? [];
  return (
    <Panel title={variable.name} meta={describeVariable(variable)} onClose={props.onClose}>
      <VariableKeysTable
        variable={variable}
        preview={preview}
        selected={selected}
        onSelect={props.onSelect}
      />
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
      {selected === undefined ? (
        <p className="quiet">Select a key to settle it on every declaration.</p>
      ) : (
        <KeyChooser
          variable={variable}
          keyName={selected}
          units={units}
          typed={props.typed}
          narrow={props.narrow}
          onTyped={props.onTyped}
          onChosen={props.onChosen}
          onPickerClosed={props.onPickerClosed}
          range={props.range}
          onRange={props.onRange}
          note={props.note}
          busy={props.busy}
          focus={props.focus}
          pickerTrigger={props.pickerTrigger}
        />
      )}
      {refusal !== null ? (
        <p className="panel-refusal" role="status">
          {refusal}
        </p>
      ) : (
        selected !== undefined &&
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
