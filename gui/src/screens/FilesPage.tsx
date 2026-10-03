import {
  skipToken,
  type UseQueryResult,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState, useSyncExternalStore } from "react";
import { type FilesPlanRequest, getFiles, getFilesPlan, postEdit } from "../api/client";
import type { FilesPlanReply, State } from "../api/types";
import { useDebounced } from "../app/useDebounced";
import {
  AddFileView,
  FileActionsView,
  NewFileView,
  RemoveFileView,
} from "../components/FileActionsView";
import { FilesTableView } from "../components/FilesTableView";
import { type FileRemoval, fileAdd, fileCreate, fileRemoval, rowsOf } from "../lib/files";
import { type FilesHold, filesHoldAfter, filesHoldOf, filesShown } from "../lib/filesHold";
import { isStale, type Refused, refusalShown } from "../lib/refusals";
import { planEdit } from "../lib/shared";
import { planShown } from "../lib/typing";
import { filesLabel } from "../lib/undo";
import { ownEdits } from "../state/edits";
import { Banner } from "../ui/Banner";
import { refusalOf } from "./UnitPanel";

interface Props {
  state: State | null;
  /** The row whose key the address names, as the route's own `path` - `undefined` for the bare
   * tab. A row it names opens that row's Remove panel beside the table (`fileRemoval`). */
  path: string | undefined;
  onPath: (path: string | undefined) => void;
  /** The server stopped: nothing can be applied. */
  stopped: boolean;
}

/** The open project's Files tab (design §2 and §3): the root project's own `includes`, one row per
 * entry, a pattern's matched files indented beneath it; above it New file and Add a file, each
 * opening its form beside the table, and beside it the Remove panel of the row selected. Fetches
 * `GET /api/files` itself and re-reads it on each new revision, the way every other tab's own
 * screen does.
 *
 * The row its own New file or Add makes shows at once (spec §3, Ruling F2): the edit answered,
 * the tab holds the entry the applied plan appends (`filesHoldOf`) and draws it after the
 * answer's own (`filesShown`) until an answer carries it, the page's own undo puts it back, or an
 * answer of a revision including the edit comes (`filesHoldAfter`). */
export function FilesPage({ state, path, onPath, stopped }: Props) {
  const revision = state?.revision;
  const files = useQuery({
    queryKey: ["files", revision],
    queryFn: () => getFiles(),
    // The table stays while the next revision's entries are read: swapped for a loading line on
    // every edit, it lost the reader's place and made the tab flash - as every other tab's own
    // table already keeps its place across a poll.
    placeholderData: (previous) => previous,
  });
  // Which of the two forms that start from no row is open beside the table, if either. Opening
  // one lets the row selected go, and selecting a row closes it, so that one panel at a time
  // stands beside the table - `SharedPage`'s own rule for its add form and an entry's panel.
  const [form, setForm] = useState<"create" | "add" | null>(null);
  // The entry the tab's own last New file or Add appended, held until an answer carries it, and
  // the edits the page's undos put back - the Undo strip's, which end the hold.
  const [hold, setHold] = useState<FilesHold | null>(null);
  const undone = useSyncExternalStore(ownEdits.subscribe, ownEdits.undone);
  const holding = filesHoldAfter(hold, undone, state, files.data);
  if (holding !== hold) setHold(holding);
  if (files.data === undefined) {
    if (files.isError) return <Banner tone="error">{files.error.message}</Banner>;
    return <p className="quiet">Reading the project's files…</p>;
  }
  const reply = filesShown(holding, files.data);
  const read = state?.files ?? [];
  const removal = fileRemoval(rowsOf(reply, read), path, reply.project);
  const open = (next: "create" | "add") => {
    onPath(undefined);
    setForm(next);
  };
  return (
    <>
      {/* A server that stopped answering leaves the table as it was, and says so above it. */}
      {files.isError && <Banner tone="error">{files.error.message}</Banner>}
      <FileActionsView onNewFile={() => open("create")} onAddFile={() => open("add")} />
      <div className={removal !== null || form !== null ? "with-panel" : undefined}>
        <div>
          <FilesTableView
            reply={reply}
            files={read}
            selected={path}
            onSelect={(key) => {
              setForm(null);
              onPath(key);
            }}
          />
        </div>
        {removal !== null ? (
          // Keyed by the row, so that another row selected is a panel of its own: its plan, its
          // refusals and its Show changes start again rather than carrying over from the last.
          <RemoveFile
            key={removal.request.path}
            removal={removal}
            project={reply.project}
            revision={revision}
            stopped={stopped}
            onClose={() => onPath(undefined)}
          />
        ) : form === "create" ? (
          <NewFile
            project={reply.project}
            creatable={reply.creatable}
            revision={revision}
            stopped={stopped}
            onClose={() => setForm(null)}
            onHeld={setHold}
          />
        ) : (
          form === "add" && (
            <AddFile
              project={reply.project}
              revision={revision}
              stopped={stopped}
              onClose={() => setForm(null)}
              onHeld={setHold}
            />
          )
        )}
      </div>
    </>
  );
}

