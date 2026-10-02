import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getUnit,
  getUnitPlan,
  getUnits,
  postEdit,
  type UnitPlanRequest,
} from "../api/client";
import { useUpdating } from "../app/updating";
import { useDebounced } from "../app/useDebounced";
import { type Offer, type UnitAction, UnitPanelView } from "../components/UnitPanelView";
import { offers, planEdit } from "../lib/projectUnits";
import { panelShows, type Refused, shownRefusal } from "../lib/refusals";
import { sameRequest } from "../lib/typing";
import { unitLabel } from "../lib/undo";
import { Banner } from "../ui/Banner";
import { Panel } from "../ui/Panel";
import { UpdatingNote } from "../ui/UpdatingNote";

interface Props {
  name: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Nothing in the open project states or lists the unit: the tab closes the panel, saying why. */
  onGone: () => void;
  /** Renamed or removed from this panel: the tab opens the new spelling's panel, or none. */
  onMoved: (unit: string | undefined) => void;
}

/** What the tab says when an edit it posted was refused: stale, as part 1's panel says it, or the
 * server's own reason. */
export function refusalOf(error: Error): string {
  return error instanceof ApiError && error.code === "stale"
    ? "A file changed on disk, so nothing was written. The page now shows the files as they are."
    : `The change was refused: ${error.message}`;
}

/**
 * One plan, asked for again at every revision - an Apply spends the fingerprints it carries - and
 * not asked for at all while `request` is `null`.
 *
 * `keep` leaves the last plan on screen while the next is asked for, marked as a placeholder, for
 * a description: it is debounced before `request` ever reaches this hook (`useDebounced`, spec
 * §6), so it changes once the reader pauses rather than with every key - but without `keep`, the
 * line saying which file it changes would still blink away each time it does.
 */
export function usePlan(
  request: UnitPlanRequest | null,
  revision: number | undefined,
  keep = false,
) {
  return useQuery({
    queryKey: ["unit-plan", request, revision],
    queryFn: request === null ? skipToken : () => getUnitPlan(request),
    placeholderData: (previous) => (keep ? previous : undefined),
  });
}

