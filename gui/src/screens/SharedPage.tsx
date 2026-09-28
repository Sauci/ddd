import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getShared, postEdit } from "../api/client";
import type { State } from "../api/types";
import { SharedAddView } from "../components/SharedAddView";
import { SharedTableView } from "../components/SharedTableView";
import { unreadable } from "../lib/findings";
import type { Route } from "../lib/route";
import {
  constantAdd,
  isDeclared,
  kindNamed,
  planEdit,
  rasterAdd,
  SHARED_KINDS,
  type SharedKind,
  sectionAdd,
  vocabularyOf,
} from "../lib/shared";
import { constantLabel, rasterLabel, sectionLabel } from "../lib/undo";
import { Banner } from "../ui/Banner";
import { ConstantPanel, useConstantPlan } from "./ConstantPanel";
import { RasterPanel, useRasterPlan } from "./RasterPanel";
import { SectionPanel, useSectionPlan } from "./SectionPanel";
import { refusalOf } from "./UnitPanel";

interface Props {
  state: State | null;
  /** The entry whose row is marked, as the address names it - `undefined` for the bare tab. A
   * name the table does not declare under that kind opens the add form pre-filled with it instead
   * of the panel (`isDeclared` decides), which is also what a race resolves to: the entry declared
   * elsewhere between the analysis and the click. */
  name: string | undefined;
  /** Which vocabulary the address says that name belongs to - `undefined` for the bare tab, and
   * for an address that named a kind this page has no vocabulary for (`route.ts` drops it). It is
   * what chooses between the three panels and what `isDeclared` is asked with: read off the route,
   * never guessed from the name's spelling. */
  kind: SharedKind | undefined;
  onName: (name: string | undefined, kind: SharedKind | undefined) => void;
  stopped: boolean;
  /** Following a use's variable, a member's type, or the component declaring a constant inline,
   * without a reload - whichever panel is open, since a section's uses lead to the first of those
   * and a constant's to all three. A raster's lead to the first of them too, and to one no other
   * panel here reaches: a component's own page, where the component measures everything it
   * produces in that raster and there is no variable between the two to open instead. */
  onOpen: (route: Route) => void;
}

/** The open project's Shared files tab (spec 5.1, as this part extends it): every constant, every
 * section and every raster it declares, across the homes each may be declared in, the panel of the
 * one selected, and the form that declares a new one of any of the three. */
