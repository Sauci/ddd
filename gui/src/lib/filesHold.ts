import type { FilesPlanRequest } from "../api/client";
import type { FilesPlanReply, FilesReply, IncludedEntryReply, State } from "../api/types";

/**
 * What the Files tab holds of one Apply of its own - New file's, Add's or Remove's - until
 * `GET /api/files` shows it (Rulings F2 and F6, Ruling T6-1's hold: the page holds what it applied
 * wherever an answer would otherwise show the old state). The tab asks for its entries again once
 * the edit is answered, but `GET /api/files` reads the includes off the disk while the edit's own
 * analysis runs beside it, and its answer can come later than spec §3's 500 ms for an Apply's own
 * change; until it does, the tab would draw the entries from before the edit. What the edit
 * changed is drawn from the plan the page applied instead, as the answer will list it: the entry
 * New file or Add appended (`FilesAdded`), or no entry of the key Remove took out
 * (`FilesRemoved`).
 */
export type FilesHold = FilesAdded | FilesRemoved;

interface Held {
  /** The number the edit was answered with. */
  edit: number;
  /** The first revision the page saw include the edit; `null` until one has. */
  landed: number | null;
}

/** What New file or Add appended. */
export interface FilesAdded extends Held {
  /** The entry the plan appended, as `GET /api/files` lists it from then until the edit's
   * analysis lands: naming its file - the one New file creates, or the one Add names, which
   * `add_plan` refuses where it is not there - bringing that file alone, and with no finding of
   * the revision's own at it, the revision having never read it. The tab's row for it reads "not
   * read by the last analysis", what is not known yet of it, as it will once the answer carries
   * it. */
  entry: IncludedEntryReply;
}

/** What Remove took out. */
export interface FilesRemoved extends Held {
  /** The key Remove was asked with - a row's own (`FileRow.key`) - every entry of which
   * `remove_plan` takes out of the includes, whatever its words or its place: an entry's key is
   * its path as the server resolved it, the very key `GET /api/files` lists the entry by. A
   * pattern left that matches the file is no entry of that key, and keeps its own row and its
   * child row of the file, as the server keeps the file in the project (`FilesPlanReply.kept_by`).
   */
  removed: string;
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
 * absolute and posix-separated as `FilesReply.project`), asked for with `request`: for Remove, the
 * key it was asked with; for New file and Add, the entry the plan's change of the description
 * appends, its place read off that change's operation, its text off what the operation writes.
 * `null` where the plan changes no description of this project's, or, for New file and Add,
 * writes no entry there.
 *
 * An appended entry's key is the created file's own path where the plan creates one (New
 * file's, the one change with no fingerprint), and otherwise - Add's - the entry joined to the
 * description's directory, `.`, `..` and a doubled `/` folded as the path is read: the key the
 * server answers short of reading links, which it resolves through and the page cannot. A row's
 * selection reads it, and so does its join to `State.files` (`rowsOf`), only while it is held:
 * where a link makes the two keys differ, the held row reads as one the last analysis did not
 * read, until the answer carries it.
 */
export function filesHoldOf(
  edit: number,
  plan: FilesPlanReply,
  project: string,
  request: FilesPlanRequest,
): FilesHold | null {
  const operation = plan.changes.find((change) => change.file === project)?.operations[0];
  if (operation === undefined) return null;
  if (request.action === "remove") return { edit, removed: request.path, landed: null };
  if (operation.raw === null) return null;
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
 * `state` have come: ended for good, `null`, once an answer shows the edit (`shows`), once the
 * page's own undo has put the edit back (`undone`, the Undo strip's), or once an answer of the
 * first revision the page saw include the edit, or of a later one, has come, whatever it says;
 * else stamped with that revision the first time the state includes the edit; else the very same
 * hold, so that the page can tell nothing changed. Ended, it never comes back: an entry taken out
 * again after an answer carried it - by the tab's own Remove - is not drawn again, and an entry
 * put back after an answer left it out - by the page's own undo, or another window - is drawn as
 * the answers list it.
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
    if (shows(served, hold)) return null;
    if (hold.landed !== null && served.revision >= hold.landed) return null;
  }
  if (hold.landed !== null) return hold;
  if (state === null || state.edits < hold.edit) return hold;
  return { ...hold, landed: state.revision };
}

/** Whether `served` shows what `hold` holds: the entry appended, the same words at the same index;
 * or, for a removal, no entry of the key taken out left. */
function shows(served: FilesReply, hold: FilesHold): boolean {
  if ("entry" in hold) {
    return served.entries.some(
      (each) => each.index === hold.entry.index && each.entry === hold.entry.entry,
    );
  }
  return !served.entries.some((each) => each.key === hold.removed);
}

/** What the tab draws of `served`: the answer itself, with the held entry after its own while
 * an addition is held - appended, as the plan appends it - and without every entry of the key
 * while a removal is. The answer itself is left as it was. */
export function filesShown(hold: FilesHold | null, served: FilesReply): FilesReply {
  if (hold === null) return served;
  if ("entry" in hold) return { ...served, entries: [...served.entries, hold.entry] };
  return { ...served, entries: served.entries.filter((each) => each.key !== hold.removed) };
}
