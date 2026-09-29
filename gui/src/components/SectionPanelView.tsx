import type { PlanReply, SectionReply, SectionUse } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import type { Route } from "../lib/route";
import { SECTION_ACCESSES, sectionRemoveBlocked } from "../lib/shared";
import { baseName, consequence, shownChanges } from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { ComboBox } from "../ui/ComboBox";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";

/** A change this panel applies: one of the section's three keys, a rename, or its removal - the
 * keys in the order `ddd.project_shared.SECTIONS.keys` lists them, which is the order the panel
 * draws them in. */
export type SectionAction = "access" | "alignment" | "describe" | "rename" | "remove";

/**
 * Where one change stands: its plan once it has come, and why it cannot be applied - the same
 * three facts `ConstantPanelView` keeps its own four offers in (this panel's sibling, spec 5.2).
 *
 * Defined here rather than imported from there, for the reason that one is not imported from
 * `UnitPanelView`: a section's five write paths are this panel's own, and sharing the shape would
 * tie it to a panel whose own reasons to grow are a constant's, not a section's.
 */
export interface Offer {
  /** The plan; `null` while it is being asked for, or when it was refused. */
  plan: PlanReply | null;
  /** Why the plan was refused, or why applying it was; `null` when neither was. */
  refusal: string | null;
  /** The plan shown is an earlier one's, kept on screen while this one is asked for: any of the
   * three keys, each of which changes with every key typed - the access included, its chooser
   * taking typed text like every other in this interface. It cannot be applied. */
  pending: boolean;
}

export interface SectionPanelViewProps {
  reply: SectionReply;
  /** What the Access field holds: what is being typed or was picked, else the entry's own word. */
  access: string;
  onAccess: (text: string) => void;
  /** What the Alignment field holds: what is being typed, else the entry's own whole number. */
  alignment: string;
  onAlignment: (text: string) => void;
  /** What the Description field holds: what is being typed, else the entry's own description. */
  description: string;
  onDescription: (text: string) => void;
  /** The spelling chosen to rename the section to, or `null` while none is typed. */
  renameTo: string | null;
  onRenameTo: (to: string | null) => void;
  accessOffer: Offer | null;
  alignmentOffer: Offer | null;
  describeOffer: Offer | null;
  renameOffer: Offer | null;
  /** `null` where a definition still places its data in the section: nothing is asked for then,
   * and the panel draws `sectionRemoveBlocked`'s sentence instead of a control that would refuse
   * the moment it was pressed. Never itself the reason that part of the panel goes empty:
   * `uses.length` is read straight off `reply` below, so a reader is told why whether or not this
   * is `null`. The last section a file declares is offered like any other: the file it leaves
   * declaring nothing still loads. */
  removeOffer: Offer | null;
  /** The offer whose lines Show changes has opened, or `null`. */
  shown: SectionAction | null;
  onShown: (action: SectionAction | null) => void;
  onApply: (action: SectionAction) => void;
  /** Following a definition to the variable that places its data here, without a reload. */
  onOpen: (route: Route) => void;
  /** Applying, or the server stopped: nothing can be changed or applied. */
  busy: boolean;
  onClose: () => void;
}

/** One section's panel (spec 5.2 as part 14 extends it), drawn from what the api answered: a
 * picture of its props. */
