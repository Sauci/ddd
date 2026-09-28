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
  /** What the Alignment field holds: the whole number of bytes a section guarantees. */
  alignment: string;
  onAlignment: (text: string) => void;
  plan: PlanReply | null;
  refusal: string | null;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  busy: boolean;
  onClose: () => void;
}

/**
 * The form that declares a new entry of either vocabulary (design §4.3's `add`): the chooser, the
 * fields that vocabulary needs, and a preview applied the way every other change in the interface
 * is (spec 5.2's own closing line).
 *
 * One form and not one per vocabulary, because the tab has one button and one address shape: the
 * Declare button opens it with the chooser unset, and a route naming an entry nothing declares
 * opens it on that route's own kind, pre-filled.
 *
 * No description field for either kind: `add` takes none, and the entry it writes always states an
 * empty one - the api supplies it itself (`_declared`), for both vocabularies - so a reader states
 * theirs afterwards, from the panel this form opens onto once it is declared.
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
            follows from it, the Name included - shared by both vocabularies, and belonging to
            neither until one is picked. Nothing can be previewed before then either, so a field
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
              onPick={props.onAccess}
              onEnter={props.onAccess}
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
