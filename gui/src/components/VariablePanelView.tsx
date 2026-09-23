import type { SettleReply, UnitsReply, VariableReply } from "../api/types";
import { removalSentence } from "../lib/declarations";
import { distinctFindings, keyedFindings, namesThisVariable, routeHref } from "../lib/findings";
import { consequence, declaredUnits, shownChanges } from "../lib/units";
import { describeVariable, offerOf } from "../lib/variableKeys";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";
import { KeyChooser, type KeyChooserProps } from "./KeyChooser";
import type { Offer } from "./UnitPanelView";
import { VariableKeysTable } from "./VariableKeysTable";

export interface VariablePanelViewProps
  extends Omit<KeyChooserProps, "keyName" | "units" | "offer" | "owner" | "inPlay"> {
  variable: VariableReply;
  units: UnitsReply;
  /** The key whose chooser is open, or `undefined` - the panel then shows the table alone. */
  selected: string | undefined;
  onSelect: (key: string | undefined) => void;
  /** Following a fixed key to the type that fixes it, without a reload. */
  onOpenType: (name: string) => void;
  preview: SettleReply | null;
  /** Why the chosen value cannot be applied, or why applying it was refused. */
  refusal: string | null;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  /** What removing this declaration from this component would take; `null` on a screen that
   * offers no removal - the graph's panel, where no one component is in view. */
  removal: Offer | null;
  /** Which component the removal would take it from, for the sentence and the label. */
  removeFrom: string | null;
  removalShown: boolean;
  onRemovalShown: (shown: boolean) => void;
  onRemove: () => void;
  onClose: () => void;
}

/** One variable's panel, drawn from what the api answered: a picture of its props. */
export function VariablePanelView(props: VariablePanelViewProps) {
  const { variable, units, preview, refusal, selected } = props;
  const changes = preview?.changes ?? [];
  const offer = selected === undefined ? undefined : offerOf(variable, selected);
  return (
    <Panel title={variable.name} meta={describeVariable(variable)} onClose={props.onClose}>
      <VariableKeysTable
        variable={variable}
        preview={preview}
        selected={selected}
        onSelect={props.onSelect}
        onOpenType={props.onOpenType}
      />
      {variable.findings.length > 0 && (
        <ul className="panel-findings">
          {keyedFindings(distinctFindings(variable.findings)).map(([finding, key]) => {
            const href = namesThisVariable(finding, variable.name) ? null : routeHref(finding);
            return (
              <li key={key}>
                <Chip tone={finding.severity === "error" ? "error" : "warning"}>
                  {finding.check}
                </Chip>{" "}
                {href === null ? (
                  <span className="quiet">{finding.message}</span>
                ) : (
                  <a className="button link" href={href}>
                    {finding.message}
                  </a>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {selected === undefined ? (
        <p className="quiet">Select a key to settle it on every declaration.</p>
      ) : (
        offer !== undefined && (
          <KeyChooser
            offer={offer}
            owner={variable.name}
            inPlay={declaredUnits(variable.declarations)}
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
        )
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
          {props.changesShown && <Changes changes={shownChanges(changes)} />}
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
      {props.removal !== null && props.removeFrom !== null && (
        <section className="panel-offer" aria-label="Remove the declaration">
          <p className="consequence">{removalSentence(variable, props.removeFrom)}</p>
          {props.removal.refusal !== null && (
            <p className="panel-refusal" role="status">
              {props.removal.refusal}
            </p>
          )}
          {props.removal.refusal === null &&
            props.removal.plan !== null &&
            props.removal.plan.changes.length > 0 && (
              <>
                {props.removalShown && (
                  <Changes changes={shownChanges(props.removal.plan.changes)} />
                )}
                <div className="panel-actions">
                  <Button variant="link" onPress={() => props.onRemovalShown(!props.removalShown)}>
                    {props.removalShown ? "Hide changes" : "Show changes"}
                  </Button>
                  <Button
                    variant="secondary"
                    isDisabled={props.busy || props.removal.pending}
                    onPress={props.onRemove}
                  >
                    Remove from {props.removeFrom}
                  </Button>
                </div>
              </>
            )}
        </section>
      )}
    </Panel>
  );
}
