import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, getValuePlan, getValues, postEdit } from "../api/client";
import type { State } from "../api/types";
import { ValuesGridView } from "../components/ValuesGridView";
import { cellAt, drawable, rawOf, typedNumber } from "../lib/objectValues";
import { planEdit } from "../lib/projectUnits";
import { type Refused, shownRefusal } from "../lib/refusals";
import { valueLabel } from "../lib/undo";
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
 * every revision, with the mutation that sets one cell of it. `ValuesGridView` draws all of it
 * from props - the raw/physical toggle, the cell being typed into and Show changes live here, the
 * way `ValuesGridView.stories.tsx`'s own `View` keeps them for a story.
 *
 * Two refusals are this screen's own rather than the component's: the object named by the route
 * is no longer produced by anything (`GET /api/values` answers `404 not-found`), or it has no
 * shape at all (a scalar's own `init`, reached by a finding filed on one or by typing the address
 * by hand) - `drawable` refuses that grid too, and a text-stated object is `ValuesGridView`'s own
 * sentence to say, not repeated here.
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
  // A refused apply for a reason other than staleness, if any: cleared whenever the reader types
  // into the cell again, exactly as `UnitPanel`'s own fields clear on a fresh choice.
  const [failed, setFailed] = useState<string | null>(null);
  // A refused apply because a file changed on disk, held to the revision it happened at - as
  // `UnitPanel`'s own `staleFailed`, so a reader who applies again straight away is not refused a
  // second time for fingerprints the next revision has already moved past.
  const [staleFailed, setStaleFailed] = useState<Refused | null>(null);

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

  const apply = useMutation({
    mutationFn: () => {
      const label =
        values.data === undefined || editing === null
          ? null
          : valueLabel(values.data.name, editing.row, editing.column, values.data.shape);
      const edit = plan.data === undefined || label === null ? null : planEdit(plan.data, label);
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setFailed(null),
    // Applying clears the cell being edited and, with it, the plan and the refusal it may have
    // shown; the values this grid reads, the file's own content and every value-plan preview are
    // asked for again, since the edit just spent the fingerprints they were made from.
    onSuccess: () => {
      setStaleFailed(null);
      setEditing(null);
      return Promise.all([
        queries.invalidateQueries({ queryKey: ["values"] }),
        queries.invalidateQueries({ queryKey: ["file"] }),
        queries.invalidateQueries({ queryKey: ["value-plan"] }),
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
    if (!(values.error instanceof ApiError && values.error.code === "not-found")) {
      return <Banner tone="error">{values.error.message}</Banner>;
    }
    // Removed from under the reader: nothing produces this name any more, so there is no grid -
    // only the way back to where they came from (spec 5.4).
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
      plan={plan.data ?? null}
      refusal={
        shownRefusal(staleFailed, revision) ?? failed ?? (plan.isError ? plan.error.message : null)
      }
      changesShown={changesShown}
      busy={stopped || apply.isPending}
      onPhysical={setPhysical}
      onEditing={(next) => {
        setEditing(next);
        setFailed(null);
      }}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      onBack={onBack}
    />
  );
}
