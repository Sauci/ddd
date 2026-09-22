import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  getType,
  getTypePlan,
  getUnits,
  postEdit,
  type TypePlanRequest,
} from "../api/client";
import { TypePanelView } from "../components/TypePanelView";
import { planEdit } from "../lib/projectUnits";
import { type Refused, shownRefusal } from "../lib/refusals";
import type { Route } from "../lib/route";
import { typeLabel } from "../lib/undo";
import { textOf, unitLabel } from "../lib/units";
import { limitsNote, limitsOf, limitsRaw, shortValue } from "../lib/variableKeys";
import { Banner } from "../ui/Banner";
import { Panel } from "../ui/Panel";

interface Props {
  name: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Nothing in the open project declares the type: the tab closes the panel, saying why. */
  onGone: () => void;
  /** Renamed from this panel: the tab opens the new spelling's panel. */
  onMoved: (name: string) => void;
  /** Following a use, a member's type or a finding, without a reload. */
  onOpen: (route: Route) => void;
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
 * not asked for at all while `request` is `null`. Never retried: a refusal the server gave this
 * exact request would only be given again until a later revision changes what it is checked
 * against.
 *
 * `keep` leaves the last plan on screen while the next is asked for, marked as a placeholder, for
 * a description: its plan changes with every key typed, and only in the text it writes, so the
 * line saying which file it changes would otherwise blink at every key.
 */
export function usePlan(
  request: TypePlanRequest | null,
  revision: number | undefined,
  keep = false,
) {
  return useQuery({
    queryKey: ["type-plan", request, revision],
    queryFn: request === null ? skipToken : () => getTypePlan(request),
    placeholderData: (previous) => (keep ? previous : undefined),
    retry: false,
  });
}

/** Which of the panel's three write paths a plan, a refusal or an apply belongs to. */
type Kind = "key" | "describe" | "rename";

/** What the chooser's field reads for a key's value while nothing is being typed: the unit
 * picker's own label for `unit`, else `variableKeys.shortValue`'s - mirroring
 * `variableKeys.labelOfRaw` without a `VariableReply` to call it through, since a type's own
 * value needs none. */
function fieldLabel(editor: string | undefined, key: string, raw: string | null): string {
  if (editor === "unit") return unitLabel(textOf(raw ?? undefined));
  return raw === null ? "state nothing" : shortValue(key, raw);
}

/** One type's panel: what it fixes, where it is used, its members, and a spelling to rename it
 * to (spec 5.2). */
export function TypePanel({ name, revision, stopped, onClose, onGone, onMoved, onOpen }: Props) {
  const queries = useQueryClient();
  const reply = useQuery({
    queryKey: ["type", name, revision],
    queryFn: () => getType(name),
    placeholderData: (previous) => previous,
  });
  const units = useQuery({
    queryKey: ["units", revision],
    queryFn: () => getUnits(),
    placeholderData: (previous) => previous,
  });
  // Set once this panel renamed its type: the type is then gone under its old name because the
  // reader asked, and the panel moves on to the new one without the tab saying it disappeared.
  const moving = useRef(false);
  // Spec 5.4: a type renamed or removed from outside - or named by an address nothing declares,
  // such as an old bookmark - is gone, and its panel closes, the tab saying why. While a file
  // does not load the server cannot say that, and answers `unreadable` instead: the panel then
  // stays, naming the file, and shows the type again once the file loads.
  const gone = reply.error instanceof ApiError && reply.error.code === "not-found";
  useEffect(() => {
    if (gone && !moving.current) onGone();
  }, [gone, onGone]);

  // Which row of "What it fixes" is open, `undefined` while none is.
  const [selected, setSelected] = useState<string | undefined>(undefined);
  // What is being typed into its field, `undefined` whenever the list is closed.
  const [typed, setTyped] = useState<string | undefined>(undefined);
  // The raw value chosen from the list for `selected`, `undefined` until the reader picks one.
  const [chosen, setChosen] = useState<string | null | undefined>(undefined);
  // The two fields of a range, touched, while `selected` is `limits` - the same tri-state
  // `chosen` is for every other key: `undefined` until the reader edits one.
  const [edited, setEdited] = useState<{ min: string; max: string } | undefined>(undefined);
  // What the reader types into the Description field, `undefined` until they do: the field then
  // reads the type's own description.
  const [description, setDescription] = useState<string | undefined>(undefined);
  // The spelling chosen to rename the type to, `null` until one is typed.
  const [renameTo, setRenameTo] = useState<string | null>(null);
  const [changesShown, setChangesShown] = useState(false);
  // The one write refused for a reason other than staleness, if any, and which of the panel's
  // three write paths it belongs to - cleared whenever the reader chooses again, exactly as the
  // unit and variable panels clear theirs.
  const [refused, setRefused] = useState<{ kind: Kind; message: string } | null>(null);
  // The one write refused because a file changed on disk, which write path it belongs to, and
  // the revision it happened at. As in the other panels, a reader who chooses again straight
  // away would otherwise send the same stale fingerprints the server just refused; `shownRefusal`
  // keeps it shown until a later revision arrives.
  const [stale, setStale] = useState<({ kind: Kind } & Refused) | null>(null);

  const type = reply.data;
  const offer = type?.keys.find((entry) => entry.key === selected);
  const starting = offer?.values[0]?.raw ?? null;
  // Two empty fields are "state nothing", which removes the key; anything else that is not a
  // range is nothing to plan for, and no request is asked for while it is broken - the same
  // gate `VariablePanel` gives its own settle query, though this panel's chooser has no field of
  // its own to show the sentence in.
  const broken = selected === "limits" ? limitsNote(edited?.min ?? "", edited?.max ?? "") : null;
  const range = edited ?? (selected === undefined ? { min: "", max: "" } : limitsOf(starting));
  const target =
    selected === undefined || broken !== null
      ? null
      : selected === "limits"
        ? limitsRaw(range.min, range.max)
        : (chosen ?? starting);
  // What the reader has changed the description away from, `null` while it reads the type's own -
  // the third write path, with no marker of its own the way `selected`/`renameTo` are.
  const draft = description !== undefined && description !== type?.description ? description : null;

  // Named once, so that whichever of the three is applied posts the very request its preview was
  // asked for, and the label an undo offers reads that same request too (part 5's Task 4, as
  // `UnitPanel` keeps it).
  const requests: Record<Kind, TypePlanRequest | null> = {
    key:
      selected === undefined || broken !== null
        ? null
        : { action: "set", name, key: selected, raw: target },
    describe:
      draft === null
        ? null
        : { action: "set", name, key: "description", raw: JSON.stringify(draft) },
    rename: renameTo === null ? null : { action: "rename", name, to: renameTo },
  };
  const plans = {
    key: usePlan(requests.key, revision),
    describe: usePlan(requests.describe, revision, true),
    rename: usePlan(requests.rename, revision),
  };
  // The panel shows one preview at a time, so at most one of the three is ever dirty at once:
  // `onSelect`, `onRenameTo` and `onDescription` below each clear the other two the moment they
  // dirty their own (a deselection or a field typed back to the type's own is the opposite of
  // dirtying, and clears nothing else). This picks whichever one that is - a key row open
  // outranks a rename typed, which outranks the description edited, the order `TypePanelView`'s
  // own comment lists its three write paths in, though at most one is ever actually pending at
  // render time. Choosing again elsewhere, or typing a field back to its own starting value,
  // always has a way back to `null`, so a path is never stuck unreachable behind another.
  const active: Kind | null =
    selected !== undefined
      ? "key"
      : renameTo !== null
        ? "rename"
        : draft !== null
          ? "describe"
          : null;
  const activePlan = active === null ? null : plans[active];

  const apply = useMutation({
    mutationFn: (kind: Kind) => {
      const plan = plans[kind].data;
      const request = requests[kind];
      const edit =
        plan === undefined || request === null ? null : planEdit(plan, typeLabel(request));
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setRefused(null),
    // Renamed, the type is the new spelling now, and the tab opens its panel - not the type
    // disappearing that spec 5.4 has the tab announce. A success is a definite answer, so it
    // also clears a stale wait left over from an earlier attempt at this same write - `onMutate`
    // above only ever clears the other refusal.
    onSuccess: (_reply, kind) => {
      setStale(null);
      setChangesShown(false);
      if (kind === "rename" && renameTo !== null) {
        moving.current = true;
        onMoved(renameTo);
      }
    },
    // Stale is the one refusal that waits for a later revision rather than clearing; setting one
    // kind clears the other, so the panel never shows two different answers to the same Apply.
    onError: (error, kind) => {
      if (error instanceof ApiError && error.code === "stale") {
        setStale({ kind, text: refusalOf(error), revision });
        setRefused(null);
      } else {
        setRefused({ kind, message: refusalOf(error) });
        setStale(null);
      }
    },
    // An Apply changes the type's own entry, every place naming it, the tab's rows and every
    // plan, whose fingerprints the edit spent: they are asked for again, and nothing can be
    // applied until they answer. The description saved is let go only then, so that the field
    // goes from what was typed straight to the type's new description, and never back through
    // the old one.
    onSettled: async (_reply, error, kind) => {
      await Promise.all([
        queries.invalidateQueries({ queryKey: ["type"] }),
        queries.invalidateQueries({ queryKey: ["types"] }),
        queries.invalidateQueries({ queryKey: ["type-plan"] }),
      ]);
      if (error === null && kind === "describe") setDescription(undefined);
    },
  });

  if (gone) return null;
  if (reply.isError) {
    return (
      <Panel title={name} onClose={onClose}>
        <Banner tone="error">{reply.error.message}</Banner>
      </Panel>
    );
  }
  if (type === undefined || units.data === undefined) {
    return (
      <Panel title={name} onClose={onClose}>
        <p className="quiet">Reading {name}…</p>
      </Panel>
    );
  }
  return (
    <TypePanelView
      type={type}
      units={units.data}
      selected={selected}
      onSelect={(key) => {
        setSelected(key);
        setTyped(undefined);
        setChosen(undefined);
        setEdited(undefined);
        setChangesShown(false);
        setRefused(null);
        // The panel shows one preview at a time: selecting a row dirties this path, so whichever
        // of the other two was previewed stops being - a deselection (key undefined) is the
        // opposite, ending this path, and must touch neither.
        if (key !== undefined) {
          setRenameTo(null);
          setDescription(undefined);
        }
      }}
      typed={
        typed ??
        (selected === undefined || broken !== null
          ? ""
          : fieldLabel(offer?.editor, selected, target))
      }
      onTyped={setTyped}
      onChosen={(raw) => {
        setChosen(raw);
        setTyped(undefined);
        setRefused(null);
        // A range chosen from the list - in play, or "state nothing", which empties the two
        // fields - is settled on by writing it into them, since they are what is applied.
        if (selected === "limits") setEdited(limitsOf(raw));
      }}
      onPickerClosed={() => setTyped(undefined)}
      range={range}
      onRange={(next) => {
        setEdited(next);
        setTyped(undefined);
        setRefused(null);
      }}
      description={description ?? type.description}
      onDescription={(text) => {
        setDescription(text);
        setRefused(null);
        // Only on the keystroke that actually starts dirtying this path - checking what was
        // pending *before* this key, the same as the plans read `selected`/`renameTo` from the
        // render this handler closes over - so continuing to type does not repeatedly clear a
        // "Show changes" the reader opened for this same, still-active preview.
        if (text !== type.description && (selected !== undefined || renameTo !== null)) {
          setSelected(undefined);
          setTyped(undefined);
          setChosen(undefined);
          setEdited(undefined);
          setRenameTo(null);
          setChangesShown(false);
        }
      }}
      renameTo={renameTo}
      onRenameTo={(to) => {
        setRenameTo(to);
        setRefused(null);
        // Same as above, the other way around: typing a rename away from the type's own name
        // dirties this path, once, the first time it does.
        if (to !== null && (selected !== undefined || draft !== null)) {
          setSelected(undefined);
          setTyped(undefined);
          setChosen(undefined);
          setEdited(undefined);
          setDescription(undefined);
          setChangesShown(false);
        }
      }}
      preview={activePlan?.data ?? null}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => {
        if (active !== null) apply.mutate(active);
      }}
      onOpen={onOpen}
      refusal={
        active === null
          ? null
          : ((stale?.kind === active ? shownRefusal(stale, revision) : null) ??
            (refused?.kind === active ? refused.message : null) ??
            activePlan?.error?.message ??
            null)
      }
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}
