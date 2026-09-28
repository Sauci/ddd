import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { type ConstantPlanRequest, getShared, postEdit } from "../api/client";
import type { State } from "../api/types";
import { ConstantAddView } from "../components/ConstantPanelView";
import { SharedTableView } from "../components/SharedTableView";
import { unreadable } from "../lib/findings";
import type { Route } from "../lib/route";
import { isDeclared, planEdit } from "../lib/shared";
import { constantLabel } from "../lib/undo";
import { Banner } from "../ui/Banner";
import { ConstantPanel, useConstantPlan } from "./ConstantPanel";
import { refusalOf } from "./UnitPanel";

interface Props {
  state: State | null;
  /** The constant whose row is marked, as the address names it - `undefined` for the bare tab. A
   * name the table does not declare opens the add form pre-filled with it instead of the panel
   * (`isDeclared` decides), which is also what a race resolves to: the constant declared
   * elsewhere between the analysis and the click. */
  name: string | undefined;
  onName: (name: string | undefined) => void;
  stopped: boolean;
  /** Following a use's variable, a member's type, or the component declaring a constant inline,
   * without a reload. */
  onOpen: (route: Route) => void;
}

/** The open project's Shared files tab (spec 5.1): every constant it declares, across both homes
 * one may be declared in, the panel of the one selected, and the form that declares a new one. */
export function SharedPage({ state, name, onName, stopped, onOpen }: Props) {
  const revision = state?.revision;
  const shared = useQuery({
    queryKey: ["shared", revision],
    queryFn: () => getShared(),
    // The table stays while the next revision's entries are read: swapped for a loading line on
    // every edit, it lost the reader's place and made the tab flash - as UnitsPage and TypesPage
    // already do.
    placeholderData: (previous) => previous,
  });
  // The constant whose panel closed because nothing declares it any longer (spec 5.4), named
  // above the table until another row is selected or the reader leaves the tab.
  const [gone, setGone] = useState<string | null>(null);
  // Whether the add form is open with nothing pre-filled, because the reader pressed "Declare a
  // constant" rather than following a route that already names one.
  const [declaring, setDeclaring] = useState(false);
  const missing = unreadable(state, ["constants"]);

  if (shared.data === undefined) {
    if (shared.isError) return <Banner tone="error">{shared.error.message}</Banner>;
    return <p className="quiet">Reading the project's shared files…</p>;
  }
  const select = (next: string | undefined) => {
    setGone(null);
    setDeclaring(false);
    onName(next);
  };
  const declared = name !== undefined && isDeclared(shared.data, "constant", name);
  // A route naming one nothing declares also opens the add form, pre-filled with that name
  // (spec: "the add form when the route names one that is not declared"); pressing Declare a
  // constant opens the same form blank. Either way the table's own selection (`name`) clears
  // first, so the two states are never both true of the same address.
  const addSeed = declaring ? "" : (name ?? "");
  return (
    <>
      {/* A server that stopped answering leaves the table as it was, and says so above it. */}
      {shared.isError && <Banner tone="error">{shared.error.message}</Banner>}
      {gone !== null && (
        <Banner tone="warning">{gone} is no longer declared in the open project.</Banner>
      )}
      <div className={name !== undefined || declaring ? "with-panel" : undefined}>
        <div>
          <SharedTableView
            reply={shared.data}
            selected={name}
            onSelect={select}
            unreadable={missing.own}
            untold={missing.untold}
            onDeclare={() => {
              setGone(null);
              setDeclaring(true);
              onName(undefined);
            }}
          />
        </div>
        {declared && name !== undefined ? (
          <ConstantPanel
            key={name}
            name={name}
            revision={revision}
            stopped={stopped}
            onClose={() => onName(undefined)}
            onGone={() => {
              setGone(name);
              onName(undefined);
            }}
            onMoved={select}
            onOpen={onOpen}
          />
        ) : (
          (declaring || name !== undefined) && (
            <ConstantAdd
              key={addSeed}
              seed={addSeed}
              revision={revision}
              stopped={stopped}
              onClose={() => {
                setDeclaring(false);
                onName(undefined);
              }}
              onAdded={select}
            />
          )
        )}
      </div>
    </>
  );
}

/**
 * The form that declares a new constant (design §4.3's `add`), beside the table in the same
 * place a constant's own panel opens: the table's own Declare a constant button, or a route
 * naming a constant nothing declares (`SharedPage`'s own `declared` check chooses between the
 * two). Modelled on `DeclarePanel.tsx`, the codebase's other "declare something new" form - this
 * one never sees spec 5.4's "gone" state, since there is no existing entry for a poll of
 * `GET /api/constant` to lose.
 */
function ConstantAdd({
  seed,
  revision,
  stopped,
  onClose,
  onAdded,
}: {
  /** What the Name field starts on: an address's own name, or "" for a blank form. */
  seed: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Declared: the tab opens the new constant's own panel. */
  onAdded: (name: string) => void;
}) {
  const queries = useQueryClient();
  const [typed, setTyped] = useState(seed);
  const [raw, setRaw] = useState("");
  const [changesShown, setChangesShown] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  // `add`'s own `raw` is one of its required parameters, unlike `set`'s (`ConstantPlanRequest`'s
  // own doc): nothing is asked for until both fields hold something, since a name with no value
  // yet is not a request the api takes, and asking anyway would only ever come back
  // `bad-request` for a reader who has not finished typing.
  const request: ConstantPlanRequest | null =
    typed.trim() === "" || raw.trim() === "" ? null : { action: "add", name: typed, raw };
  const plan = useConstantPlan(request, revision);
  const apply = useMutation({
    mutationFn: () => {
      const edit =
        plan.data === undefined || request === null
          ? null
          : planEdit(plan.data, constantLabel(request));
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setRefusal(null),
    // Declared, the tab moves straight onto the new constant's own panel; its rows and every
    // constant plan change too, and are asked for again before anything else can be applied.
    onSuccess: async () => {
      await Promise.all([
        queries.invalidateQueries({ queryKey: ["shared"] }),
        queries.invalidateQueries({ queryKey: ["constant"] }),
        queries.invalidateQueries({ queryKey: ["constant-plan"] }),
      ]);
      onAdded(typed);
    },
    onError: (error) => setRefusal(refusalOf(error)),
  });
  return (
    <ConstantAddView
      typed={typed}
      onTyped={(text) => {
        setTyped(text);
        setRefusal(null);
      }}
      raw={raw}
      onRaw={(text) => {
        setRaw(text);
        setRefusal(null);
      }}
      plan={plan.data ?? null}
      refusal={refusal ?? plan.error?.message ?? null}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}
