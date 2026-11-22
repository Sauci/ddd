import type { SessionInfo } from "../api/types";
import { baseName } from "./units";

/** The project the session says is open (`GET /api/session`'s `project`), as the page holds it. */
type Opened = NonNullable<SessionInfo["project"]>;

/**
 * What the page names the open project by, in its heading and its masthead: the project the state
 * it follows is of - `project`, that state's `State.project`, or `null` before the page has
 * followed one.
 *
 * The state carries the project's path and no name; the name is the session's, which the page asks
 * for as it loads and as it opens a project. So the session's name - or its path, where the
 * description gives none - while the session names the project the state is of, and before there
 * is a state; otherwise the file name of the state's own description. The server has one project
 * open at a time, and another page of it opened another: the session, asked again because the two
 * differ (`sessionAskedFor`), names that one once it answers.
 */
export function projectName(opened: Opened, project: string | null): string {
  if (project === null || project === opened.path) return opened.name ?? opened.path;
  return baseName(project);
}

/**
 * What the page asks the server again which project is open for (`["session"]`): the project the
 * state it follows is of, while the session it holds names another - `null` while the two agree,
 * before any state, and while the session names no project open. The page asks once as it loads,
 * and again as it opens a project itself; a project another page opens reaches it through the
 * state alone.
 *
 * The page asks once for each answer here (`App.tsx` keys its ask by it). A state of yet another
 * project, coming while an ask is out, is asked for again, since the answer on its way may name the
 * one before - and an ask made again drops that answer. An answer naming another project than the
 * state's asks nothing more for that state: it is one opened later still, whose state follows. A
 * session naming no project open is not asked again: no state is followed then, and the last one
 * followed is older than its answer.
 */
export function sessionAskedFor(opened: Opened | null, project: string | null): string | null {
  return opened !== null && project !== null && project !== opened.path ? project : null;
}
