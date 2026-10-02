import type { PlanReply, ProjectUnit, UnitReply, UnitsReply } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import {
  offers,
  placeRole,
  renameConsequence,
  renameSections,
  unitMeta,
} from "../lib/projectUnits";
import { baseName, consequence, shownChanges } from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { also, Cell, Column, LongTable, Row, TableBody, TableHeader } from "../ui/Table";
import { UpdatingNote } from "../ui/UpdatingNote";
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
  /** Whether the findings may be about to change (spec 6): the panel says so where it lists them,
   * also while it lists none - an edit may be about to bring the first. */
  updating?: boolean;
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
      {props.updating && <UpdatingNote />}
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
        // Ruling T9-1: a unit stated 12,500 times over (100,000 declarations, one unit) makes
        // this table as long as the brief's own seven, so it is virtualised the same way.
        // `.panel-declarations` beside `.long`, for this table alone: it draws in a panel
        // already, the one place a plain `<table>` of the same class once stood, and keeps that
        // look - its header's own size, the margin above the table - rather than `.long`'s own,
        // smaller, unmargined one (fix round 1, Minor 5).
        //
        // Widths measured in Chrome (fix round 3) on scratch copies of examples/demo, of a
        // generated project of 10,000 declarations and of examples/vocabulary. The table draws only
        // inside this panel, whose box is 472px in a 1280px window and 456px when the table beside
        // the panel measures 535px. What is fixed at 140px: its words are `placeRole`'s, "structure
        // member" the widest at 136px. File and Where share the rest, 1fr each, and a column never
        // goes below its `minWidth`: File keeps 180px, which holds the demo's widest file name
        // (user_interface.ddd.json, 169px), and Where, whose names are short - the demo's widest is
        // ParameterA at 96px, the generated project's C00000_O0005 at 115px, examples/vocabulary's
        // ManifoldPressure at 132px - takes what is left, 152px in the 472px box and 136px in the
        // 456px one, above a floor of 125px. A name longer than its column - ManifoldPressure is
        // about 4px short of the 136px - is cut with an ellipsis, never wrapped; Windows' own font
        // was not measured. The floors sum to 445px: the panel's box holds them down to a window
        // about 1043px wide - 1089px where a browser draws the box's own vertical scrollbar and the
        // page's, 15px each - and narrower, until the panel moves under the table it stands beside
        // at 900px and takes the window's whole width, the box scrolls sideways.
        <LongTable aria-label={`Where ${unit.unit} is stated`} className="panel-declarations">
          <TableHeader>
            <Column isRowHeader width="1fr" minWidth={125}>
              Where
            </Column>
            <Column width="1fr" minWidth={180}>
              File
            </Column>
            <Column width={140}>What</Column>
          </TableHeader>
          <TableBody items={reply.sites}>
            {(site) => (
              <Row id={`${site.path} ${site.pointer}`}>
                <Cell>{site.name}</Cell>
                <Cell className={also("quiet")}>{baseName(site.path)}</Cell>
                <Cell>{placeRole(site)}</Cell>
              </Row>
            )}
          </TableBody>
        </LongTable>
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
          {shown && <Changes changes={shownChanges(plan.changes)} />}
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
