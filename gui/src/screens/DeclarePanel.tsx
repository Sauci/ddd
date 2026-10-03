import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  type DeclarationPlanRequest,
  getDeclarable,
  getDeclarationPlan,
  postEdit,
} from "../api/client";
import type { DeclarableReply } from "../api/types";
import { useDebounced } from "../app/useDebounced";
import { DeclarePanelView } from "../components/DeclarePanelView";
import {
  definitionOf,
  dimensionsRaw,
  followedScope,
  type Mode,
  modeOf,
  scopesOf,
} from "../lib/declarations";
import { planEdit } from "../lib/projectUnits";
import { planShown } from "../lib/typing";
import { declareLabel } from "../lib/undo";
import { Banner } from "../ui/Banner";
import { Panel } from "../ui/Panel";
import { refusalOf } from "./UnitPanel";

interface Props {
  /** The component being added to: its absolute, posix-separated path. */
  file: string;
  /** The component's own name, for the label an undo of this declaration will offer. */
  component: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Applied: the component page selects the new declaration's variable. */
  onDeclared: (name: string) => void;
}

/** The plan to ask for from what the form currently says, `null` while there is nothing complete
 * enough to ask one for: no name chosen yet, or - declaring - a required key still unstated. */
function requestOf(
  file: string,
  mode: Mode,
  typed: string,
  kind: string,
  scope: string,
  values: Record<string, string>,
  dimensions: string[],
  reply: DeclarableReply | undefined,
): DeclarationPlanRequest | null {
  if (reply === undefined || mode === "unchosen") return null;
  if (mode === "read") return { action: "read", file, name: typed, scope };
  // The value block's rows have no chooser of their own (`DeclarePanelView`'s own `dimensions`);
  // folded in here under the one key `definitionOf` reads them through, for whichever kind - if
  // any - actually carries a `dimensions` key.
  const raw = dimensionsRaw(dimensions);
  const withDimensions = raw === null ? values : { ...values, dimensions: raw };
  const definition = definitionOf(typed, kind, withDimensions, reply);
  return definition === null ? null : { action: "declare", file, scope, definition };
}

/**
 * The panel that adds a declaration to a component's interface (spec 5.2): the queries, the
 * mutation and the refusals behind `DeclarePanelView`'s picture of its props.
 *
 * One name field rather than two verbs: a name the project already declares reads it, carrying
 * the producer's own keys; a name nobody has declared grows a kind and that kind's keys.
 */