export function SectionPanelView(props: SectionPanelViewProps) {
  const { reply, busy } = props;
  const outcome = (
    action: SectionAction,
    offer: Offer | null,
    label: (plan: PlanReply) => string,
  ) => (
    <Outcome
      offer={offer}
      label={label}
      variant={action === "remove" ? "secondary" : "primary"}
      shown={props.shown === action}
      onShown={(shown) => props.onShown(shown ? action : null)}
      onApply={() => props.onApply(action)}
      busy={busy}
    />
  );
  return (
    <Panel title={reply.name} onClose={props.onClose}>
      {/* The file's name and nothing to follow it to: a section is declared in a sections file and
          nowhere else (`SectionReply.file`'s own doc), where a constant has a second home - a
          component, which has a page of its own for its panel to link to. */}
      <p className="panel-meta">Declared in {baseName(reply.file)}</p>
      <section className="panel-offer" aria-label="Access">
        {/* A chooser over the model's own two words rather than a text field: `access` is an enum
            (`SectionAccess`), so there is a list to offer, and the api judges whatever arrives
            against that same enum - a third word typed over the chooser is refused there, naming
            the two that are allowed, rather than written. */}
        <ComboBox
          label="Access"
          inputValue={props.access}
          onInputChange={props.onAccess}
          sections={[
            {
              id: "accesses",
              title: "Access",
              choices: SECTION_ACCESSES.map((access) => ({
                id: access,
                label: access,
                detail: "",
              })),
            },
          ]}
          onPick={props.onAccess}
          onEnter={props.onAccess}
          onClose={() => undefined}
          isDisabled={busy}
        />
        {outcome("access", props.accessOffer, () => "Save")}
      </section>
      <section className="panel-offer" aria-label="Alignment">
        <label className="panel-field">
          Alignment
          {/* Text, not a number, for the reason the sibling's Value field is: a number input's
              value is a JS `number`, and the model wants the whole number `4`, which one would
              hand back as `4.0` the moment it carried a decimal point - a file the loader then
              refuses. The bytes are what a reader types here; the power-of-two rule is the
              model's, and a `3` is refused in its own words. */}
          <input
            type="text"
            value={props.alignment}
            disabled={busy}
            onChange={(event) => props.onAlignment(event.target.value)}
          />
        </label>
        {outcome("alignment", props.alignmentOffer, () => "Save")}
      </section>
      <section className="panel-offer" aria-label="Description">
        <label className="panel-field">
          Description
          <input
            type="text"
            value={props.description}
            disabled={busy}
            onChange={(event) => props.onDescription(event.target.value)}
          />
        </label>
        {outcome("describe", props.describeOffer, () => "Save")}
      </section>
      <h3 className="panel-heading">Used by</h3>
      {reply.uses.length === 0 ? (
        <p className="quiet">Nothing in the project places its data in {reply.name}.</p>
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
            {reply.uses.map((use) => (
              <tr key={`${use.path} ${use.pointer}`}>
                <td>
                  <Button variant="link" onPress={() => props.onOpen(routeOfUse(use))}>
                    {use.name}
                  </Button>
                </td>
                <td className="quiet">{baseName(use.path)}</td>
                <td>{use.component ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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
      <section className="panel-offer" aria-label="Rename">
        <label className="panel-field">
          {`Rename ${reply.name} to`}
          <input
            type="text"
            value={props.renameTo ?? reply.name}
            disabled={busy}
            onChange={(event) => {
              const text = event.target.value;
              props.onRenameTo(text === reply.name ? null : text);
            }}
          />
        </label>
        <p className="rename-note">
          Only the name changes; its access, alignment and description stay as they are, and every
          definition placing data in it follows.
        </p>
        {outcome(
          "rename",
          props.renameOffer,
          (plan) => `Apply to ${plan.changes.length} file${plan.changes.length === 1 ? "" : "s"}`,
        )}
      </section>
      <section className="panel-offer" aria-label="Remove from the sections">
        {reply.uses.length === 0 ? (
          outcome("remove", props.removeOffer, () => "Remove from the sections")
        ) : (
          <p className="quiet">{sectionRemoveBlocked(reply.name, reply.uses.length)}</p>
        )}
      </section>
    </Panel>
  );
}

/**
 * One change's part of the panel: why it cannot be applied, if it cannot; then, once its plan has
 * come, what it changes, the lines it changes once Show changes opens them, and the button that
 * applies it. Mirrors `ConstantPanelView`'s own private `Outcome`, which mirrors `UnitPanelView`'s
 * before it, for the same offers shape; kept local for the reason `Offer` above is.
 */
function Outcome({
  offer,
  label,
  variant,
  shown,
  onShown,
  onApply,
  busy,
}: {
  offer: Offer | null;
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
      {plan !== null && <p className="consequence">{consequence(plan.changes)}</p>}
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

/** Where a use's row leads: the variable whose definition places its data here, on its component's
 * page. One shape only, where a constant's own `routeOfUse` has two - a section is named by a
 * definition and nowhere else (`SectionUse.kind`, always `"variable"`), so there is no structure
 * member to lead to a type instead. */
function routeOfUse(use: SectionUse): Route {
  return { page: "component", file: use.path, variable: use.name };
}
