import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, getValuePlan, getValues, getValuesPlan, postEdit } from "../api/client";
import type { State } from "../api/types";
import { ValuesGridView } from "../components/ValuesGridView";
import { cellAt, drawable, pasted, rawOf, typedNumber } from "../lib/objectValues";
import { planEdit } from "../lib/projectUnits";
import { type Refused, shownRefusal as staleRefusal } from "../lib/refusals";
import { pasteLabel, valueLabel } from "../lib/undo";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { UndoStrip } from "./UndoStrip";
import { refusalOf } from "./UnitPanel";

interface Props {
  /** The object whose values this grid shows - the route's own `variable`. */
  name: string;
  /** The file the route was opened from - the route's own `file`, not necessarily the object's
   * own producer (spec 5.4): what names and is returned to by "Back to". */
  file: string;
  state: State | null;
  stopped: boolean;
  onBack: () => void;
}

/** The cell being typed into, and its text; `null` when none is - `ValuesGridView`'s own. */
type Editing = { row: number; column: number; typed: string } | null;

/**
 * The open project's values grid (spec 5.4): one object's `init` against its axes, read fresh at
 * every revision, with the mutation that sets one cell of it, or a whole pasted table of them
 * (part 9). `ValuesGridView` draws all of it from props - the raw/physical toggle, the cell being
 * typed into and Show changes live here, the way `ValuesGridView.stories.tsx`'s own `View` keeps
 * them for a story.
 *
 * Two refusals are this screen's own rather than the component's: `GET /api/values` refused the
 * name - it is declared no longer, or its shape is more than a grid draws - or it has no shape at
 * all (a scalar's own `init`, reached by a finding filed on one or by typing the address by hand)
 * - `drawable` refuses that grid too, and a text-stated object is `ValuesGridView`'s own sentence
 * to say, not repeated here. Each of them keeps the heading and the way back.
 *
 * A cell typed into and a table pasted are two ways to reach the same mutation (spec 3's "a
 * paste is a second way to reach `init`"), so only one owns the preview, the sentence and Apply
 * at a time: `pastedRows` and `editing` are cleared by each other's own action, and `shownPlan`/
 * `shownRefusal`/`label` below choose between the two once, rather than at each prop.
 */
