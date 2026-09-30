import {
  skipToken,
  type UseQueryResult,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState } from "react";
import { type FilesPlanRequest, getFiles, getFilesPlan, postEdit } from "../api/client";
import type { FilesPlanReply, State } from "../api/types";
import {
  AddFileView,
  FileActionsView,
  NewFileView,
  RemoveFileView,
} from "../components/FileActionsView";
import { FilesTableView } from "../components/FilesTableView";
import { type FileRemoval, fileAdd, fileCreate, fileRemoval, rowsOf } from "../lib/files";
import { isStale, type Refused, refusalShown } from "../lib/refusals";
import { planEdit } from "../lib/shared";
import { filesLabel } from "../lib/undo";
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
 * screen does. */
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
  if (files.data === undefined) {
    if (files.isError) return <Banner tone="error">{files.error.message}</Banner>;
    return <p className="quiet">Reading the project's files…</p>;
  }
  const reply = files.data;
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
          />
        ) : (
          form === "add" && (
            <AddFile
              project={reply.project}
              revision={revision}
              stopped={stopped}
              onClose={() => setForm(null)}
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
 * Add's fields ask again with every key typed, and a plan kept through a refusal would come back
 * as the plan of a request the reader has typed past - React Query hands a placeholder the last
 * plan that came, not the last one asked. `SharedAdd`'s own per-keystroke plans keep none either.
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
 * plan was asked with); a refusal because a file changed on disk is held until the analysis moves
 * past it, and any other until the reader chooses again (`refusalShown` says which is shown).
 * Once an Apply is answered, applied or refused, the tab's entries and every plan are asked for
 * again - each of the three edits the project description, whose fingerprint every plan carries -
 * and applied, `onApplied` closes the panel.
 */
function useFilesApply(
  request: FilesPlanRequest | null,
  plan: UseQueryResult<FilesPlanReply>,
  revision: number | undefined,
  onApplied: () => void,
) {
  const queries = useQueryClient();
  const [refused, setRefused] = useState<string | null>(null);
  const [stale, setStale] = useState<Refused | null>(null);
  const apply = useMutation({
    mutationFn: () => {
      const edit =
        request === null || plan.data === undefined
          ? null
          : planEdit(plan.data, filesLabel(request));
      if (edit === null) throw new Error("there is nothing to change");
      return postEdit(edit);
    },
    onMutate: () => setRefused(null),
    // A success is a definite answer, so it also clears a stale wait left over from an earlier
    // attempt; `onMutate` above only ever clears the other refusal.
    onSuccess: () => {
      setStale(null);
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
    refusal: refusalShown(stale, refused, plan.error, revision),
    /** The reader chose again: what an earlier Apply was refused for says nothing of this plan. */
    chose: () => setRefused(null),
  };
}

/** New file's form, holding its three fields; its plan is asked for again as each is typed. */
function NewFile({
  project,
  creatable,
  revision,
  stopped,
  onClose,
}: {
  project: string;
  creatable: readonly string[];
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
}) {
  const [kind, setKind] = useState("");
  const [name, setName] = useState("");
  const [component, setComponent] = useState("");
  const [changesShown, setChangesShown] = useState(false);
  const request = fileCreate(kind, name, component);
  const plan = useFilesPlan(request, revision);
  // Created, the form closes: the new file's row is the table's to show, once it reads again.
  const { apply, refusal, chose } = useFilesApply(request, plan, revision, onClose);
  return (
    <NewFileView
      project={project}
      creatable={creatable}
      kind={kind}
      onKind={(text) => {
        setKind(text);
        chose();
      }}
      name={name}
      onName={(text) => {
        setName(text);
        chose();
      }}
      component={component}
      onComponent={(text) => {
        setComponent(text);
        chose();
      }}
      offer={{ plan: plan.data ?? null, refusal }}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}

/** Add's form, holding its path; its plan is asked for again as it is typed. */
function AddFile({
  project,
  revision,
  stopped,
  onClose,
}: {
  project: string;
  revision: number | undefined;
  stopped: boolean;
  onClose: () => void;
}) {
  const [path, setPath] = useState("");
  const [changesShown, setChangesShown] = useState(false);
  const request = fileAdd(path);
  const plan = useFilesPlan(request, revision);
  // Added, the form closes: the file's row is the table's to show, once it reads again.
  const { apply, refusal, chose } = useFilesApply(request, plan, revision, onClose);
  return (
    <AddFileView
      project={project}
      path={path}
      onPath={(text) => {
        setPath(text);
        chose();
      }}
      offer={{ plan: plan.data ?? null, refusal }}
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
  // server would refuse, naming the pattern, the moment it was selected again.
  const { apply, refusal } = useFilesApply(removal.request, plan, revision, onClose);
  return (
    <RemoveFileView
      removal={removal}
      project={project}
      offer={{ plan: plan.data ?? null, refusal }}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => apply.mutate()}
      busy={stopped || apply.isPending}
      onClose={onClose}
    />
  );
}
