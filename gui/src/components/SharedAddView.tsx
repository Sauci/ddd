import type { PlanReply } from "../api/types";
import {
  addTitle,
  kindNamed,
  SECTION_ACCESSES,
  SHARED_VOCABULARIES,
  vocabularyOf,
} from "../lib/shared";
import { consequence, shownChanges } from "../lib/units";
import { Button } from "../ui/Button";
import { ComboBox } from "../ui/ComboBox";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";

export interface SharedAddViewProps {
  /** What the Vocabulary field holds: the word a vocabulary is known by, or "" while none is
   * chosen. `kindNamed` is what settles it on a vocabulary, here and in the screen that builds
   * the request, so the fields drawn and the request sent can never be for different kinds. */
  vocabulary: string;
  onVocabulary: (text: string) => void;
  /** What the Name field holds. */
  typed: string;
  onTyped: (text: string) => void;
  /** What the Value field holds: the json text to declare a constant with. */
  raw: string;
  onRaw: (text: string) => void;
  /** What the Access field holds: one of a section's two, or "" until one is chosen. */
  access: string;
  onAccess: (text: string) => void;
  /** The chooser's own pick or Enter, apart from typing (`onAccess`): a discrete commit, which
   * `SharedPage.tsx` takes at once rather than waiting out a pause as it does for typing (spec
   * §6, Ruling T12-3). */
  onAccessPicked: (text: string) => void;
  /** What the Alignment field holds: the whole number of bytes a section guarantees. */
  alignment: string;
  onAlignment: (text: string) => void;
  /** What the Event field holds: the channel number xcp addresses a raster by. */
  event: string;
  onEvent: (text: string) => void;
  plan: PlanReply | null;
  refusal: string | null;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  busy: boolean;
  onClose: () => void;
}

/**
 * The form that declares a new entry of any of the tab's three vocabularies (design §4.3's `add`):
 * the chooser, the fields that vocabulary needs, and a preview applied the way every other change
 * in the interface is (spec 5.2's own closing line).
 *
 * One form and not one per vocabulary, because the tab has one button and one address shape: the
 * Declare button opens it with the chooser unset, and a route naming an entry nothing declares
 * opens it on that route's own kind, pre-filled.
 *
 * No description field for any of the three: `add` takes none, and the entry it writes always
 * states an empty one, which the api supplies itself. It reaches them by two roads - a section's
 * and a raster's through `_declared`, which appends it after the keys `add` requires, and a
 * constant's written into the call in `_constant_plan_of` - so a reader states theirs afterwards
 * whichever was declared, from the panel this form opens onto once it is.
 */
export function SharedAddView(props: SharedAddViewProps) {
  const kind = kindNamed(props.vocabulary);
  return (
    <Panel title={addTitle(kind)} onClose={props.onClose}>
      <div className="declare-fields">
        <ComboBox
          label="Vocabulary"
          inputValue={props.vocabulary}
          onInputChange={props.onVocabulary}
          sections={[
            {
              id: "vocabularies",
              title: "Vocabulary",
              choices: SHARED_VOCABULARIES.map((offered) => ({
                id: vocabularyOf(offered),
                label: vocabularyOf(offered),
                detail: "",
              })),
            },
          ]}
          // The choice's own id is the word the field holds, so picking one from the list and
          // typing it out by hand leave the form in the very same state.
          onPick={props.onVocabulary}
          onEnter={props.onVocabulary}
          onClose={() => undefined}
          isDisabled={props.busy}
        />
        {/* Nothing but the chooser until a vocabulary is chosen: what a reader is asked for
            follows from it, the Name included - shared by all three vocabularies, and belonging
            to none until one is picked. Nothing can be previewed before then either, so a field
            offered under a title naming no vocabulary would be a form with no answer to what it
            would write. What has been typed survives a change of vocabulary - `SharedPage` keeps
            each field's own state - so a reader who chooses again keeps the name they typed. */}
        {kind !== undefined && (
          <label className="panel-field">
            Name
            <input
              type="text"
              value={props.typed}
              disabled={props.busy}
              onChange={(event) => props.onTyped(event.target.value)}
            />
          </label>
        )}
        {/* One arm per vocabulary below, and no arm for a kind none of them names: a fourth
            vocabulary would draw the title, the Name field above, and not one field of its own -
            a form that cannot be filled in. `tsc` does not catch it; `screens/SharedPage.tsx`'s
            panel chain carries the inventory of all four places that fall through this way, and
            the measurement of the one place a fourth word does stop the build. */}
        {kind === "constant" && (
          <label className="panel-field">
            Value
            {/* Text, not a number, for the same reason a constant's own panel gives: `2` and
                `2.0` are two different constants to the format, and a number input cannot tell
                them apart. */}
            <input
              type="text"
              value={props.raw}
              disabled={props.busy}
              onChange={(event) => props.onRaw(event.target.value)}
            />
          </label>
        )}
        {kind === "section" && (
          <>
            {/* Both of a section's required keys, because the model defaults neither
                (`SECTIONS.required`): a section declared without either is one whose file would
                not load, where a constant's `add` needs only its one value. */}
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
              onPick={props.onAccessPicked}
              onEnter={props.onAccessPicked}
              onClose={() => undefined}
              isDisabled={props.busy}
            />
            <label className="panel-field">
              Alignment
              {/* Text, not a number, for the reason the section's own panel gives: the model
                  wants the whole number `4`, and a number input would hand back `4.0`. */}
              <input
                type="text"
                value={props.alignment}
                disabled={props.busy}
                onChange={(event) => props.onAlignment(event.target.value)}
              />
            </label>
          </>
        )}
        {kind === "raster" && (
          <label className="panel-field">
            Event
            {/* The one key a raster's `add` requires (`RASTERS.required`), where a section needs
                two and a constant one: the model defaults `cycle` and `description` both, so a
                raster declared with an event alone is one whose file loads. `cycle` is left to
                the panel this form opens onto for a second reason besides - an event that is not
                cyclic is a real kind of raster rather than an omission, so a field asking for one
                here would be asking for something a reader may rightly have nothing to put in.

                Text, not a number, for the reason Alignment above is: the model wants the whole
                number `3`, and a number input would hand back `3.0`. */}
            <input
              type="text"
              value={props.event}
              disabled={props.busy}
              onChange={(event) => props.onEvent(event.target.value)}
            />
          </label>
        )}
      </div>
      {kind === undefined && (
        <p className="quiet">Choose a vocabulary, and the fields it is declared with follow.</p>
      )}
      {props.refusal !== null && (
        <p className="panel-refusal" role="status">
          {props.refusal}
        </p>
      )}
      {props.refusal === null && props.plan !== null && (
        <p className="consequence">{consequence(props.plan.changes)}</p>
      )}
      {props.refusal === null && props.plan !== null && props.plan.changes.length > 0 && (
        <>
          {props.changesShown && <Changes changes={shownChanges(props.plan.changes)} />}
          <div className="panel-actions">
            <Button variant="link" onPress={() => props.onChangesShown(!props.changesShown)}>
              {props.changesShown ? "Hide changes" : "Show changes"}
            </Button>
            <Button variant="primary" isDisabled={props.busy} onPress={props.onApply}>
              Apply to {props.plan.changes.length} file
              {props.plan.changes.length === 1 ? "" : "s"}
            </Button>
          </div>
        </>
      )}
    </Panel>
  );
}
