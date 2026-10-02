import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getSection,
  getSectionPlan,
  postEdit,
  type SectionPlanRequest,
} from "../api/client";
import { useUpdating } from "../app/updating";
import { useDebounced } from "../app/useDebounced";
import { type Offer, type SectionAction, SectionPanelView } from "../components/SectionPanelView";
import { panelShows, type Refused, shownRefusal } from "../lib/refusals";
import type { Route } from "../lib/route";
import { planEdit, sectionSet } from "../lib/shared";
import { planShown } from "../lib/typing";
import { sectionLabel } from "../lib/undo";
import { Banner } from "../ui/Banner";
import { Panel } from "../ui/Panel";
import { UpdatingNote } from "../ui/UpdatingNote";
import { refusalOf } from "./UnitPanel";

interface Props {
  name: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Nothing in the open project declares the section: the tab closes the panel, saying why. */
  onGone: () => void;
  /** Renamed or removed from this panel: the tab opens the new spelling's panel, or none. */
  onMoved: (name: string | undefined) => void;
  /** Following a definition to the variable placing its data here, without a reload. */
  onOpen: (route: Route) => void;
}

/**
 * One plan, asked for again at every revision - an Apply spends the fingerprints it carries - and
 * not asked for at all while `request` is `null`.
 *
 * Its own hook, keyed `["section-plan", ...]` rather than a widening of `ConstantPanel`'s
 * `useConstantPlan` (keyed `["constant-plan", ...]`): the keys have to differ so that invalidating
 * one vocabulary's plans on an edit does not throw away the other's, and a generic wide enough for
 * both requests would be a bigger change than one more hook.
 *
 * Keeps no placeholder while the next is asked for: each of the section's three keys - the
 * access among them, its chooser taking typed text as well as a pick - is debounced before
 * `request` ever reaches this hook (`useDebounced`, spec §6), and `planShown` (`lib/typing.ts`)
 * never trusts a placeholder's own answer, so one kept here would never be drawn - a `keep`
 * option once did exactly that (fix round 2's own finding), which is why there is none now.
 */
export function useSectionPlan(request: SectionPlanRequest | null, revision: number | undefined) {
  return useQuery({
    queryKey: ["section-plan", request, revision],
    queryFn: request === null ? skipToken : () => getSectionPlan(request),
  });
}

/** One section's panel: its access, alignment and description, the file declaring it, every
 * definition placing data in it, its findings, and a spelling to rename it to (spec 5.2). */
