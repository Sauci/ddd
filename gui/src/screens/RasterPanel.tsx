import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getRaster,
  getRasterPlan,
  postEdit,
  type RasterPlanRequest,
} from "../api/client";
import { useUpdating } from "../app/updating";
import { useDebounced } from "../app/useDebounced";
import { type Offer, type RasterAction, RasterPanelView } from "../components/RasterPanelView";
import { panelShows, type Refused, shownRefusal } from "../lib/refusals";
import type { Route } from "../lib/route";
import { planEdit, rasterRemovable, rasterSet } from "../lib/shared";
import { sameRequest } from "../lib/typing";
import { rasterLabel } from "../lib/undo";
import { Banner } from "../ui/Banner";
import { Panel } from "../ui/Panel";
import { UpdatingNote } from "../ui/UpdatingNote";
import { refusalOf } from "./UnitPanel";

interface Props {
  name: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Nothing in the open project declares the raster: the tab closes the panel, saying why. */
  onGone: () => void;
  /** Renamed or removed from this panel: the tab opens the new spelling's panel, or none. */
  onMoved: (name: string | undefined) => void;
  /** Following a use to the variable measured here, or to the component whose default this is,
   * without a reload. */
  onOpen: (route: Route) => void;
}

/**
 * One plan, asked for again at every revision - an Apply spends the fingerprints it carries - and
 * not asked for at all while `request` is `null`.
 *
 * Its own hook, keyed `["raster-plan", ...]` rather than a widening of `SectionPanel`'s
 * `useSectionPlan` (keyed `["section-plan", ...]`), for the reason that one is not a widening of
 * `useConstantPlan`: the keys have to differ so that invalidating one vocabulary's plans on an
 * edit does not throw away another's, and a generic wide enough for three requests would be a
 * bigger change than one more hook. `SharedPage`'s own add form relies on that spelling too - it
 * invalidates `` [`${declared}-plan`] `` from the kind itself, which is this key exactly.
 *
 * `keep` leaves the last plan on screen while the next is asked for, marked as a placeholder, for
 * each of the raster's three keys: all three are debounced before `request` ever reaches this
 * hook (`useDebounced`, spec §6), so it changes once the reader pauses rather than with every key
 * - but without `keep`, the line saying which file it changes would still blink away each time it
 * does.
 */
export function useRasterPlan(
  request: RasterPlanRequest | null,
  revision: number | undefined,
  keep = false,
) {
  return useQuery({
    queryKey: ["raster-plan", request, revision],
    queryFn: request === null ? skipToken : () => getRasterPlan(request),
    placeholderData: (previous) => (keep ? previous : undefined),
  });
}

/** One raster's panel: its event, cycle and description, the file declaring it, every shape
 * naming it - a definition measured in it or a component measuring everything it produces in it -
 * its findings, and a spelling to rename it to (spec 5.2). */
