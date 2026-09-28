import type { PlanReply, RasterReply } from "../api/types";
import { distinctFindings, keyedFindings } from "../lib/findings";
import type { Route } from "../lib/route";
import { rasterRemovable, rasterRemoveBlocked, rasterUseRoute, rasterUseWhat } from "../lib/shared";
import { baseName, consequence, shownChanges } from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";

/** A change this panel applies: one of the raster's three keys, a rename, or its removal - the
 * keys in the order `ddd.project_shared.RASTERS.keys` lists them, which is the order the panel
 * draws them in. */
export type RasterAction = "event" | "cycle" | "describe" | "rename" | "remove";

/**
 * Where one change stands: its plan once it has come, and why it cannot be applied - the same
 * three facts `SectionPanelView` keeps its own five offers in (this panel's sibling, spec 5.2).
 *
 * The fourth declaration of this shape, and the count the review that raised it asked to revisit
 * at. Kept, and here is the reason the other three do not give: typescript is structural, so an
 * object with these three fields satisfies all four of them, and no declaration has to be reached
 * for to build one. Four copies of a structural shape cannot come to disagree silently - one that
 * grew a field would be answered by the compiler, at the call sites of that panel and nowhere
 * else. That is not true of the duplications this branch was actually burned by, a key spelled
 * twice (`sectionSet`'s own doc measures it) and a route kind not pinned to the contract's: those
 * were values, which can disagree and did.
 *
 * What sharing costs is readable in `components/VariablePanelView.tsx`, which took the other road:
 * its `removal.offer` is typed by an import from `UnitPanelView`, so a reader asking what a
 * variable's removal offers is sent to a unit's panel to find out - and the import buys nothing.
 * Measured rather than argued: dropping both that import and `screens/VariablePanel.tsx`'s
 * `removalOffer` annotation leaves `tsc --noEmit` passing, the literal being checked against the
 * prop either way. A view's props are its own contract, and this one is three lines.
 */
export interface Offer {
  /** The plan; `null` while it is being asked for, or when it was refused. */
  plan: PlanReply | null;
  /** Why the plan was refused, or why applying it was; `null` when neither was. */
  refusal: string | null;
  /** The plan shown is an earlier one's, kept on screen while this one is asked for: any of the
   * three keys, each of which changes with every key typed. It cannot be applied. */
  pending: boolean;
}

export interface RasterPanelViewProps {
  reply: RasterReply;
  /** What the Event field holds: what is being typed, else the entry's own whole number. */
  event: string;
  onEvent: (text: string) => void;
  /** What the Cycle field holds: what is being typed, else the entry's own cycle - "" where it
   * states none, which is a raster that is not cyclic rather than one missing a key. */
  cycle: string;
  onCycle: (text: string) => void;
  /** What the Description field holds: what is being typed, else the entry's own description. */
  description: string;
  onDescription: (text: string) => void;
  /** The spelling chosen to rename the raster to, or `null` while none is typed. */
  renameTo: string | null;
  onRenameTo: (to: string | null) => void;
  eventOffer: Offer | null;
  cycleOffer: Offer | null;
  describeOffer: Offer | null;
  renameOffer: Offer | null;
  /** `null` where a shape still names the raster: nothing is asked for then, and the panel draws
   * `rasterRemoveBlocked`'s sentence instead of a control that would refuse the moment it was
   * pressed. Never itself the reason that part of the panel goes empty: `rasterRemovable` is
   * asked of `reply` below, so a reader is told why whether or not this is `null`. The api's
   * other refusal - a raster that is all its own file declares - is not a fact the reply carries,
   * so it arrives as this offer's `refusal` instead, in the server's own words and with no button
   * under it. */
  removeOffer: Offer | null;
  /** The offer whose lines Show changes has opened, or `null`. */
  shown: RasterAction | null;
  onShown: (action: RasterAction | null) => void;
  onApply: (action: RasterAction) => void;
  /** Following a use to the variable measured in this raster, or to the component measuring
   * everything it produces in it, without a reload. */
  onOpen: (route: Route) => void;
  /** Applying, or the server stopped: nothing can be changed or applied. */
  busy: boolean;
  onClose: () => void;
}