export function ValuesPage({ name, file, state, stopped, onBack }: Props) {
  const queries = useQueryClient();
  const revision = state?.revision;
  // The component named by the file the route carries - "Back to" both says and returns to the
  // same place, which the object's own owner cannot always promise (spec 5.4). Resolved once,
  // for every branch below to share, from `State.files`' own `name` - the answer to `GET
  // /api/state` already carries it, so this asks the server for nothing new.
  const backTo = state?.files.find((entry) => entry.path === file)?.name ?? "component";
  const values = useQuery({
    queryKey: ["values", name, revision],
    queryFn: () => getValues(name),
    // The grid does not blink on every revision: the shape or the numbers may have changed, but
    // the table stays up while the next revision's answer is read.
    placeholderData: (previous) => previous,
  });

  const [physical, setPhysical] = useState(true);
  const [editing, setEditing] = useState<Editing>(null);
  const [changesShown, setChangesShown] = useState(false);
  // A refused apply for a reason other than staleness, if any: cleared whenever the reader takes
  // a fresh action - types into the cell again, or pastes a fresh table over it - exactly as
  // `UnitPanel`'s own fields clear on a fresh choice. Without the paste side of that, a failure
  // left over from an earlier cell apply would sit under a perfectly good pasted table.
  const [failed, setFailed] = useState<string | null>(null);
  // A refused apply because a file changed on disk, held to the revision it happened at - as
  // `UnitPanel`'s own `staleFailed`, so a reader who applies again straight away is not refused a
  // second time for fingerprints the next revision has already moved past.
  const [staleFailed, setStaleFailed] = useState<Refused | null>(null);
  // A pasted table's counts, row-major, or `null` where nothing has been pasted; and the
  // sentence a pasted block was refused with, if any - the two ways `onPaste` below can answer,
  // from Task 2's `Pasted`. Held apart from `editing`'s own cell so a paste and a typed cell
  // never both hold something (each clears the other's state below).
  const [pastedRows, setPastedRows] = useState<number[][] | null>(null);
  const [pasteRefusal, setPasteRefusal] = useState<string | null>(null);

  // Every use below tolerates `values.data` not having arrived yet, which is what keeps `at` and
  // `raw` `null` and the plan query skipped until it has.
  const shape = values.data?.shape;
  const at =
    editing !== null && shape !== undefined ? cellAt(editing.row, editing.column, shape) : null;
  // What `editing.typed` would write, as a raw count: `null` while nothing is being edited or
  // what is typed is not a number - the same gate `ValuesGridView` itself keys its own sentence
  // on, so the two either agree or the plan below is still not asked for.
  const typed = editing === null ? Number.NaN : typedNumber(editing.typed);
  const raw =
    values.data === undefined || Number.isNaN(typed)
      ? null
      : physical
        ? rawOf(typed, values.data.conversion, values.data.datatype)
        : typed;
  const plan = useQuery({
    queryKey: ["value-plan", name, at, raw, revision],
    queryFn: at === null || raw === null ? skipToken : () => getValuePlan({ name, at, raw }),
  });
  // A pasted table's own preview, keyed on the counts themselves so a second, different paste
  // asks again - the same shape `plan` above already takes for one cell, and `getValuesPlan`
  // wants them row-major in one flat list.
  const table = useQuery({
    queryKey: ["values-plan", name, pastedRows, revision],
    queryFn:
      pastedRows === null ? skipToken : () => getValuesPlan({ name, raw: pastedRows.flat() }),
  });

  // One offer under the grid at a time: whichever of the two was last acted on owns the preview,
  // the sentence and Apply. `pastedRows` is cleared when a cell is typed into and `editing` when
  // a block is pasted (both below), so these never both hold something. `pasteRefusal` alone -
  // `pastedRows` still `null` - is still a paste: a block the parser itself refuses (a wrong
  // shape, a cell that is not a number) never reaches `pastedRows` at all, since `Pasted` (Task
  // 2's) holds exactly one of the two. Gating on `pastedRows` alone would fall through to the
  // cell's own refusal chain below, silently dropping the parser's own sentence for a paste that
  // was never a cell to begin with - driving it through a real browser (`values.spec.ts`'s own
  // "a block of the wrong shape is refused and nothing is written") is what actually found this.
  const pasting = pastedRows !== null || pasteRefusal !== null;
  const shownPlan = pasting ? (table.data ?? null) : (plan.data ?? null);
  // The pre-apply refusal each offer can find for itself - a pasted block's own sentence, or the
  // server's, for the one thing the parser cannot check - ahead of a stale or a plain apply
  // failure either way. A typed cell's own refusal is `ValuesGridView`'s to find, from `editing`
  // directly (`typedRefusal`), so it is not repeated here - repeating it would only recompute
  // the same sentence a second time for no reader to see any sooner.
  const shownRefusal = pasting
    ? (pasteRefusal ??
      staleRefusal(staleFailed, revision) ??
      failed ??
      (table.isError ? table.error.message : null))
    : (staleRefusal(staleFailed, revision) ?? failed ?? (plan.isError ? plan.error.message : null));
  // What either offer's own edit is called, for the undo stack: the whole object for a paste,
  // the one element for a cell - `pasteLabel`'s and `valueLabel`'s own difference.
  const label = pasting
    ? pasteLabel(name)
    : values.data === undefined || editing === null
      ? null
      : valueLabel(values.data.name, editing.row, editing.column, values.data.shape);

  const apply = useMutation({
    mutationFn: () => {
      const edit = shownPlan === null || label === null ? null : planEdit(shownPlan, label);
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setFailed(null),
    // Applying clears the cell being edited or the table being pasted and, with them, the plan
    // and the refusal either may have shown; the values this grid reads, the file's own content
    // and every value-plan preview - one cell's and a whole table's - are asked for again, since
    // the edit just spent the fingerprints they were made from.
    onSuccess: () => {
      setStaleFailed(null);
      setEditing(null);
      setPastedRows(null);
      setPasteRefusal(null);
      return Promise.all([
        queries.invalidateQueries({ queryKey: ["values"] }),
        queries.invalidateQueries({ queryKey: ["file"] }),
        queries.invalidateQueries({ queryKey: ["value-plan"] }),
        queries.invalidateQueries({ queryKey: ["values-plan"] }),
      ]);
    },
    // Stale is the one refusal that waits for a later revision rather than clearing; setting one
    // kind clears the other, so the grid never shows two different answers to the same Apply.
    onError: (error) => {
      if (error instanceof ApiError && error.code === "stale") {
        setStaleFailed({ text: refusalOf(error), revision });
        setFailed(null);
      } else {
        setFailed(refusalOf(error));
        setStaleFailed(null);
      }
    },
  });

  if (values.isPending) return <p className="quiet">Reading the values…</p>;
  if (values.isError) {
    // Every refusal keeps the heading and the way back, not only the object removed from under
    // the reader (spec 5.4): a grid this cannot draw - a shape of more dimensions than rows of
    // cells - is reached by a typed address or by a finding filed on its own init, and a bare
    // banner would leave the reader on a page holding nothing but the sentence.
    return (
      <section>
        <div className="heading">
          <h1>{name}</h1>
          <Button variant="link" onPress={onBack}>
            Back to {backTo}
          </Button>
        </div>
        <Banner tone="error">{values.error.message}</Banner>
      </section>
    );
  }
  const reply = values.data;
  if (!drawable(reply) && reply.stated !== "text") {
    // A scalar's own init: no cell for a value to sit in, the same words `object_values.py`'s
    // own `set_cell` refuses one with - reached by a finding on it or a typed address, never by
    // this screen's own Shape button, which offers none for a scalar.
    return (
      <section>
        <div className="heading">
          <h1>{reply.name}</h1>
          <Button variant="link" onPress={onBack}>
            Back to {backTo}
          </Button>
        </div>
        <p className="quiet">{`'${reply.name}' has no cell for a value to sit in`}</p>
      </section>
    );
  }
  return (
    <ValuesGridView
      reply={reply}
      backTo={backTo}
      undoStrip={<UndoStrip state={state} stopped={stopped} />}
      physical={physical}
      editing={editing}
      plan={shownPlan}
      refusal={shownRefusal}
      changesShown={changesShown}
      busy={stopped || apply.isPending}
      onPhysical={setPhysical}
      onEditing={(next) => {
        setEditing(next);
        setFailed(null);
        setPastedRows(null);
        setPasteRefusal(null);
      }}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      onBack={onBack}
      onPaste={(text) => {
        const block = pasted(text, reply, physical);
        setPastedRows(block.rows);
        setPasteRefusal(block.refusal);
        setFailed(null);
        setEditing(null);
      }}
    />
  );
}