export function DeclarePanel({ file, component, revision, stopped, onClose, onDeclared }: Props) {
  const queries = useQueryClient();
  const declarable = useQuery({
    queryKey: ["declarable", file, revision],
    queryFn: () => getDeclarable(file),
    placeholderData: (previous) => previous,
  });

  // The form's own state - a half-filled declaration is this panel's and nothing else's.
  const [typed, setTyped] = useState("");
  const [kind, setKind] = useState("");
  const [scope, setScope] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  // What is being typed into each key's own field, by key; a key absent means "not typing", and
  // the committed value from `values` shows instead - `DeclarePanelView`'s own `typed_`.
  const [typed_, setTyped_] = useState<Record<string, string | undefined>>({});
  // A value block's rows, kept apart because `dimensions` has no chooser of its own.
  const [dimensions, setDimensions] = useState<string[]>([]);
  const [changesShown, setChangesShown] = useState(false);
  // The one write refused, cleared on the next change of the form - unlike the other panels, this
  // one always closes on success, so there is no later revision for a stale refusal to wait on.
  const [refusal, setRefusal] = useState<string | null>(null);
  // Whether the most recent change to the form was typed into a field, or committed discretely -
  // a key's own chooser, picked or confirmed with Enter (`onValue`, never typing: `DeclarePanelView`'s
  // own `KeyChooser` commits only through `onChosen`, same as every other panel's). Fed to
  // `useDebounced` below so a key's own Enter takes effect at once, the same as every other pick
  // or button on this screen, rather than waiting `PLAN_DELAY_MS` for debouncing the one combined
  // request uniformly (fix round 2's own finding). `dimensions` is left typed, conservatively:
  // `DimensionsField`'s own `onRows` fires for a row typed into as readily as one picked or
  // entered, and does not say which.
  const [typedEdit, setTypedEdit] = useState(true);

  // Scope follows the name (`followedScope`). A name typed moves it in `onTyped` below, as part of
  // that typed change. A new answer of `declarable` - its first, or a revision's - can take the
  // scope chosen away from the name as it stands: moved then, it is a change of the form's own,
  // no keystroke to wait out, and takes effect at once (`typedEdit` false), where it once rode
  // whichever kind the reader's last change had been. Run for a new answer alone, reading the
  // name and the scope as they stand.
  // biome-ignore lint/correctness/useExhaustiveDependencies: run for a new answer alone; typed and scope are read as they stand.
  useEffect(() => {
    if (declarable.data === undefined) return;
    const next = followedScope(scope, scopesOf(typed, declarable.data));
    if (next === scope) return;
    setScope(next);
    setTypedEdit(false);
  }, [declarable.data]);

  const mode = declarable.data === undefined ? "unchosen" : modeOf(typed, declarable.data.names);
  const request = requestOf(file, mode, typed, kind, scope, values, dimensions, declarable.data);
  // The one plan this panel ever asks for, debounced as a whole (spec §6): the name, kind and
  // scope fields each commit on every keystroke (`DeclarePanelView`'s own `ComboBox`es wire
  // `onInputChange` straight to the state `requestOf` reads), so the request above changes on
  // every one of them, not only when a key's own chooser commits a value - `typedEdit` tells
  // `useDebounced` which this latest change was.
  const asked = useDebounced(request, typedEdit);
  const plan = useQuery({
    queryKey: ["declaration-plan", asked, revision],
    queryFn: asked === null ? skipToken : () => getDeclarationPlan(asked),
  });
  // The plan to draw, and why its own fetch was refused if it was - `planShown`'s own,
  // `lib/typing.ts` (review fix round 1): there is no separate `pending` flag here, so a
  // debounced request not yet caught up with what the fields now say, or an answer kept as a
  // placeholder, nulls the plan and its own fetch refusal outright rather than disabling a
  // button.
  const shown = planShown(asked, request, plan);

  const apply = useMutation({
    mutationFn: () => {
      const edit =
        plan.data === undefined || request === null
          ? null
          : planEdit(plan.data, declareLabel(mode, typed, component));
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setRefusal(null),
    // An Apply changes the component's own file, this panel's own queries - whose fingerprints it
    // spent - and what the project's variables are; the tab's table picks the new row up once
    // `["file"]` answers again, and the page moves the reader straight onto it.
    onSuccess: async () => {
      await Promise.all([
        queries.invalidateQueries({ queryKey: ["file"] }),
        queries.invalidateQueries({ queryKey: ["declarable"] }),
        queries.invalidateQueries({ queryKey: ["declaration-plan"] }),
      ]);
      onDeclared(typed);
    },
    onError: (error) => setRefusal(refusalOf(error)),
  });

  if (declarable.isError) {
    return (
      <Panel title="Add a declaration" onClose={onClose}>
        <Banner tone="error">{declarable.error.message}</Banner>
      </Panel>
    );
  }
  if (declarable.data === undefined) {
    return (
      <Panel title="Add a declaration" onClose={onClose}>
        <p className="quiet">Reading the file…</p>
      </Panel>
    );
  }
  const reply = declarable.data;
  return (
    <DeclarePanelView
      reply={reply}
      typed={typed}
      kind={kind}
      scope={scope}
      values={values}
      typed_={typed_}
      dimensions={dimensions}
      plan={shown.plan}
      refusal={refusal ?? shown.refusal}
      changesShown={changesShown}
      busy={stopped || apply.isPending}
      onTyped={(text) => {
        setTyped(text);
        setScope((current) => followedScope(current, scopesOf(text, reply)));
        setTypedEdit(true);
        setRefusal(null);
      }}
      onKind={(next) => {
        setKind(next);
        setTypedEdit(true);
        setRefusal(null);
      }}
      onScope={(next) => {
        setScope(next);
        setTypedEdit(true);
        setRefusal(null);
      }}
      onValue={(key, raw) => {
        setValues((current) => ({ ...current, [key]: raw }));
        setTypedEdit(false);
        setRefusal(null);
      }}
      onTyped_={(key, text) => setTyped_((current) => ({ ...current, [key]: text }))}
      onDimensions={(rows) => {
        setDimensions(rows);
        setTypedEdit(true);
        setRefusal(null);
      }}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      onClose={onClose}
    />
  );
}