/**
 * One of the three plans, asked for again at every revision - an Apply spends the fingerprints it
 * carries - and not asked for at all while `request` is `null`.
 *
 * Keyed `["files-plan", ...]`, apart from every other tab's plans, so that invalidating these on an
 * edit throws none of theirs away. Never kept on screen while the next is asked for: New file's and
 * Add's fields are debounced as a whole (spec §6) rather than kept, since a plan kept through a
 * refusal would come back as the plan of a request the reader has typed past once the debounced
 * request moved on - React Query hands a placeholder the last plan that came, not the last one
 * asked. `SharedAdd`'s own three plans are debounced the very same way and keep none either -
 * `useConstantPlan`, `useSectionPlan` and `useRasterPlan` (called from there as much as from the
 * three panels that otherwise own them) have no `keep` option to ask for one with (fix round 2).
 */
function useFilesPlan(request: FilesPlanRequest | null, revision: number | undefined) {
  return useQuery({
    queryKey: ["files-plan", request, revision],
    queryFn: request === null ? skipToken : () => getFilesPlan(request),
  });
}

/**
 * Applying one of the three plans the way every other panel applies its own: the edit posted is
 * the plan's, under the label an undo of it will offer (`filesLabel`, from the very request the
 * plan was asked with and the plan itself: a created file named as the plan creates it, a
 * removal's key relative to `project`); a refusal because a file changed on disk is held until
 * the analysis moves past it, and any other until the reader chooses again - `refusalShown`
 * (`lib/refusals.ts`) says which is shown, read with `shown.refusal` (`planShown`,
 * `lib/typing.ts`) as the plan-fetch refusal it already takes a `string | null` for.
 * Once an Apply is answered, applied or refused, the tab's entries and every plan are asked for
 * again - each of the three edits the project description, whose fingerprint every plan carries -
 * and applied, `onApplied` closes the panel, and `onHeld`, where a form passes one, is handed the
 * entry the plan it posted appends (`filesHoldOf`), for the tab to draw until its entries carry it.
 */
function useFilesApply(
  request: FilesPlanRequest | null,
  // The debounced request actually behind `plan`'s own key - `request` itself where a form is
  // never debounced (`RemoveFile`'s, never typed into), so its one call site below passes the
  // same value twice.
  asked: FilesPlanRequest | null,
  project: string,
  plan: UseQueryResult<FilesPlanReply>,
  revision: number | undefined,
  onApplied: () => void,
  onHeld?: (hold: FilesHold | null) => void,
) {
  const queries = useQueryClient();
  const [refused, setRefused] = useState<string | null>(null);
  const [stale, setStale] = useState<Refused | null>(null);
  // The plan to offer, and why its own fetch was refused if it was - `planShown`'s own,
  // `lib/typing.ts` (review fix round 1): `null`/`null` while `asked` has not caught up with
  // `request`, or while `plan`'s answer is an earlier request's kept as a placeholder - never a
  // plan, nor its own fetch refusal, for text the reader has since typed past.
  const shown = planShown(asked, request, plan);
  const apply = useMutation({
    // Answers the plan it posted beside the edit's own answer: what the tab holds is read off the
    // very plan applied, whatever the query holds by the time the answer comes.
    mutationFn: async () => {
      const applied = plan.data;
      const edit =
        request === null || applied === undefined
          ? null
          : planEdit(applied, filesLabel(request, applied, project));
      if (edit === null || applied === undefined) throw new Error("there is nothing to change");
      return { reply: await postEdit(edit), applied };
    },
    onMutate: () => setRefused(null),
    // A success is a definite answer, so it also clears a stale wait left over from an earlier
    // attempt; `onMutate` above only ever clears the other refusal.
    onSuccess: ({ reply, applied }) => {
      setStale(null);
      onHeld?.(filesHoldOf(reply.edit, applied, project));
      onApplied();
    },
    // Stale is the one refusal that waits for a later revision rather than clearing; setting one
    // kind clears the other, so an action never shows two different answers to the same Apply.
    onError: (error) => {
      if (isStale(error)) {
        setStale({ text: refusalOf(error), revision });
        setRefused(null);
      } else {
        setRefused(refusalOf(error));
        setStale(null);
      }
    },
    onSettled: () =>
      Promise.all([
        queries.invalidateQueries({ queryKey: ["files"] }),
        queries.invalidateQueries({ queryKey: ["files-plan"] }),
      ]),
  });
  return {
    apply,
    plan: shown.plan,
    // Stale or a plain apply failure takes precedence, as it always did - both are about an
    // Apply already made, not a plan still loading, so neither is affected by `shown`.
    refusal: refusalShown(stale, refused, shown.refusal, revision),
    /** The reader chose again: what an earlier Apply was refused for says nothing of this plan. */
    chose: () => setRefused(null),
  };
}

