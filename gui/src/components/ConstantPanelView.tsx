import type { ConstantReply, ConstantUse, PlanReply } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import type { Route } from "../lib/route";
import { baseName, consequence, shownChanges } from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { UpdatingNote } from "../ui/UpdatingNote";
import { Changes } from "./Changes";

/** A change this panel applies: its own value, its description, a rename, or its removal. */
export type ConstantAction = "value" | "describe" | "rename" | "remove";

/**
 * Where one change stands: its plan once it has come, and why it cannot be applied - the same
 * three facts `UnitPanelView` keeps its own four offers in (this panel's sibling, spec 5.2).
 *
 * Defined here rather than imported from there: a constant's four write paths are this panel's
 * own, and importing a unit's would couple the two so that a shape grown for a unit's reason -
 * one neither this panel nor a constant's plan has - would have to be carried here too.
 */
export interface Offer {
  /** The plan; `null` while it is being asked for, or when it was refused. */
  plan: PlanReply | null;
  /** Why the plan was refused, or why applying it was; `null` when neither was. */
  refusal: string | null;
  /** Whether `plan` is `null` because there is none to trust yet: a value's or a description's
   * own debounced request (spec §6) has not yet caught up with what the fields now say, or the
   * server has not yet answered the one that has (`planShown`, `lib/typing.ts` - never an
   * earlier request's answer, kept on screen in its place). `plan` is drawn, and Apply offered,
   * only once this is `false`. */
  pending: boolean;
}

export interface ConstantPanelViewProps {
  reply: ConstantReply;
  /** What the Value field holds: what is being typed, else the entry's own text. */
  value: string;
  onValue: (text: string) => void;
  /** What the Description field holds: what is being typed, else the entry's own description. */
  description: string;
  onDescription: (text: string) => void;
  /** The spelling chosen to rename the constant to, or `null` while none is typed. */
  renameTo: string | null;
  onRenameTo: (to: string | null) => void;
  valueOffer: Offer | null;
  describeOffer: Offer | null;
  renameOffer: Offer | null;
  /** `null` where a shape still names the constant: nothing is asked for then, and the section
   * draws the "Used by" count instead of a control (spec 4.5's refusal is real, but a button that
   * would refuse the moment it was pressed is a button that lies - `ComponentPage.tsx`'s own rule
   * for a shape's cell, spec 5.1). Never itself the reason the section goes empty: `uses.length`
   * is read straight off `reply` below, so a reader is told why whether or not this is `null`. */
  removeOffer: Offer | null;
  /** The offer whose lines Show changes has opened, or `null`. */
  shown: ConstantAction | null;
  onShown: (action: ConstantAction | null) => void;
  onApply: (action: ConstantAction) => void;
  /** Following a use's variable, a member's type, or the component declaring the constant inline,
   * without a reload. */
  onOpen: (route: Route) => void;
  /** Applying, or the server stopped: nothing can be changed or applied. */
  busy: boolean;
  onClose: () => void;
  /** Whether the findings may be about to change (spec 6): the panel says so where it lists them,
   * also while it lists none - an edit may be about to bring the first. */
  updating?: boolean;
}

