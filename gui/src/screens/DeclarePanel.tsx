import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  type DeclarationPlanRequest,
  getDeclarable,
  getDeclarationPlan,
  postEdit,
} from "../api/client";
import type { DeclarableReply } from "../api/types";
import { DeclarePanelView } from "../components/DeclarePanelView";
import { definitionOf, dimensionsRaw, type Mode, modeOf, scopesOf } from "../lib/declarations";
import { planEdit } from "../lib/projectUnits";
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

/** What this declaration is called when it comes to be undone - the verb the mode settled on,
 * naming the variable and the component it joins: "reading ValueC into Controller", "declaring
 * Pressure in Controller". */
function declareLabel(mode: Mode, typed: string, component: string): string {
  return mode === "read"
    ? `reading ${typed} into ${component}`
    : `declaring ${typed} in ${component}`;
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

  // Scope follows the name: a scope the newly typed (or newly loaded) name may not take is not
  // kept, and moves forward onto the first this name does take. Typing between two names that
  // both allow the scope already chosen leaves it exactly as it was - this only ever moves it
  // forward, never back onto a scope let go of for a name typed in between.
  useEffect(() => {
    if (declarable.data === undefined) return;
    const scopes = scopesOf(typed, declarable.data);
    setScope((current) => (scopes.includes(current) ? current : (scopes[0] ?? "")));
  }, [typed, declarable.data]);

  const mode = declarable.data === undefined ? "unchosen" : modeOf(typed, declarable.data.names);
  const request = requestOf(file, mode, typed, kind, scope, values, dimensions, declarable.data);
  const plan = useQuery({
    queryKey: ["declaration-plan", request, revision],
    queryFn: request === null ? skipToken : () => getDeclarationPlan(request),
  });

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
  return (
    <DeclarePanelView
      reply={declarable.data}
      typed={typed}
      kind={kind}
      scope={scope}
      values={values}
      typed_={typed_}
      dimensions={dimensions}
      plan={plan.data ?? null}
      refusal={refusal ?? plan.error?.message ?? null}
      changesShown={changesShown}
      busy={stopped || apply.isPending}
      onTyped={(text) => {
        setTyped(text);
        setRefusal(null);
      }}
      onKind={(next) => {
        setKind(next);
        setRefusal(null);
      }}
      onScope={(next) => {
        setScope(next);
        setRefusal(null);
      }}
      onValue={(key, raw) => {
        setValues((current) => ({ ...current, [key]: raw }));
        setRefusal(null);
      }}
      onTyped_={(key, text) => setTyped_((current) => ({ ...current, [key]: text }))}
      onDimensions={(rows) => {
        setDimensions(rows);
        setRefusal(null);
      }}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      onClose={onClose}
    />
  );
}
