import type { FilesPlanReply, FilesReply, IncludedEntryReply, State } from "../api/types";

/**
 * What the Files tab holds of one Apply of its own - New file's or Add's - until `GET /api/files`
 * carries it (Ruling F2, Ruling T6-1's hold: the page holds what it applied wherever an answer
 * would otherwise show the old state). The tab asks for its entries again once the edit is
 * answered, but `GET /api/files` reads the includes off the disk while the edit's own analysis
 * runs beside it, and its answer can come later than spec §3's 500 ms for an Apply's own change;
 * until it does, the tab would draw the entries from before the edit. The held entry is drawn
 * from the plan the page applied instead, as the answer will list it.
 */
export interface FilesHold {
  /** The number the edit was answered with. */
  edit: number;
  /** The entry the plan appended, as `GET /api/files` lists it from then until the edit's
   * analysis lands: naming its file - the one New file creates, or the one Add names, which
   * `add_plan` refuses where it is not there - bringing that file alone, and with no finding of
   * the revision's own at it, the revision having never read it. The tab's row for it reads "not
   * read by the last analysis", what is not known yet of it, as it will once the answer carries
   * it. */
  entry: IncludedEntryReply;
  /** The first revision the page saw include the edit; `null` until one has. */
  landed: number | null;
}

/** Where an appended entry goes in the description: `project.includes[N]`, `entry_appended`'s
 * insertion (`ddd.lsp.units`) - or, where the description had no `includes`, the list set whole,
 * its one entry the first. */
const INSERTED = /^project\.includes\[(\d+)\]$/;

/** An entry naming a path from a root - `/` - or a drive - `C:` - rather than from the
 * description's own directory. */
const ABSOLUTE = /^(?:\/|[A-Za-z]:)/;

/**
 * What the tab holds of an edit answered as `edit`, applying `plan` to `project` (the description,
 * absolute and posix-separated as `FilesReply.project`): the entry the plan's change of the
 * description appends, its place read off that change's operation, its text off what the
 * operation writes. `null` where the plan appends none - a removal's writes no entry - or changes
 * no description of this project's.
 *
 * Its key is the created file's own path where the plan creates one (New file's, the one change
 * with no fingerprint), and otherwise - Add's - the entry joined to the description's directory,
 * `.`, `..` and a doubled `/` folded as the path is read: the key the server answers short of
 * reading links, which it resolves through and the page cannot. A row's selection reads it, and
 * so does its join to `State.files` (`rowsOf`), only while it is held: where a link makes the two
 * keys differ, the held row reads as one the last analysis did not read, until the answer
 * carries it.
 */
export function filesHoldOf(edit: number, plan: FilesPlanReply, project: string): FilesHold | null {
  const operation = plan.changes.find((change) => change.file === project)?.operations[0];
  if (operation === undefined || operation.raw === null) return null;
  const at = INSERTED.exec(operation.pointer);
  const written: unknown = JSON.parse(operation.raw);
  const text = String(Array.isArray(written) ? written[0] : written);
  const created = plan.changes.find((change) => change.fingerprint === null);
  const key = created === undefined ? joined(project, text) : created.file;
  return {
    edit,
    entry: {
      index: at === null ? 0 : Number(at[1]),
      entry: text,
      names: true,
      key,
      files: [key],
      findings: 0,
    },
    landed: null,
  };
}

/** `entry` read from `project`'s directory: itself where it is `ABSOLUTE`, else that directory
 * with each of its parts taken in turn - `..` leaving the last, `.` and an empty part leaving it
 * as it is. */
function joined(project: string, entry: string): string {
  if (ABSOLUTE.test(entry)) return entry;
  const parts = project.split("/").slice(0, -1);
  for (const part of entry.split("/")) {
    if (part === "..") {
      parts.pop();
    } else if (part !== "." && part !== "") {
      parts.push(part);
    }
  }
  return parts.join("/");
}

/**
 * The hold as it stands once `served` - the tab's last answer, `undefined` before any - and
 * `state` have come: ended for good, `null`, once an answer carries the entry at its own place,
 * once the page's own undo has put the edit back (`undone`, the Undo strip's), or once an answer
 * of the first revision the page saw include the edit, or of a later one, has come, whatever it
 * says; else stamped with that revision the first time the state includes the edit; else the
 * very same hold, so that the page can tell nothing changed. Ended, it never comes back: an entry
 * taken out again after an answer carried it - by the tab's own Remove - is not drawn again.
 */
export function filesHoldAfter(
  hold: FilesHold | null,
  undone: ReadonlyMap<number, number>,
  state: Pick<State, "revision" | "edits"> | null,
  served: FilesReply | undefined,
): FilesHold | null {
  if (hold === null) return null;
  if (undone.has(hold.edit)) return null;
  if (served !== undefined) {
    if (carries(served, hold.entry)) return null;
    if (hold.landed !== null && served.revision >= hold.landed) return null;
  }
  if (hold.landed !== null) return hold;
  if (state === null || state.edits < hold.edit) return hold;
  return { ...hold, landed: state.revision };
}

/** Whether `served` lists `entry` at its own place: the same words at the same index. */
function carries(served: FilesReply, entry: IncludedEntryReply): boolean {
  return served.entries.some((each) => each.index === entry.index && each.entry === entry.entry);
}

/** What the tab draws of `served`: the answer itself, with the held entry after its own while a
 * hold stands - appended, as the plan appends it. The answer itself is left as it was. */
export function filesShown(hold: FilesHold | null, served: FilesReply): FilesReply {
  if (hold === null) return served;
  return { ...served, entries: [...served.entries, hold.entry] };
}
