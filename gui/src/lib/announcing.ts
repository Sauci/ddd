import type { SourceFile, UndoPreview } from "../api/types";
import { toldApartAll } from "./paths";
import type { ProjectView, Route } from "./route";
import { baseName, FILES_NAMED } from "./units";

/**
 * What the page says of itself (16:I13): the title the browser names each page by - its tab, its
 * history, a screen reader's list of pages - where every page was titled "ddd gui" alike; and the
 * line the heading says what the page last wrote on, where only "Updating the findings…" told of a
 * write, gone again before it is read wherever the analysis is quick.
 */

/** One of the page's own writes, as the page says it. */
export interface Write {
  /** An edit written, or an undo putting one back. */
  kind: "wrote" | "put back";
  /** What the page called the edit (`Changes.label`): "the unit of ValueA". */
  label: string;
  /** Every file it wrote, absolute and posix-separated, in the order the server names them; of an
   * undo, every file it put back. */
  files: readonly string[];
  /** Every file an undo took away, as `files` names them: one its preview names gone, which the
   * strip notes as removed (`shownUndo`, lib/undo.ts) - an adopted vocabulary's units file. */
  removed?: readonly string[];
}

/** One of the page's own writes, by the number the server answered it with (`EditReply.edit`,
 * `UndoReply.edit`). */
export interface NumberedWrite {
  edit: number;
  write: Write;
}

/** What an undo put back, as its preview says it: the edit's label, every file it puts back, and
 * apart from them every file it takes away, which its preview names gone. */
export function putBackOf(preview: UndoPreview): Write {
  return {
    kind: "put back",
    label: preview.label,
    files: preview.changes.filter((change) => !change.gone).map((change) => change.file),
    removed: preview.changes.filter((change) => change.gone).map((change) => change.file),
  };
}

/** How many files, as the panels count them: "1 file", "2 files". */
function fileCount(count: number): string {
  return `${count} file${count === 1 ? "" : "s"}`;
}

/** The files a write names: each by as much of its path as tells it apart from the others, every
 * one of four at most, else the first `FILES_NAMED` and how many more, as a plan's consequence
 * names them. */
function filesNamed(files: readonly string[]): string {
  const names = toldApartAll(files);
  return names.length <= FILES_NAMED + 1
    ? names.join(", ")
    : `${names.slice(0, FILES_NAMED).join(", ")} and ${names.length - FILES_NAMED} more`;
}

/**
 * What a write of the page's own says on the heading's line: "Wrote 2 files for the unit of
 * ValueA: controller.ddd.json, sensor_hub.ddd.json.", "Undid the unit of ValueA, putting back 1
 * file: controller.ddd.json." - the edit by the label the Undo control names it by, which reads
 * after "for" and "Undid" as it reads after "Undo". A file an undo took away is named apart, in the
 * strip's own word for it: "Undid the vocabulary adopted, putting back 1 file: demo.ddd.json, and
 * removing 1 file: units.ddd.json."
 */
export function writtenSentence({ kind, label, files, removed = [] }: Write): string {
  const count = fileCount(files.length);
  const named = files.length === 0 ? "" : `: ${filesNamed(files)}`;
  if (kind === "wrote") return `Wrote ${count} for ${label}${named}.`;
  const back = files.length > 0 || removed.length === 0 ? [`putting back ${count}${named}`] : [];
  const gone =
    removed.length === 0 ? [] : [`removing ${fileCount(removed.length)}: ${filesNamed(removed)}`];
  return `Undid ${label}, ${[...back, ...gone].join(", and ")}.`;
}

/** What the heading's line says of a write of the page's own: its sentence, and the number the
 * server answered the write with - by which a screen reader is told of a second write that says
 * what the first said, as of the first (`UpdatingStatus`). */
export interface WrittenLine {
  edit: number;
  sentence: string;
}

/** What the heading's line says of the page's last write (`last`): its sentence where it was
 * written after `since`, the number of the last write before the page was drawn - a change of page
 * lets it go, no longer the news of the page drawn; nothing before. */
export function writtenSince(last: NumberedWrite | null, since: number): WrittenLine | null {
  return last !== null && last.edit > since
    ? { edit: last.edit, sentence: writtenSentence(last.write) }
    : null;
}

/** The project screen's tabs, in the order they are shown. */
export const PROJECT_VIEWS: readonly ProjectView[] = [
  "graph",
  "table",
  "units",
  "types",
  "shared",
  "files",
  "findings",
  "compare",
];

/** The name each tab of the project screen is shown under, and its page titled by. */
export const VIEW_NAMES: Readonly<Record<ProjectView, string>> = {
  graph: "Graph",
  table: "Table",
  units: "Units",
  types: "Types",
  shared: "Shared files",
  files: "Files",
  findings: "Findings",
  compare: "Compare",
};

/** The tool, which every title ends with. */
const TOOL = "ddd gui";

/** What a title's names are told apart by, as the page's lines part their counts. */
const APART = " · ";

/** What a page's title is made of, as the page draws it. */
export interface Titled {
  /** A page is drawn: not while the page connects, is signed out, or the session failed. */
  drawn: boolean;
  /** The page the address asks for. */
  route: Route;
  /** The open project's name, as the heading names it; `null` where none is open, the start page
   * then drawn whatever the address asks for. */
  project: string | null;
  /** The files of the state followed, a component named by its own. */
  files: readonly SourceFile[];
}

/**
 * The title of the page drawn: the page's own name, then the open project's, then the tool's -
 * "Units · DemoDevice · ddd gui", "Controller · DemoDevice · ddd gui", "MapA · Controller ·
 * DemoDevice · ddd gui", "Open a project · ddd gui"; "ddd gui" alone before a page is drawn. A
 * component is named by its file's component, or its file's name where none is known yet. What a
 * page selects in it - a variable's panel, a unit's - is no page, and leaves the title as it was.
 */
export function pageTitle({ drawn, route: shown, project, files }: Titled): string {
  if (!drawn) return TOOL;
  if (shown.page === "start" || project === null) return ["Open a project", TOOL].join(APART);
  if (shown.page === "project") return [VIEW_NAMES[shown.view], project, TOOL].join(APART);
  const component = files.find((file) => file.path === shown.file)?.name ?? baseName(shown.file);
  const names = "view" in shown ? [shown.variable, component] : [component];
  return [...names, project, TOOL].join(APART);
}
