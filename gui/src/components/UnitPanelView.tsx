import type { PlanReply, ProjectUnit, UnitReply, UnitsReply } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import {
  offers,
  placeRole,
  renameConsequence,
  renameSections,
  unitMeta,
} from "../lib/projectUnits";
import { baseName, consequence } from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";
import { UnitPicker } from "./UnitPicker";

/** A change a unit's panel applies. */
export type UnitAction = "describe" | "add" | "remove" | "rename";

/** Where one change stands: its plan once it has come, and why it cannot be applied. */
export interface Offer {
  /** The plan; `null` while it is being asked for, or when it was refused. */
  plan: PlanReply | null;
  /** Why the plan was refused, or why applying it was; `null` when neither was. */
  refusal: string | null;
  /** The plan shown is an earlier one's, kept on screen while this one is asked for: a
   * description's, which changes with every key typed. It cannot be applied. */
  pending: boolean;
}

export interface UnitPanelViewProps {
  unit: ProjectUnit;
  reply: UnitReply;
  units: UnitsReply;
  /** What the Description field reads: what is being typed, else the vocabulary's description. */
  description: string;
  onDescription: (text: string) => void;
  /** What the rename picker's field reads: what is being typed, else the spelling chosen, else
   * the unit's own. */
  typed: string;
  /** What narrows the picker's sections: "" unless the reader is typing, as in part 1's panel -
   * opening the picker lists everything, not just what contains the spelling it shows. */
  narrow: string;
  onTyped: (text: string) => void;
  /** A spelling chosen from the picker, or typed and confirmed with Enter. */
  onChosen: (unit: string) => void;
  /** The picker's list closed or its field was left: what was typed there is dropped. */
  onPickerClosed: () => void;
  /** The spelling chosen to rename the unit to, or `null` while none is. */
  to: string | null;
  /** Each change asked for, or `null` while it is not: the description left as it is, no
   * spelling chosen, or a change the unit's state does not offer. */
  describing: Offer | null;
  adding: Offer | null;
  removing: Offer | null;
  renaming: Offer | null;
  /** The change whose lines Show changes has opened, or `null`. */
  shown: UnitAction | null;
  onShown: (action: UnitAction | null) => void;
  onApply: (action: UnitAction) => void;
  /** Applying, or the server stopped: nothing can be changed or applied. */
  busy: boolean;
  onClose: () => void;
}

/** One unit's panel (spec 5.2), drawn from what the api answered: a picture of its props. */
export function UnitPanelView(props: UnitPanelViewProps) {
  const { unit, reply, units, to } = props;
  const hasVocabulary = units.vocabulary !== null;
  const offered = offers(unit, hasVocabulary);
  const outcome = (
    action: UnitAction,
    offer: Offer | null,
    sentence: (plan: PlanReply) => string,
    label: (plan: PlanReply) => string,
  ) => (
    <Outcome
      offer={offer}
      sentence={sentence}
      label={label}
      // The rename is the one change every panel offers, and its button the panel's own.
      variant={action === "rename" ? "primary" : "secondary"}
      shown={props.shown === action}
      onShown={(shown) => props.onShown(shown ? action : null)}
      onApply={() => props.onApply(action)}
      busy={props.busy}
    />
  );
  const files = (plan: PlanReply) => consequence(plan.changes);
  return (
    <Panel title={unit.unit} meta={unitMeta(unit, reply, hasVocabulary)} onClose={props.onClose}>
      {reply.findings.length > 0 && (
        <ul className="panel-findings">
          {keyedFindings(distinctFindings(reply.findings)).map(([finding, key]) => (
            <li key={key}>
              <Chip tone={finding.severity === "error" ? "error" : "warning"}>{finding.check}</Chip>{" "}
              <span className="quiet">{finding.message}</span>
            </li>
          ))}
        </ul>
      )}
      <h3 className="panel-heading">Where it is stated</h3>
      {reply.sites.length === 0 ? (
        <p className="quiet">Nothing in the project states {unit.unit}.</p>
      ) : (
        <table className="panel-declarations">
          <thead>
            <tr>
              <th scope="col">Where</th>
              <th scope="col">File</th>
              <th scope="col">What</th>
            </tr>
          </thead>
          <tbody>
            {reply.sites.map((site) => (
              <tr key={`${site.path} ${site.pointer}`}>
                <td>{site.name}</td>
                <td className="quiet">{baseName(site.path)}</td>
                <td>{placeRole(site)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {offered.describe && (
        <section className="panel-offer" aria-label="Description">
          <label className="panel-field">
            Description
            <input
              type="text"
              value={props.description}
              disabled={props.busy}
              onChange={(event) => props.onDescription(event.target.value)}
            />
          </label>
          {outcome("describe", props.describing, files, () => "Save")}
        </section>
      )}
      {offered.remove && (
        <section className="panel-offer" aria-label="Remove from the vocabulary">
          {outcome("remove", props.removing, files, () => "Remove from the vocabulary")}
        </section>
      )}
      {offered.add && (
        <section className="panel-offer" aria-label="Add to the vocabulary">
          {outcome("add", props.adding, files, () => "Add to the vocabulary")}
        </section>
      )}
      <section className="panel-offer" aria-label="Rename">
        <UnitPicker
          label={`Rename ${unit.unit} to`}
          sections={renameSections(unit.unit, units, props.narrow)}
          typed={props.typed}
          onTyped={props.onTyped}
          onPick={(chosen) => {
            // Only Enter on the no-unit label answers `null` (part 1's rule), and a unit cannot be
            // renamed into none: the rename lists no such entry, and ignores it.
            if (chosen !== null) props.onChosen(chosen);
          }}
          onClose={props.onPickerClosed}
          note={undefined}
          isDisabled={props.busy}
          autoFocus={null}
        />
        <p className="rename-note">
          Only the spelling changes; values, limits and conversions stay as they are.
        </p>
        {to !== null &&
          outcome(
            "rename",
            props.renaming,
            (plan) => renameConsequence(plan, unit, to, units),
            (plan) => `Apply to ${plan.changes.length} file${plan.changes.length === 1 ? "" : "s"}`,
          )}
      </section>
    </Panel>
  );
}

/**
 * One change's part of the panel: why it cannot be applied, if it cannot; then, once its plan has
 * come, what it changes, the lines it changes once Show changes opens them, and the button that
 * applies it. A change refused on Apply - a file changed on disk - says so above the plan asked
 * for again, which the reader then applies or not.
 */
function Outcome({
  offer,
  sentence,
  label,
  variant,
  shown,
  onShown,
  onApply,
  busy,
}: {
  offer: Offer | null;
  sentence: (plan: PlanReply) => string;
  label: (plan: PlanReply) => string;
  variant: "primary" | "secondary";
  shown: boolean;
  onShown: (shown: boolean) => void;
  onApply: () => void;
  busy: boolean;
}) {
  if (offer === null) return null;
  const { plan, refusal } = offer;
  return (
    <>
      {refusal !== null && (
        <p className="panel-refusal" role="status">
          {refusal}
        </p>
      )}
      {plan !== null && <p className="consequence">{sentence(plan)}</p>}
      {plan !== null && plan.changes.length > 0 && (
        <>
          {shown && <Changes changes={plan.changes} />}
          <div className="panel-actions">
            <Button variant="link" onPress={() => onShown(!shown)}>
              {shown ? "Hide changes" : "Show changes"}
            </Button>
            <Button variant={variant} isDisabled={busy || offer.pending} onPress={onApply}>
              {label(plan)}
            </Button>
          </div>
        </>
      )}
    </>
  );
}