export function SharedPage({ state, name, kind, onName, stopped, onOpen }: Props) {
  const revision = state?.revision;
  const shared = useQuery({
    queryKey: ["shared", revision],
    queryFn: () => getShared(),
    // The table stays while the next revision's entries are read: swapped for a loading line on
    // every edit, it lost the reader's place and made the tab flash - as UnitsPage and TypesPage
    // already do.
    placeholderData: (previous) => previous,
  });
  // The entry whose panel closed because nothing declares it any longer (spec 5.4), named above
  // the table until another row is selected or the reader leaves the tab.
  const [gone, setGone] = useState<string | null>(null);
  // Whether the add form is open with nothing pre-filled and no vocabulary chosen, because the
  // reader pressed Declare an entry rather than following a route that already names one.
  const [declaring, setDeclaring] = useState(false);
  const missing = unreadable(state, SHARED_KINDS);

  if (shared.data === undefined) {
    if (shared.isError) return <Banner tone="error">{shared.error.message}</Banner>;
    return <p className="quiet">Reading the project's shared files…</p>;
  }
  const select = (next: string | undefined, nextKind: SharedKind | undefined) => {
    setGone(null);
    setDeclaring(false);
    onName(next, nextKind);
  };
  const declared = name !== undefined && kind !== undefined && isDeclared(shared.data, kind, name);
  // A route naming one nothing declares also opens the add form, pre-filled with that name and
  // with the chooser on the vocabulary the route named (spec: "the add form when the route names
  // one that is not declared"); pressing Declare an entry opens the same form blank, with the
  // chooser unset. Either way the table's own selection (`name`) clears first, so the two states
  // are never both true of the same address.
  const addSeed = declaring ? "" : (name ?? "");
  const addKind = declaring ? undefined : kind;
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
            // Both halves of the address go to the table and both come back: a row is keyed by
            // its vocabulary and its name together, so the row a reader clicked is the row that
            // answers, even where a project declares a constant and a section under one spelling.
            // Every kind the tab lists is a kind an address can name, this part's raster included;
            // a row of one outside `SHARED_VOCABULARIES` would come back `undefined` from
            // `selectionAt`, which leaves the address bare rather than opening another's panel.
            selected={name !== undefined && kind !== undefined ? { kind, name } : undefined}
            onSelect={(next) => select(next?.name, next?.kind)}
            unreadable={missing.own}
            untold={missing.untold}
            onDeclare={() => {
              setGone(null);
              setDeclaring(true);
              onName(undefined, undefined);
            }}
          />
        </div>
        {declared && name !== undefined && kind !== undefined ? (
          // Each vocabulary's own panel, chosen on the route's kind: the three read different
          // replies and write different keys, and the kind is the fact that says which - the
          // entry's own word, answered by the server and carried by the address.
          //
          // A constant's is the fall-through arm, as it was when there were two, and nothing here
          // is checked against `SharedKind` for exhaustiveness - a chain of ternaries registers no
          // complaint from `tsc` for a kind it does not name, and no gate executes this file. A
          // fourth vocabulary would therefore open a constant's panel under its own route until an
          // arm is written for it - and it would reach that route quietly, because the one place a
          // fourth word does stop the build is `SHARED_VOCABULARIES`'s own object literal in
          // `lib/shared.ts`, which `valuesOf` types to force a key per kind. That keeps a new
          // vocabulary out of the chooser until someone names it, and says nothing about here.
          kind === "section" ? (
            <SectionPanel
              key={name}
              name={name}
              revision={revision}
              stopped={stopped}
              onClose={() => onName(undefined, undefined)}
              onGone={() => {
                setGone(name);
                onName(undefined, undefined);
              }}
              // The panel knows its own vocabulary and hands it back, here and in the two arms
              // below. Written out rather than read off the table's rows, because a rename's
              // new spelling is in no row until the next answer arrives: a kind looked up there
              // would find nothing, the address would go bare, and the reader would be put back
              // on the tab instead of onto the panel of what they just renamed.
              onMoved={(moved) => select(moved, moved === undefined ? undefined : "section")}
              onOpen={onOpen}
            />
          ) : kind === "raster" ? (
            <RasterPanel
              key={name}
              name={name}
              revision={revision}
              stopped={stopped}
              onClose={() => onName(undefined, undefined)}
              onGone={() => {
                setGone(name);
                onName(undefined, undefined);
              }}
              onMoved={(moved) => select(moved, moved === undefined ? undefined : "raster")}
              onOpen={onOpen}
            />
          ) : (
            <ConstantPanel
              key={name}
              name={name}
              revision={revision}
              stopped={stopped}
              onClose={() => onName(undefined, undefined)}
              onGone={() => {
                setGone(name);
                onName(undefined, undefined);
              }}
              onMoved={(moved) => select(moved, moved === undefined ? undefined : "constant")}
              onOpen={onOpen}
            />
          )
        ) : (
          (declaring || name !== undefined) && (
            <SharedAdd
              key={`${addKind ?? ""} ${addSeed}`}
              seed={addSeed}
              seedKind={addKind}
              revision={revision}
              stopped={stopped}
              onClose={() => {
                setDeclaring(false);
                onName(undefined, undefined);
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
 * The form that declares a new entry of any of the three vocabularies (design §4.3's `add`),
 * beside the table in the same place an entry's own panel opens: the table's own Declare an entry
 * button, or a route naming an entry nothing declares (`SharedPage`'s own `declared` check chooses
 * between the two). Modelled on `DeclarePanel.tsx`, the codebase's other "declare something new"
 * form - this one never sees spec 5.4's "gone" state, since there is no existing entry for a poll
 * of `GET /api/constant`, `GET /api/section` or `GET /api/raster` to lose.
 */
function SharedAdd({
  seed,
  seedKind,
  revision,
  stopped,
  onClose,
  onAdded,
}: {
  /** What the Name field starts on: an address's own name, or "" for a blank form. */
  seed: string;
  /** Which vocabulary the chooser starts on: an address's own kind, or `undefined` for a form
   * opened by the button, where the reader picks one. */
  seedKind: SharedKind | undefined;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Declared: the tab opens the new entry's own panel, of the vocabulary it was declared into. */
  onAdded: (name: string, kind: SharedKind) => void;
}) {
  const queries = useQueryClient();
  const [vocabulary, setVocabulary] = useState(
    seedKind === undefined ? "" : vocabularyOf(seedKind),
  );
  const [typed, setTyped] = useState(seed);
  const [raw, setRaw] = useState("");
  const [access, setAccess] = useState("");
  const [alignment, setAlignment] = useState("");
  const [event, setEvent] = useState("");
  const [changesShown, setChangesShown] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  // Which vocabulary the chooser has settled on, by the same function the form's own fields
  // follow, so the request built here is always for the kind the reader can see.
  const kind = kindNamed(vocabulary);
  // One request per vocabulary, each `null` while the chooser is on another and until its own
  // fields hold what `add` requires of them - so at most one of the three plans below is ever
  // asked for, none at all while the chooser is unset, and each request stays beside the label an
  // undo of it offers rather than meeting it again later.
  const constantRequest = kind === "constant" ? constantAdd(typed, raw) : null;
  const sectionRequest = kind === "section" ? sectionAdd(typed, access, alignment) : null;
  const rasterRequest = kind === "raster" ? rasterAdd(typed, event) : null;
  const constantPlan = useConstantPlan(constantRequest, revision);
  const sectionPlan = useSectionPlan(sectionRequest, revision);
  const rasterPlan = useRasterPlan(rasterRequest, revision);
  const plan = kind === "section" ? sectionPlan : kind === "raster" ? rasterPlan : constantPlan;
  // The vocabulary being declared into travels with the change rather than being read again when
  // it lands: what is invalidated and which panel opens are then the same choice the plan was
  // made under, and cannot be a later reading of the chooser.
  const apply = useMutation({
    mutationFn: (_declared: SharedKind) => {
      const edit =
        sectionRequest !== null && sectionPlan.data !== undefined
          ? planEdit(sectionPlan.data, sectionLabel(sectionRequest))
          : rasterRequest !== null && rasterPlan.data !== undefined
            ? planEdit(rasterPlan.data, rasterLabel(rasterRequest))
            : constantRequest !== null && constantPlan.data !== undefined
              ? planEdit(constantPlan.data, constantLabel(constantRequest))
              : null;
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setRefusal(null),
    // Declared, the tab moves straight onto the new entry's own panel; the tab's rows and that
    // vocabulary's entries and plans change too, and are asked for again before anything else can
    // be applied. The keys are written from the kind itself rather than named per vocabulary:
    // they are `["constant" | "section" | "raster", ...]` and `["constant-plan" | "section-plan" |
    // "raster-plan", ...]`, the very keys the three panels' hooks above are cached under.
    onSuccess: async (_reply, declared) => {
      await Promise.all([
        queries.invalidateQueries({ queryKey: ["shared"] }),
        queries.invalidateQueries({ queryKey: [declared] }),
        queries.invalidateQueries({ queryKey: [`${declared}-plan`] }),
      ]);
      onAdded(typed, declared);
    },
    onError: (error) => setRefusal(refusalOf(error)),
  });
  return (
    <SharedAddView
      vocabulary={vocabulary}
      onVocabulary={(text) => {
        setVocabulary(text);
        setRefusal(null);
      }}
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
      access={access}
      onAccess={(text) => {
        setAccess(text);
        setRefusal(null);
      }}
      alignment={alignment}
      onAlignment={(text) => {
        setAlignment(text);
        setRefusal(null);
      }}
      event={event}
      onEvent={(text) => {
        setEvent(text);
        setRefusal(null);
      }}
      plan={plan.data ?? null}
      refusal={refusal ?? plan.error?.message ?? null}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => {
        // Never pressed with the chooser unset - the Apply button is drawn under a plan, and no
        // plan is asked for until a vocabulary is chosen - and this is what says so in the types.
        if (kind !== undefined) apply.mutate(kind);
      }}
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}
