import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  ApiError,
  type ConstantPlanRequest,
  getConstant,
  getConstantPlan,
  postEdit,
} from "../api/client";
import {
  type ConstantAction,
  ConstantPanelView,
  type Offer,
} from "../components/ConstantPanelView";
import { type Refused, shownRefusal } from "../lib/refusals";
import type { Route } from "../lib/route";
import { planEdit } from "../lib/shared";
import { constantLabel } from "../lib/undo";
import { Banner } from "../ui/Banner";
import { Panel } from "../ui/Panel";
import { refusalOf } from "./UnitPanel";

interface Props {
  name: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Nothing in the open project declares the constant: the tab closes the panel, saying why. */
  onGone: () => void;
  /** Renamed or removed from this panel: the tab opens the new spelling's panel, or none. */
  onMoved: (name: string | undefined) => void;
  /** Following a use's variable, a member's type, or the component declaring the constant inline,
   * without a reload. */
  onOpen: (route: Route) => void;
}

/**
 * One plan, asked for again at every revision - an Apply spends the fingerprints it carries - and
 * not asked for at all while `request` is `null`.
 *
 * Its own hook, keyed `["constant-plan", ...]` rather than widening `UnitPanel`'s `usePlan`
 * (keyed `["unit-plan", ...]`) to take either request: the keys have to differ so that
 * invalidating one tab's plans on an edit does not throw away the other's, and a generic wide
 * enough for both requests would be a bigger change than one more tab's own hook.
 *
 * `keep` leaves the last plan on screen while the next is asked for, marked as a placeholder, for
 * a value or a description: both change with every key typed, and only in the text they write, so
 * the line saying which file it changes would otherwise blink at every key.
 */
export function useConstantPlan(
  request: ConstantPlanRequest | null,
  revision: number | undefined,
  keep = false,
) {
  return useQuery({
    queryKey: ["constant-plan", request, revision],
    queryFn: request === null ? skipToken : () => getConstantPlan(request),
    placeholderData: (previous) => (keep ? previous : undefined),
  });
}

/** One constant's panel: its value and description, where it is declared, every shape naming it,
 * its findings, and a spelling to rename it to (spec 5.2). */
export function ConstantPanel({
  name,
  revision,
  stopped,
  onClose,
  onGone,
  onMoved,
  onOpen,
}: Props) {
  const queries = useQueryClient();
  const reply = useQuery({
    queryKey: ["constant", name, revision],
    queryFn: () => getConstant(name),
    placeholderData: (previous) => previous,
  });
  // Set once this panel renamed or removed its constant: it is then gone because the reader
  // asked, and the panel moves on without the tab saying that it disappeared.
  const moving = useRef(false);
  // Spec 5.4: a constant renamed or removed from outside - or named by an address nothing
  // declares, such as an old bookmark - is gone, and its panel closes, the tab saying why. While
  // a file does not load the server cannot say that, and answers `unreadable` instead: the panel
  // then stays, naming the file, and shows the constant again once the file loads.
  const gone = reply.error instanceof ApiError && reply.error.code === "not-found";
  useEffect(() => {
    if (gone && !moving.current) onGone();
  }, [gone, onGone]);

  // What the reader types into Value and Description, `undefined` until they do: each field then
  // reads the entry's own text.
  const [value, setValue] = useState<string | undefined>(undefined);
  const [description, setDescription] = useState<string | undefined>(undefined);
  // The spelling chosen to rename the constant to, `null` until one is typed.
  const [to, setTo] = useState<string | null>(null);
  const [shown, setShown] = useState<ConstantAction | null>(null);
  // The one action refused for a reason other than staleness, if any: cleared whenever the
  // reader chooses again, exactly as `UnitPanel`'s own.
  const [failed, setFailed] = useState<{ action: ConstantAction; message: string } | null>(null);
  // The one action refused because a file changed on disk, and the revision it happened at -
  // held until a later revision arrives, exactly as `UnitPanel`'s own `staleFailed`.
  const [staleFailed, setStaleFailed] = useState<({ action: ConstantAction } & Refused) | null>(
    null,
  );

  const entry = reply.data;
  const draftValue = value !== undefined && value !== entry?.value ? value : null;
  const draftDescription =
    description !== undefined && description !== entry?.description ? description : null;
  // Named before the plans that ask for them, so that applying one can say what it was: the
  // label an undo of this edit will offer comes from the same request the preview was made
  // from, rather than from a second reading of the panel's state.
  const requests: Record<ConstantAction, ConstantPlanRequest | null> = {
    value: draftValue === null ? null : { action: "set", name, key: "value", raw: draftValue },
    describe:
      draftDescription === null
        ? null
        : { action: "set", name, key: "description", raw: JSON.stringify(draftDescription) },
    rename: to === null ? null : { action: "rename", name, to },
    // Asked for as soon as the panel opens, unlike the other three: removing takes only the name
    // the route already carries, with no draft to wait on. Offered where nothing names the
    // constant; refused in the server's own words otherwise (design §4.5) - the reader reads why
    // in the same banner every other refusal is shown in, rather than the control simply not
    // being there to try.
    remove: { action: "remove", name },
  };
  const plans = {
    value: useConstantPlan(requests.value, revision, true),
    describe: useConstantPlan(requests.describe, revision, true),
    rename: useConstantPlan(requests.rename, revision),
    remove: useConstantPlan(requests.remove, revision),
  };
  const apply = useMutation({
    mutationFn: (action: ConstantAction) => {
      const plan = plans[action].data;
      const request = requests[action];
      const edit =
        plan === undefined || request === null ? null : planEdit(plan, constantLabel(request));
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setFailed(null),
    // Renamed, the constant is the new spelling now, and the tab opens its panel; removed, it is
    // gone as the reader asked. Neither is the constant disappearing that spec 5.4 has the tab
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
    // An Apply changes the constant's own entry or every place naming it, the tab's rows and
    // every plan, whose fingerprints it spent: they are asked for again, and nothing can be
    // applied until they answer. A field saved is let go only then, so it goes from what was
    // typed straight to the entry's new text, and never back through the old one.
    onSettled: async (_reply, error, action) => {
      await Promise.all([
        queries.invalidateQueries({ queryKey: ["shared"] }),
        queries.invalidateQueries({ queryKey: ["constant"] }),
        queries.invalidateQueries({ queryKey: ["constant-plan"] }),
      ]);
      if (error === null && action === "value") setValue(undefined);
      if (error === null && action === "describe") setDescription(undefined);
    },
  });
  /** Where a change stands: its plan, and why it was refused - on Apply, else when asked for. */
  const offer = (action: ConstantAction): Offer => ({
    plan: plans[action].data ?? null,
    refusal:
      staleFailed?.action === action
        ? shownRefusal(staleFailed, revision)
        : failed?.action === action
          ? failed.message
          : (plans[action].error?.message ?? null),
    pending: plans[action].isPlaceholderData,
  });

  if (gone) return null;
  if (reply.isError) {
    return (
      <Panel title={name} onClose={onClose}>
        <Banner tone="error">{reply.error.message}</Banner>
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
    <ConstantPanelView
      reply={entry}
      value={value ?? entry.value}
      onValue={(text) => {
        setValue(text);
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
      valueOffer={draftValue === null ? null : offer("value")}
      describeOffer={draftDescription === null ? null : offer("describe")}
      renameOffer={to === null ? null : offer("rename")}
      removeOffer={offer("remove")}
      shown={shown}
      onShown={setShown}
      onApply={(action) => apply.mutate(action)}
      onOpen={onOpen}
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}