/** One unit's panel: where it is stated, its vocabulary entry, and a spelling to rename it to. */
export function UnitPanel({ name, revision, stopped, onClose, onGone, onMoved }: Props) {
  const queries = useQueryClient();
  const updating = useUpdating();
  const reply = useQuery({
    queryKey: ["unit", name, revision],
    queryFn: () => getUnit(name),
    placeholderData: (previous) => previous,
  });
  // What the panel shows of that answer (`panelShows`): a unit just renamed to this spelling is
  // refused until the rename is analysed, and the panel says the findings are updating meanwhile.
  const answer = panelShows(reply, (shown) => shown.unit, name, updating);
  const shownReply = answer.shown === "reply" ? answer.reply : undefined;
  const units = useQuery({
    queryKey: ["units", revision],
    queryFn: () => getUnits(),
    placeholderData: (previous) => previous,
  });
  // Set once this panel renamed or removed its unit: the unit is then gone because the reader
  // asked, and the panel moves on without the tab saying that it disappeared.
  const moving = useRef(false);
  // Spec 5.4: a unit renamed or removed from outside - or named by an address nothing states or
  // lists, such as an old bookmark - is gone, and its panel closes, the tab saying why. While a
  // file does not load the server cannot say that, and answers `unreadable` instead: the panel
  // then stays, naming the file, and shows the unit again once the file loads.
  const gone = reply.error instanceof ApiError && reply.error.code === "not-found";
  useEffect(() => {
    if (gone && !moving.current) onGone();
  }, [gone, onGone]);

  // What the reader types into the Description field, `undefined` until they do: the field then
  // reads the vocabulary's description.
  const [description, setDescription] = useState<string | undefined>(undefined);
  // The spelling chosen to rename the unit to, `null` until one is; and what is being typed into
  // the picker, `undefined` whenever its list is closed - the field then reads the spelling
  // chosen, else the unit's own, as part 1's picker reads the unit settled on.
  const [to, setTo] = useState<string | null>(null);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [shown, setShown] = useState<UnitAction | null>(null);
  // The one action refused for a reason other than staleness, if any: cleared whenever the
  // reader chooses again, exactly as before.
  const [failed, setFailed] = useState<{ action: UnitAction; message: string } | null>(null);
  // The one action refused because a file changed on disk, and the revision it happened at. As
  // in `VariablePanel`, a reader who chooses again straight away would otherwise send the same
  // stale fingerprints the server just refused; `shownRefusal` keeps it shown until a later
  // revision arrives.
  const [staleFailed, setStaleFailed] = useState<({ action: UnitAction } & Refused) | null>(null);

  const row = units.data?.units.find((entry) => entry.unit === name);
  const offered =
    row === undefined || units.data === undefined
      ? null
      : offers(row, units.data.vocabulary !== null);
  const draft =
    description !== undefined && description !== (row?.description ?? "") ? description : null;
  // Named before the plans that ask for them, so that applying one can say what it was: the
  // label an undo of this edit will offer comes from the same request the preview was made
  // from, rather than from a second reading of the panel's state.
  const requests: Record<UnitAction, UnitPlanRequest | null> = {
    describe:
      offered?.describe && draft !== null
        ? { action: "describe", unit: name, description: draft }
        : null,
    add: offered?.add ? { action: "add", unit: name } : null,
    remove: offered?.remove ? { action: "remove", unit: name } : null,
    rename: to === null ? null : { action: "rename", unit: name, to },
  };
  // Description is the one field here typed into directly (a plain field, committing on every
  // keystroke), so it is the one debounced (spec §6): a panel's first ask of it is immediate, and
  // only a later one waits. Add and remove are never typed into - `offers` offers each outright
  // once the unit's own state says so - and the rename picker commits only on a spelling picked
  // or typed and confirmed with Enter (`UnitPanelView`'s own `UnitPicker`), never on a keystroke
  // of its own: `to` only ever holds a whole, deliberate choice, so there is no keystroke for any
  // of the three to wait on, and `asked`'s own entries for them are `requests`' outright.
  const asked: Record<UnitAction, UnitPlanRequest | null> = {
    describe: useDebounced(requests.describe),
    add: requests.add,
    remove: requests.remove,
    rename: requests.rename,
  };
  const plans = {
    describe: usePlan(asked.describe, revision, true),
    add: usePlan(asked.add, revision),
    remove: usePlan(asked.remove, revision),
    rename: usePlan(asked.rename, revision),
  };
  const apply = useMutation({
    mutationFn: (action: UnitAction) => {
      const plan = plans[action].data;
      const request = requests[action];
      const edit =
        plan === undefined || request === null ? null : planEdit(plan, unitLabel(request));
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setFailed(null),
    // Renamed, the unit is the new spelling now, and the tab opens its panel; removed, it is gone
    // as the reader asked. Neither is the unit disappearing that spec 5.4 has the tab announce.
    // A success is a definite answer, so it also clears a stale wait left over from an earlier
    // attempt at this same action - `onMutate` above only ever clears the other refusal.
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
    // An Apply changes the unit's places, the tab's rows and every plan, whose fingerprints the
    // edit spent: they are asked for again, and nothing can be applied until they answer. The
    // description saved is let go only then, so that the field goes from what was typed straight
    // to the vocabulary's new description, and never back through the old one.
    onSettled: async (_reply, error, action) => {
      await Promise.all([
        queries.invalidateQueries({ queryKey: ["unit"] }),
        queries.invalidateQueries({ queryKey: ["units"] }),
        queries.invalidateQueries({ queryKey: ["unit-plan"] }),
      ]);
      if (error === null && action === "describe") setDescription(undefined);
    },
  });
  /** Where a change stands: its plan, and why it was refused - on Apply, else when asked for.
   * `pending` also covers a debounced request not yet caught up with what the fields now say
   * (`sameRequest`): the preview is then an earlier request's, same as while any plan loads, and
   * Apply stays disabled rather than offered over text the reader has since typed past. Always
   * `false` for `add`/`remove`/`rename`, whose `asked` entries are never behind `requests`'. */
  const offer = (action: UnitAction): Offer => ({
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
  if (shownReply === undefined || units.data === undefined || row === undefined) {
    return (
      <Panel title={name} onClose={onClose}>
        <p className="quiet">Reading {name}…</p>
      </Panel>
    );
  }
  return (
    <UnitPanelView
      unit={row}
      reply={shownReply}
      units={units.data}
      updating={updating}
      description={description ?? row.description ?? ""}
      onDescription={(text) => {
        setDescription(text);
        setFailed(null);
      }}
      typed={typed ?? to ?? name}
      // Never the spelling chosen: opening the picker on it must still list everything.
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(chosen) => {
        // The unit's own spelling renames nothing: choosing it goes back to no rename at all.
        setTo(chosen === name ? null : chosen);
        setTyped(undefined);
        setFailed(null);
      }}
      onPickerClosed={() => setTyped(undefined)}
      to={to}
      // Nothing is said of a description left as it is: the plan kept for the last key typed
      // (usePlan) would otherwise still show once the text is the vocabulary's again.
      describing={draft === null ? null : offer("describe")}
      adding={offer("add")}
      removing={offer("remove")}
      renaming={offer("rename")}
      shown={shown}
      onShown={setShown}
      onApply={(action) => apply.mutate(action)}
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}