export function RasterPanel({ name, revision, stopped, onClose, onGone, onMoved, onOpen }: Props) {
  const queries = useQueryClient();
  const updating = useUpdating();
  const reply = useQuery({
    queryKey: ["raster", name, revision],
    queryFn: () => getRaster(name),
    placeholderData: (previous) => previous,
  });
  // Set once this panel renamed or removed its raster: it is then gone because the reader asked,
  // and the panel moves on without the tab saying that it disappeared.
  const moving = useRef(false);
  // Spec 5.4: a raster renamed or removed from outside - or named by an address nothing declares,
  // such as an old bookmark - is gone, and its panel closes, the tab saying why. While a file does
  // not load the server cannot say that, and answers `unreadable` instead: the panel then stays,
  // naming the file, and shows the raster again once the file loads.
  const gone = reply.error instanceof ApiError && reply.error.code === "not-found";
  useEffect(() => {
    if (gone && !moving.current) onGone();
  }, [gone, onGone]);

  // What the reader has typed into the three fields, `undefined` until they do: each field then
  // reads the entry's own text.
  const [event, setEvent] = useState<string | undefined>(undefined);
  const [cycle, setCycle] = useState<string | undefined>(undefined);
  const [description, setDescription] = useState<string | undefined>(undefined);
  // The spelling chosen to rename the raster to, `null` until one is typed.
  const [to, setTo] = useState<string | null>(null);
  const [shown, setShown] = useState<RasterAction | null>(null);
  // The one action refused for a reason other than staleness, if any: cleared whenever the reader
  // types again, exactly as `SectionPanel`'s own.
  const [failed, setFailed] = useState<{ action: RasterAction; message: string } | null>(null);
  // The one action refused because a file changed on disk, and the revision it happened at - held
  // until a later revision arrives, exactly as `SectionPanel`'s own `staleFailed`.
  const [staleFailed, setStaleFailed] = useState<({ action: RasterAction } & Refused) | null>(null);

  // What the panel shows of that answer (`panelShows`): a raster just added or renamed is refused
  // until its file is analysed again, and the panel says the findings are updating meanwhile.
  const answer = panelShows(reply, (shown) => shown.name, name, updating);
  const entry = answer.shown === "reply" ? answer.reply : undefined;
  const draftEvent = event !== undefined && event !== entry?.event ? event : null;
  const draftCycle = cycle !== undefined && cycle !== entry?.cycle ? cycle : null;
  const draftDescription =
    description !== undefined && description !== entry?.description ? description : null;
  // Named before the plans that ask for them, so that applying one can say what it was: the label
  // an undo of this edit will offer comes from the same request the preview was made from.
  //
  // `Record<RasterAction, …>` is what keeps `requests[action]` typed at the call sites below and
  // forces an entry for every action; the `satisfies` clause beside it is what ties each entry to
  // its own key, exactly as `SectionPanel.tsx`'s own does and for the measured reason it gives -
  // `Record` alone accepts `cycle`'s request under `event` just as readily, and nothing in this
  // repo executes a `.tsx` file under a gate. The three `set` arms are the ones that can swap
  // silently, `RasterAction` not being 1:1 with the request's own `action` - all three are `set`,
  // told apart by `key` alone - which is why it is the `key` literal each of them is pinned to
  // here. Each goes through `rasterSet`, which is what carries that one literal to the request and
  // to the quoting alike: an event quoted like a string is a refusal the reader did nothing to
  // earn, and a cycle sent bare is another.
  const requests: Record<RasterAction, RasterPlanRequest | null> = {
    event: draftEvent === null ? null : rasterSet(name, "event", draftEvent),
    cycle: draftCycle === null ? null : rasterSet(name, "cycle", draftCycle),
    describe: draftDescription === null ? null : rasterSet(name, "description", draftDescription),
    rename: to === null ? null : { action: "rename", name, to },
    // Asked for only while nothing names the raster, which `rasterRemovable` is the one judge of:
    // a shape still naming it always refuses (`remove_entry`), and a control that would refuse the
    // instant it was pressed is a lying button. The last raster a file declares is asked for like
    // any other, since the file it leaves declaring nothing still loads.
    remove: entry !== undefined && rasterRemovable(entry.uses) ? { action: "remove", name } : null,
  } satisfies {
    event: (Extract<RasterPlanRequest, { action: "set" }> & { key: "event" }) | null;
    cycle: (Extract<RasterPlanRequest, { action: "set" }> & { key: "cycle" }) | null;
    describe: (Extract<RasterPlanRequest, { action: "set" }> & { key: "description" }) | null;
    rename: Extract<RasterPlanRequest, { action: "rename" }> | null;
    remove: Extract<RasterPlanRequest, { action: "remove" }> | null;
  };
  // Event, cycle, description and rename each commit on every keystroke - plain fields, every
  // one - so each is debounced on its own (spec §6): a field's first ask is immediate, and only
  // one asked of before waits. Remove is never typed into - it is offered outright once nothing
  // names the raster any longer - so `asked.remove` is `requests.remove` itself.
  const asked: Record<RasterAction, RasterPlanRequest | null> = {
    event: useDebounced(requests.event),
    cycle: useDebounced(requests.cycle),
    describe: useDebounced(requests.describe),
    rename: useDebounced(requests.rename),
    remove: requests.remove,
  };
  const plans = {
    event: useRasterPlan(asked.event, revision, true),
    cycle: useRasterPlan(asked.cycle, revision, true),
    describe: useRasterPlan(asked.describe, revision, true),
    rename: useRasterPlan(asked.rename, revision),
    remove: useRasterPlan(asked.remove, revision),
  };
  const apply = useMutation({
    mutationFn: (action: RasterAction) => {
      const plan = plans[action].data;
      const request = requests[action];
      const edit =
        plan === undefined || request === null ? null : planEdit(plan, rasterLabel(request));
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setFailed(null),
    // Renamed, the raster is the new spelling now, and the tab opens its panel; removed, it is
    // gone as the reader asked. Neither is the raster disappearing that spec 5.4 has the tab
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
    // An Apply changes the raster's own entry or every shape naming it, the tab's rows and every
    // raster plan, whose fingerprints it spent: they are asked for again, and nothing can be
    // applied until they answer. A field saved is let go only then, so it goes from what was typed
    // straight to the entry's new text, and never back through the old one.
    onSettled: async (_reply, error, action) => {
      await Promise.all([
        queries.invalidateQueries({ queryKey: ["shared"] }),
        queries.invalidateQueries({ queryKey: ["raster"] }),
        queries.invalidateQueries({ queryKey: ["raster-plan"] }),
      ]);
      if (error === null && action === "event") setEvent(undefined);
      if (error === null && action === "cycle") setCycle(undefined);
      if (error === null && action === "describe") setDescription(undefined);
    },
  });
  /** Where a change stands: its plan, and why it was refused - on Apply, else when asked for.
   * `pending` also covers a debounced request not yet caught up with what the fields now say
   * (`sameRequest`): the preview is then an earlier request's, same as while any plan loads, and
   * Apply stays disabled rather than offered over text the reader has since typed past. */
  const offer = (action: RasterAction): Offer => ({
    plan: plans[action].data ?? null,
    refusal:
      staleFailed?.action === action
        ? shownRefusal(staleFailed, revision)
        : failed?.action === action
          ? failed.message
          : (plans[action].error?.message ?? null),
    pending: plans[action].isPlaceholderData || !sameRequest(asked[action], requests[action]),
  });

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
    <RasterPanelView
      reply={entry}
      updating={updating}
      event={event ?? entry.event}
      onEvent={(text) => {
        setEvent(text);
        setFailed(null);
      }}
      cycle={cycle ?? entry.cycle}
      onCycle={(text) => {
        setCycle(text);
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
      eventOffer={draftEvent === null ? null : offer("event")}
      cycleOffer={draftCycle === null ? null : offer("cycle")}
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