/** One raster's panel (spec 5.2 as this part extends it), drawn from what the api answered: a
 * picture of its props. */
export function RasterPanelView(props: RasterPanelViewProps) {
  const { reply, busy } = props;
  const outcome = (
    action: RasterAction,
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
      {/* The file's name and nothing to follow it to: a raster is declared in a rasters file and
          nowhere else (`RasterReply.file`'s own doc), as a section is - a component names one and
          declares none. */}
      <p className="panel-meta">Declared in {baseName(reply.file)}</p>
      <section className="panel-offer" aria-label="Event">
        <label className="panel-field">
          Event
          {/* Text, not a number, for the reason the sibling's Alignment field is: a number
              input's value is a JS `number`, and the model wants the whole number `1`, which one
              would hand back as `1.0` the moment it carried a decimal point - a file the loader
              then refuses. The channel range is the model's, and an event outside it is refused
              in its own words; so is one another raster has already claimed, which is a judgement
              no reply on this screen carries (`_event_taken`). */}
          <input
            type="text"
            value={props.event}
            disabled={busy}
            onChange={(event) => props.onEvent(event.target.value)}
          />
        </label>
        {outcome("event", props.eventOffer, () => "Save")}
      </section>
      <section className="panel-offer" aria-label="Cycle">
        <label className="panel-field">
          Cycle
          {/* Left empty for a raster that is not cyclic - crank synchronous, on change, on demand
              - which is a real kind of raster and not an omission (`RasterReply.cycle`'s own
              doc). The spellings the model takes are its own, and one it will not take is refused
              in its words rather than narrowed to a chooser here: unlike a section's `access`,
              `cycle` is a pattern over a count and a decade, not an enum there would be a list to
              offer from. */}
          <input
            type="text"
            value={props.cycle}
            disabled={busy}
            onChange={(event) => props.onCycle(event.target.value)}
          />
        </label>
        {outcome("cycle", props.cycleOffer, () => "Save")}
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
        <p className="quiet">Nothing in the project measures in {reply.name}.</p>
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
            {/* Every shape naming it, of both kinds: a definition measured in it, and a component
                measuring everything it produces in it. What each row is comes from
                `rasterUseWhat` rather than from a condition written here, for the reason the
                whole of this panel's judgement lives in `lib/shared.ts`: a list that quietly
                dropped the second kind would look exactly like a correct one. */}
            {reply.uses.map((use) => (
              <tr key={`${use.path} ${use.pointer}`}>
                <td>
                  <Button variant="link" onPress={() => props.onOpen(rasterUseRoute(use))}>
                    {use.name}
                  </Button>
                </td>
                <td className="quiet">{baseName(use.path)}</td>
                <td>{rasterUseWhat(use)}</td>
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
          Only the name changes; its event, cycle and description stay as they are, and every shape
          naming it follows.
        </p>
        {outcome(
          "rename",
          props.renameOffer,
          (plan) => `Apply to ${plan.changes.length} file${plan.changes.length === 1 ? "" : "s"}`,
        )}
      </section>
      <section className="panel-offer" aria-label="Remove from the rasters">
        {rasterRemovable(reply.uses) ? (
          outcome("remove", props.removeOffer, () => "Remove from the rasters")
        ) : (
          <p className="quiet">{rasterRemoveBlocked(reply.name, reply.uses.length)}</p>
        )}
      </section>
    </Panel>
  );
}

/**
 * One change's part of the panel: why it cannot be applied, if it cannot; then, once its plan has
 * come, what it changes, the lines it changes once Show changes opens them, and the button that
 * applies it. Mirrors `SectionPanelView`'s own private `Outcome`, which mirrors
 * `ConstantPanelView`'s before it, for the same offers shape; kept local for the reason `Offer`
 * above is.
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