export function SectionPanel({ name, revision, stopped, onClose, onGone, onMoved, onOpen }: Props) {
  const queries = useQueryClient();
  const updating = useUpdating();
  const reply = useQuery({
    queryKey: ["section", name, revision],
    queryFn: () => getSection(name),
    placeholderData: (previous) => previous,
  });
  // Set once this panel renamed or removed its section: it is then gone because the reader asked,
  // and the panel moves on without the tab saying that it disappeared.
  const moving = useRef(false);
  // Spec 5.4: a section renamed or removed from outside - or named by an address nothing
  // declares, such as an old bookmark - is gone, and its panel closes, the tab saying why. While
  // a file does not load the server cannot say that, and answers `unreadable` instead: the panel
  // then stays, naming the file, and shows the section again once the file loads.
  const gone = reply.error instanceof ApiError && reply.error.code === "not-found";
  useEffect(() => {
    if (gone && !moving.current) onGone();
  }, [gone, onGone]);

  // What the reader has chosen or typed into the three fields, `undefined` until they do: each
  // field then reads the entry's own text.
  const [access, setAccess] = useState<string | undefined>(undefined);
  const [alignment, setAlignment] = useState<string | undefined>(undefined);
  const [description, setDescription] = useState<string | undefined>(undefined);
  // The spelling chosen to rename the section to, `null` until one is typed.
  const [to, setTo] = useState<string | null>(null);
  const [shown, setShown] = useState<SectionAction | null>(null);
  // The one action refused for a reason other than staleness, if any: cleared whenever the
  // reader chooses again, exactly as `ConstantPanel`'s own.
  const [failed, setFailed] = useState<{ action: SectionAction; message: string } | null>(null);
  // The one action refused because a file changed on disk, and the revision it happened at -
  // held until a later revision arrives, exactly as `ConstantPanel`'s own `staleFailed`.
  const [staleFailed, setStaleFailed] = useState<({ action: SectionAction } & Refused) | null>(
    null,
  );

  // What the panel shows of that answer (`panelShows`): a section just added or renamed is refused
  // until its file is analysed again, and the panel says the findings are updating meanwhile.
  const answer = panelShows(reply, (shown) => shown.name, name, updating);
  const entry = answer.shown === "reply" ? answer.reply : undefined;
  const draftAccess = access !== undefined && access !== entry?.access ? access : null;
  const draftAlignment =
    alignment !== undefined && alignment !== entry?.alignment ? alignment : null;
  const draftDescription =
    description !== undefined && description !== entry?.description ? description : null;
  // Named before the plans that ask for them, so that applying one can say what it was: the label
  // an undo of this edit will offer comes from the same request the preview was made from.
  //
  // `Record<SectionAction, …>` is what keeps `requests[action]` typed at the call sites below and
  // forces an entry for every action; the `satisfies` clause beside it is what ties each entry to
  // its own key. `Record` alone accepts `describe`'s request under `access` just as readily, and
  // nothing in this repo executes a `.tsx` file under a gate: the panel would then write a
  // description where the Access field was saved, and label the undo "the description of X". The
  // three `set` arms are the ones that can swap silently, `SectionAction` not being 1:1 with the
  // request's own `action` - all three are `set`, told apart by `key` alone - which is why it is
  // the `key` literal each of them is pinned to here. Each goes through `sectionSet`, which is
  // what carries that one literal to the request and to the quoting alike: a key spelled twice
  // here could be spelled differently twice, and an alignment quoted like a string is a refusal
  // the reader did nothing to earn (fix round 1).
  const requests: Record<SectionAction, SectionPlanRequest | null> = {
    access: draftAccess === null ? null : sectionSet(name, "access", draftAccess),
    alignment: draftAlignment === null ? null : sectionSet(name, "alignment", draftAlignment),
    describe: draftDescription === null ? null : sectionSet(name, "description", draftDescription),
    rename: to === null ? null : { action: "rename", name, to },
    // Asked for only while nothing places its data in the section: a definition still naming it
    // always refuses (design §4.5), and a control that would refuse the instant it was pressed is
    // a lying button. The last section a file declares is asked for like any other, since the
    // file it leaves declaring nothing still loads.
    remove: entry !== undefined && entry.uses.length === 0 ? { action: "remove", name } : null,
  } satisfies {
    access: (Extract<SectionPlanRequest, { action: "set" }> & { key: "access" }) | null;
    alignment: (Extract<SectionPlanRequest, { action: "set" }> & { key: "alignment" }) | null;
    describe: (Extract<SectionPlanRequest, { action: "set" }> & { key: "description" }) | null;
    rename: Extract<SectionPlanRequest, { action: "rename" }> | null;
    remove: Extract<SectionPlanRequest, { action: "remove" }> | null;
  };
  // Access, alignment, description and rename each commit on every keystroke - access through
  // its own chooser, which takes typed text like every other field here (`useSectionPlan`'s own
  // doc) - so each is debounced on its own (spec §6): a field's first ask is immediate, and only
  // one asked of before waits. Remove is never typed into - it is offered outright once nothing
  // places data in the section any longer - so `asked.remove` is `requests.remove` itself.
  const asked: Record<SectionAction, SectionPlanRequest | null> = {
    access: useDebounced(requests.access),
    alignment: useDebounced(requests.alignment),
    describe: useDebounced(requests.describe),
    rename: useDebounced(requests.rename),
    remove: requests.remove,
  };
  const plans = {
    access: useSectionPlan(asked.access, revision),
    alignment: useSectionPlan(asked.alignment, revision),
    describe: useSectionPlan(asked.describe, revision),
    rename: useSectionPlan(asked.rename, revision),
    remove: useSectionPlan(asked.remove, revision),
  };
  const apply = useMutation({
    mutationFn: (action: SectionAction) => {
      const plan = plans[action].data;
      const request = requests[action];
      const edit =
        plan === undefined || request === null ? null : planEdit(plan, sectionLabel(request));
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setFailed(null),
    // Renamed, the section is the new spelling now, and the tab opens its panel; removed, it is
    // gone as the reader asked. Neither is the section disappearing that spec 5.4 has the tab
    // announce. A success is a definite answer, so it also clears a stale wait left over from an
    // earlier attempt at this same action - `onMutate` above only ever clears the other refusal.
    onSuccess: (_reply, action) => {
      setStaleFailed(null);
      setShown(null);
      if (action === "rename" && to !== null) {
        moving.current = true;
        onMoved(to);
      } else if (action === "remove") {
        moving.current = true;
        onMoved(undefined);
      }
    },
    // Stale is the one refusal that waits for a later revision rather than clearing; setting one
    // kind clears the other, so an action never shows two different answers to the same Apply.
    onError: (error, action) => {
      if (error instanceof ApiError && error.code === "stale") {
        setStaleFailed({ action, text: refusalOf(error), revision });
        setFailed(null);
      } else {
        setFailed({ action, message: refusalOf(error) });
        setStaleFailed(null);
      }
    },
    // An Apply changes the section's own entry or every definition naming it, the tab's rows and
    // every section plan, whose fingerprints it spent: they are asked for again, and nothing can
    // be applied until they answer. A field saved is let go only then, so it goes from what was
    // typed straight to the entry's new text, and never back through the old one.
    onSettled: async (_reply, error, action) => {
      await Promise.all([
        queries.invalidateQueries({ queryKey: ["shared"] }),
        queries.invalidateQueries({ queryKey: ["section"] }),
        queries.invalidateQueries({ queryKey: ["section-plan"] }),
      ]);
      if (error === null && action === "access") setAccess(undefined);
      if (error === null && action === "alignment") setAlignment(undefined);
      if (error === null && action === "describe") setDescription(undefined);
    },
  });
  /** Where a change stands: its plan, and why it was refused - on Apply, else when asked for.
   * `plan`/`refusal`/`pending` are `planShown`'s own, `lib/typing.ts` (review fix round 1):
   * `null`/`null`/pending while the debounced request has not caught up with what the fields now
   * say, or while the answer is an earlier request's kept as a placeholder - never a plan, nor
   * its own fetch refusal, for text the reader has since typed past. A stale or a plain apply
   * failure takes precedence, as it always did. */
  const offer = (action: SectionAction): Offer => {
    const shown = planShown(asked[action], requests[action], plans[action]);
    return {
      plan: shown.plan,
      refusal:
        staleFailed?.action === action
          ? shownRefusal(staleFailed, revision)
          : failed?.action === action
            ? failed.message
            : shown.refusal,
      pending: shown.pending,
    };
  };

  if (gone) return null;
  if (answer.shown === "refusal") {
    return (
      <Panel title={name} onClose={onClose}>
        <Banner tone="error">{answer.refusal}</Banner>
      </Panel>
    );
  }
  if (answer.shown === "updating") {
    return (
      <Panel title={name} onClose={onClose}>
        <UpdatingNote />
      </Panel>
    );
  }
  if (entry === undefined) {
    return (
      <Panel title={name} onClose={onClose}>
        <p className="quiet">Reading {name}…</p>
      </Panel>
    );
  }
  return (
    <SectionPanelView
      reply={entry}
      updating={updating}
      access={access ?? entry.access}
      onAccess={(text) => {
        setAccess(text);
        setFailed(null);
      }}
      alignment={alignment ?? entry.alignment}
      onAlignment={(text) => {
        setAlignment(text);
        setFailed(null);
      }}
      description={description ?? entry.description}
      onDescription={(text) => {
        setDescription(text);
        setFailed(null);
      }}
      renameTo={to}
      onRenameTo={(next) => {
        setTo(next);
        setFailed(null);
      }}
      accessOffer={draftAccess === null ? null : offer("access")}
      alignmentOffer={draftAlignment === null ? null : offer("alignment")}
      describeOffer={draftDescription === null ? null : offer("describe")}
      renameOffer={to === null ? null : offer("rename")}
      removeOffer={requests.remove === null ? null : offer("remove")}
      shown={shown}
      onShown={setShown}
      onApply={(action) => apply.mutate(action)}
      onOpen={onOpen}
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}