/** One constant's panel (spec 5.2), drawn from what the api answered: a picture of its props. */
export function ConstantPanelView(props: ConstantPanelViewProps) {
  const { reply, busy } = props;
  // The entry's own pointer is `constants[i]` in a constants file or `component.constants[i]`
  // inline (`ConstantReply.pointer`'s own doc): the prefix is the only place that tells the two
  // apart, since a constants file is not a component and so has no page of its own to link to.
  const declaredInComponent = reply.pointer.startsWith("component.");
  const outcome = (
    action: ConstantAction,
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
      <p className="panel-meta">
        Declared in{" "}
        {declaredInComponent ? (
          <Button
            variant="link"
            onPress={() => props.onOpen({ page: "component", file: reply.file })}
          >
            {baseName(reply.file)}
          </Button>
        ) : (
          baseName(reply.file)
        )}
      </p>
      <section className="panel-offer" aria-label="Value">
        <label className="panel-field">
          Value
          {/* Text, not a number: the format tells `2` and `2.0` apart by the spelling its author
              wrote (design §2) - a whole constant and a fractional one, and `_refuse_whole_
              number` keeps them that way. A number input's value is a JS `number` either way, so
              typing "2.0" there would hand back `2`, silently declaring the other constant from
              the one written. */}
          <input
            type="text"
            value={props.value}
            disabled={busy}
            onChange={(event) => props.onValue(event.target.value)}
          />
        </label>
        {outcome("value", props.valueOffer, () => "Save")}
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
        <p className="quiet">Nothing in the project uses {reply.name}.</p>
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
                <td>{whatOf(use)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <UpdatingNote updating={props.updating === true} />
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
          Only the name changes; its value and description stay as they are, and every place naming
          it follows.
        </p>
        {outcome(
          "rename",
          props.renameOffer,
          (plan) => `Apply to ${plan.changes.length} file${plan.changes.length === 1 ? "" : "s"}`,
        )}
      </section>
      <section className="panel-offer" aria-label="Remove from the constants">
        {reply.uses.length === 0 ? (
          outcome("remove", props.removeOffer, () => "Remove from the constants")
        ) : (
          <p className="quiet">{removeBlocked(reply.name, reply.uses.length)}</p>
        )}
      </section>
    </Panel>
  );
}

/**
 * One change's part of the panel: why it cannot be applied, if it cannot; then, once its plan has
 * come, what it changes, the lines it changes once Show changes opens them, and the button that
 * applies it. Mirrors `UnitPanelView`'s own private `Outcome` component for the same four offers
 * shape; kept local for the reason `Offer` above is.
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

/** What a use's row says under What: the component for a variable's declaration, the one word
 * for a structure member - `ConstantUse.name` already says which member ("Sample_t.history"), so
 * this is only ever a component's name or the noun, never a role the way a type's uses table
 * reads one (a constant's own dimension carries no role of its own to show). */
function whatOf(use: ConstantUse): string {
  return use.kind === "member" ? "member" : (use.component ?? "");
}

/** Where a use's row leads: a variable's own panel on its component's page, or - a member's
 * `name` always being `"<Type>.<member>"` (`ConstantUse.name`'s own doc) - the type holding it,
 * on the Types tab. Mirrors `TypePanelView`'s own private `routeOfUse` for the same two shapes;
 * kept local since that one is not exported and reads a `TypeUse`, not a `ConstantUse`. */
function routeOfUse(use: ConstantUse): Route {
  if (use.kind === "variable") {
    return { page: "component", file: use.path, variable: use.name };
  }
  const dot = use.name.indexOf(".");
  return { page: "project", view: "types", type: dot === -1 ? use.name : use.name.slice(0, dot) };
}

/** What stands where Remove would be, while a shape still names the constant: not the server's
 * own refusal - trying would only ever come back with the one word this already says, and a
 * control asked for just to prove it refuses is the lying button `ComponentPage.tsx` already
 * refuses to draw - but the count that made it refuse, read off `reply.uses` already on screen,
 * in the quiet register the "Used by" table's own empty line above uses, not the warning tone an
 * actual refusal is drawn in. The table above already names each of them; this only says how many. */
function removeBlocked(name: string, count: number): string {
  const verb = count === 1 ? "names" : "name";
  return `${count} shape${count === 1 ? "" : "s"} ${verb} ${name}, so it cannot be removed.`;
}

/* The form that declares a new constant lived here, beside the panel, while a constant was the
 * one thing this tab could declare. It is `SharedAddView` now: one form, whose chooser picks the
 * vocabulary and whose fields follow from it, since the tab has one Declare button and one
 * address shape for both. */
