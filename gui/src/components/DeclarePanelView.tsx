import type { DeclarableReply, PlanReply, UnitsReply } from "../api/types";
import { declareSentence, keysOf, modeOf, scopesOf } from "../lib/declarations";
import { shownChanges } from "../lib/units";
import { shortValue } from "../lib/variableKeys";
import { Button } from "../ui/Button";
import { ComboBox } from "../ui/ComboBox";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";
import { DimensionsField } from "./DimensionsField";
import { KeyChooser } from "./KeyChooser";

export interface DeclarePanelViewProps {
  reply: DeclarableReply;
  /** What the name field holds: a listed name, a new one, or nothing yet. */
  typed: string;
  kind: string;
  scope: string;
  /** The json text of each key the form has stated, by key. */
  values: Record<string, string>;
  /** What is being typed into each key's field, by key; a key absent means "not typing", and
   * the committed value from `values` shows instead. */
  typed_: Record<string, string | undefined>;
  /** A value block's rows, kept apart because `dimensions` has no chooser. */
  dimensions: string[];
  plan: PlanReply | null;
  refusal: string | null;
  changesShown: boolean;
  busy: boolean;
  onTyped: (typed: string) => void;
  onKind: (kind: string) => void;
  onScope: (scope: string) => void;
  onValue: (key: string, raw: string) => void;
  onTyped_: (key: string, text: string | undefined) => void;
  onDimensions: (rows: string[]) => void;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  onClose: () => void;
}

/** How the page words each scope, as `lib/declarations.ts`'s own `ROLE` words it for the
 * consequence sentence - kept here too, the way `TypePanelView`'s `KIND_WORDS` keeps
 * `projectTypes.ts`'s three words rather than importing them for one field. */
const SCOPE_WORDS: Record<string, string> = {
  output: "produces",
  input: "reads",
  local: "keeps to itself",
};

const NOTHING = "state nothing";

/** The label a key's field shows for its committed value, `shortValue`'s own wording - the same
 * idea `labelOfRaw` reads for an existing variable's chooser, adapted for `values`' "absent
 * means unstated" instead of a `VariableReply` to read `null` from: a declaration being drafted
 * has none yet. */
function labelOf(key: string, raw: string | undefined): string {
  return raw === undefined || raw === "" ? NOTHING : shortValue(key, raw);
}

/** `KeyChooser`'s `unit` and `limits` editors never appear in this form - `keysOf` excludes both
 * keys, since no kind requires either to become a loadable declaration (`declarations.ts`) - so
 * these satisfy its props' types without ever being read. */
const NO_UNITS: UnitsReply = {
  revision: 0,
  vocabulary: null,
  used: [],
  units: [],
  adoptable: null,
};
const NO_RANGE = { min: "", max: "" };
/** A declaration being drafted has nothing else stating it yet. */
const NOTHING_IN_PLAY = new Map<string | null, string[]>();

/** The panel that adds a declaration (spec 5.2), drawn from what the api answered: a picture of
 * its props. One name field rather than two verbs: a listed name reads, with the producer's own
 * keys; a name nobody has declared grows a kind and that kind's keys. */
export function DeclarePanelView(props: DeclarePanelViewProps) {
  const { reply } = props;
  const mode = modeOf(props.typed, reply.names);
  return (
    <Panel title="Add a declaration" onClose={props.onClose}>
      <div className="declare-fields">
        <ComboBox
          label="Name"
          inputValue={props.typed}
          onInputChange={props.onTyped}
          sections={[
            {
              id: "names",
              title: "This project's variables",
              choices: reply.names.map((entry) => ({
                id: entry.name,
                label: entry.name,
                detail: `${entry.kind} from ${entry.producer ?? "no producer"}`,
              })),
            },
          ]}
          onPick={props.onTyped}
          onEnter={props.onTyped}
          onClose={() => undefined}
          isDisabled={props.busy}
        />
        <ComboBox
          label="Scope"
          inputValue={SCOPE_WORDS[props.scope] ?? props.scope}
          onInputChange={props.onScope}
          sections={[
            {
              id: "scopes",
              title: "Scope",
              choices: scopesOf(props.typed, reply).map((scope) => ({
                id: scope,
                label: SCOPE_WORDS[scope] ?? scope,
                detail: "",
              })),
            },
          ]}
          onPick={props.onScope}
          onEnter={props.onScope}
          onClose={() => undefined}
          isDisabled={props.busy}
        />
        {mode === "declare" && (
          <>
            <ComboBox
              label="Kind"
              inputValue={props.kind}
              onInputChange={props.onKind}
              sections={[
                {
                  id: "kinds",
                  title: "Kind",
                  choices: reply.kinds.map((entry) => ({
                    id: entry.kind,
                    label: entry.kind,
                    detail: "",
                  })),
                },
              ]}
              onPick={props.onKind}
              onEnter={props.onKind}
              onClose={() => undefined}
              isDisabled={props.busy}
            />
            {keysOf(props.kind, reply).map((key) =>
              key.key === "dimensions" ? (
                <DimensionsField
                  key={key.key}
                  rows={props.dimensions}
                  constants={key.choices}
                  owner={props.typed}
                  busy={props.busy}
                  onRows={props.onDimensions}
                />
              ) : (
                <KeyChooser
                  key={key.key}
                  offer={key}
                  owner={props.typed}
                  inPlay={NOTHING_IN_PLAY}
                  keyName={key.key}
                  units={NO_UNITS}
                  typed={props.typed_[key.key] ?? labelOf(key.key, props.values[key.key])}
                  narrow={props.typed_[key.key] ?? ""}
                  onTyped={(text) => props.onTyped_(key.key, text)}
                  onChosen={(raw) => {
                    props.onValue(key.key, raw ?? "");
                    props.onTyped_(key.key, undefined);
                  }}
                  onPickerClosed={() => props.onTyped_(key.key, undefined)}
                  range={NO_RANGE}
                  onRange={() => undefined}
                  note={undefined}
                  busy={props.busy}
                  focus={null}
                  pickerTrigger={undefined}
                />
              ),
            )}
          </>
        )}
      </div>
      <p className="consequence">{declareSentence(props.typed, props.kind, props.scope, reply)}</p>
      {props.refusal !== null && (
        <p className="panel-refusal" role="status">
          {props.refusal}
        </p>
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
