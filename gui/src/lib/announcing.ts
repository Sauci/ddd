import type { SourceFile } from "../api/types";
import type { ProjectView, Route } from "./route";
import { baseName } from "./units";

/**
 * What the page says of itself (16:I13): the title the browser names each page by - its tab, its
 * history, a screen reader's list of pages - where every page was titled "ddd gui" alike.
 */

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