/** New file's form, holding its three fields; its plan is debounced as each is typed (spec §6),
 * except a pick of Kind, which takes effect at once like every other pick (Ruling T12-3): File
 * name and Component name are always typed, but Kind commits by a pick as readily as by typing
 * (`NewFileView`'s own chooser), and `typedKind` says which the latest change was - never
 * inferred from the value itself, which a pick and typing can both leave in the very same shape
 * (the same reason `VariablePanel`'s `typedLimits` and `DeclarePanel`'s `typedEdit` keep their
 * own record rather than following the field). */
function NewFile({
  project,
  creatable,
  revision,
  stopped,
  onClose,
  onHeld,
}: {
  project: string;
  creatable: readonly string[];
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Applied: the entry the tab holds until its entries carry it. */
  onHeld: (hold: FilesHold | null) => void;
}) {
  const [kind, setKind] = useState("");
  const [name, setName] = useState("");
  const [component, setComponent] = useState("");
  const [changesShown, setChangesShown] = useState(false);
  const [typedKind, setTypedKind] = useState(true);
  const request = fileCreate(kind, name, component);
  const asked = useDebounced(request, typedKind);
  const plan = useFilesPlan(asked, revision);
  // Created, the form closes, and the tab holds the new file's row until its entries carry it.
  const {
    apply,
    plan: offerPlan,
    refusal,
    chose,
  } = useFilesApply(request, asked, project, plan, revision, onClose, onHeld);
  return (
    <NewFileView
      project={project}
      creatable={creatable}
      kind={kind}
      onKind={(text) => {
        setKind(text);
        setTypedKind(true);
        chose();
      }}
      onKindPicked={(text) => {
        setKind(text);
        setTypedKind(false);
        chose();
      }}
      name={name}
      onName={(text) => {
        setName(text);
        setTypedKind(true);
        chose();
      }}
      component={component}
      onComponent={(text) => {
        setComponent(text);
        setTypedKind(true);
        chose();
      }}
      offer={{ plan: offerPlan, refusal }}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}

/** Add's form, holding its path; its plan is debounced as it is typed (spec §6): the plain Path
 * field (`AddFileView`'s own) commits on every keystroke. */
function AddFile({
  project,
  revision,
  stopped,
  onClose,
  onHeld,
}: {
  project: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
  /** Applied: the entry the tab holds until its entries carry it. */
  onHeld: (hold: FilesHold | null) => void;
}) {
  const [path, setPath] = useState("");
  const [changesShown, setChangesShown] = useState(false);
  const request = fileAdd(path);
  const asked = useDebounced(request);
  const plan = useFilesPlan(asked, revision);
  // Added, the form closes, and the tab holds the file's row until its entries carry it.
  const {
    apply,
    plan: offerPlan,
    refusal,
    chose,
  } = useFilesApply(request, asked, project, plan, revision, onClose, onHeld);
  return (
    <AddFileView
      project={project}
      path={path}
      onPath={(text) => {
        setPath(text);
        chose();
      }}
      offer={{ plan: offerPlan, refusal }}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}

/** The selected row's Remove panel; its plan is asked for as soon as the row is selected. */
function RemoveFile({
  removal,
  project,
  revision,
  stopped,
  onClose,
}: {
  removal: FileRemoval;
  project: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
}) {
  const [changesShown, setChangesShown] = useState(false);
  const plan = useFilesPlan(removal.request, revision);
  // Removed, the panel closes, the address going bare: the row is gone - and where a pattern
  // keeps the file in all the same, the row left is the pattern's child, whose own Remove the
  // server would refuse, naming the pattern, the moment it was selected again. Never debounced -
  // `asked` and `request` are the same value - so `planShown` inside `useFilesApply` is always
  // trusted the moment the query itself settles.
  const {
    apply,
    plan: offerPlan,
    refusal,
  } = useFilesApply(removal.request, removal.request, project, plan, revision, onClose);
  return (
    <RemoveFileView
      removal={removal}
      project={project}
      offer={{ plan: offerPlan, refusal }}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}
