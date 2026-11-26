import type { CompareReply, Finding, State } from "../api/types";
import { counted, type FindingRow, findingCounts, keyedFindings, noRouteReason } from "./findings";
import { baseName } from "./units";

/**
 * Why a comparison's finding leads nowhere, said only where it does - a row that names a place
 * in the open project leads there, and the panel offers the way rather than a sentence.
 *
 * Three kinds of row, and which one this is is known structurally rather than guessed:
 *
 * - **the baseline's own findings**, marked route-less at the source whatever their path
 *   resolves to - even one naming a file of the open project, which comparing a project against
 *   itself makes legal (spec 2026-09-26-gui-compare-design.md §3). Answered first, before
 *   anything reads `state`, because that is the case `noRouteReason` cannot answer: asked of a
 *   baseline finding whose file *is* a live, loaded component of the open project, with a
 *   pointer that still names a declaration there, it would answer "there is nothing at that
 *   place any more", which is false - there is something there, this finding is simply not
 *   about it.
 * - **`compare`'s own findings**, filed at the candidate's project file with an empty pointer,
 *   which is how a check about the whole delivery reports itself. `noRouteReason` would call
 *   that file "a project file, which has no page yet" - true of the file, wrong about the
 *   finding, which does not want a page to lead to.
 * - **a plugin's comparison rule**, which files where its own `locate` puts it: a declaration in
 *   a component of the open project, with a real pointer. Those route, and this is never asked
 *   about one. When such a finding does not route - the file moved on since the analysis read
 *   it, the same race the Findings tab lives with - `noRouteReason` is exactly the right answer,
 *   and it is the open project's own file it is answering about.
 */
export function compareRouteReason(row: CompareRow, state: State): string {
  if (row.fromBaseline) return "It is the baseline's own finding, not a place in your project";
  if (row.finding.pointer === "") {
    return "It is about the whole delivery being compared, not a place in one file";
  }
  return noRouteReason(row.finding, state);
}

/** How a comparison names a file, for its table's File column and for its finding's panel - the
 * heading line, and each file its notes point at: by its base name for a finding of the open
 * project's own, and as the baseline's for one the baseline itself reports. The baseline's files
 * can display with the very name one of the open project's own has (comparing a project against
 * itself is legal), and `sensor_hub.ddd.json` alone would then read as the reader's own file
 * rather than the baseline's. */
export function fileNameIn(fromBaseline: boolean): (path: string) => string {
  return fromBaseline ? baselineFileName : baseName;
}

function baselineFileName(path: string): string {
  return `the baseline's ${baseName(path)}`;
}

/** One row of the Compare tab's table: `FindingRow`'s three fields, and which side of the
 * comparison it came from - structurally, from which field of `CompareReply` it was read out
 * of, never by matching a message's own text (`CompareReply.baseline_findings`'s own docstring
 * is explicit that a page must not do that). */
export interface CompareRow extends FindingRow {
  fromBaseline: boolean;
}

/** The Compare tab's own rows: `reply.findings` and `reply.baseline_findings` combined, worst
 * first, each carrying which one it came from - keyed by `keyedFindings`, in the Findings tab's
 * own severity order, the order `GET /api/findings` answers the open project's own findings in.
 * The File column names a baseline row as the baseline's own (`fileNameIn`). */
export function compareRows(reply: CompareReply): CompareRow[] {
  const rank: Record<Finding["severity"], number> = { error: 0, warning: 1, info: 2, ignore: 3 };
  const fromBaseline = new Set<Finding>(reply.baseline_findings);
  return keyedFindings([...reply.findings, ...reply.baseline_findings])
    .map(([finding, key]) => {
      const baseline = fromBaseline.has(finding);
      return { finding, key, fromBaseline: baseline, file: fileNameIn(baseline)(finding.file) };
    })
    .sort((one, other) => rank[one.finding.severity] - rank[other.finding.severity]);
}

/** The line above the Compare tab's table: the statements the reply's two lists make, each once
 * as `ddd compare` counts them (decision 14.3), where the table lists a baseline's disagreement on
 * each file it concerns (`compareRows`). Never ending in "updating": it counts a reply of its own,
 * not the revision. */
export function compareLine(reply: CompareReply): string {
  return findingCounts(reply.statements, false);
}

/**
 * What the Compare tab says under a verdict that counts the open project's own errors (14:I1): that
 * the project has some, how many, that the verdict counts them as `ddd compare`'s exit code does,
 * and where they are listed - the comparison's table lists none of them, and a project whose every
 * error is its own was told it cannot replace the baseline above a line saying there was nothing to
 * report. `null` for a project with none (`CompareReply.own_errors` at 0).
 *
 * Counted as the Findings tab's line counts them, each once (`State.statements`, decision 14.3),
 * where `state` is of the revision the reply was read from: `own_errors` counts a disagreement on
 * each file it concerns, two where that line says one, and so says only whether there are any. Of
 * another revision - the server answered from one the page has not followed yet - the line says the
 * project has errors of its own, and no count.
 */
export function ownErrorsLine(reply: CompareReply, state: State): string | null {
  if (reply.own_errors === 0) return null;
  const count = reply.revision === state.revision ? state.statements.error : null;
  const errors = count === null ? "errors" : counted(count, "error", "errors");
  const them = count === 1 ? "it" : "them";
  return (
    `This project has ${errors} of its own, and the verdict counts ${them} as ddd compare ` +
    `does: the Findings tab lists ${them}.`
  );
}

/**
 * A comparison the reader asked for: the baseline's path, trimmed, and the ask's number, counted
 * from the first ask the page made. `ComparePage` keys its query on this, so that every ask is a
 * query of its own (`nextAsk`).
 */
export interface Ask {
  readonly baseline: string;
  readonly number: number;
}

/**
 * The ask a press of Compare, or an Enter, makes after `previous`: the path `typed` names
 * (`baselineOf`), numbered one more than the ask before it, whatever either baseline is.
 *
 * A baseline asked for again is therefore a new query, sent again, and the server reads the file as
 * it now stands: a query keyed on the path alone was served from the answer the page held, and a
 * refusal for a file that did not exist then, or a verdict for a delivery written over since,
 * stood until the path - or the project - changed. A baseline that comes back after another is no
 * exception: no number repeats, so nothing is answered from an older ask.
 */
export function nextAsk(previous: Ask | null, typed: string): Ask {
  return { baseline: baselineOf(typed), number: (previous?.number ?? 0) + 1 };
}

/**
 * The path a baseline typed names: trimmed - a path with a stray space at either end is not a path
 * under the root the server would find - and without the pair of like quotes round it, double or
 * single, that it may have been copied with: Windows' Copy as path writes double ones, a shell's
 * quoting single ones. A quote alone, or two unlike, are the path's own characters. The server
 * reads a baseline so too (`_unquoted`, src/ddd/gui/queries.py, 16:M3); this is the path asked for,
 * which the verdict names (`verdictLine`).
 */
export function baselineOf(typed: string): string {
  const trimmed = typed.trim();
  const first = trimmed.charAt(0);
  const quoted = trimmed.length > 1 && (first === '"' || first === "'") && trimmed.endsWith(first);
  return quoted ? trimmed.slice(1, -1) : trimmed;
}

/** Whether `typed` asks for nothing, the field's Compare and its Enter then doing nothing: it names
 * no path (`baselineOf`) - nothing but spaces, or quotes round nothing. */
export function asksNothing(typed: string): boolean {
  return baselineOf(typed) === "";
}

/** The verdict drawn of a comparison, naming the baseline it was asked for (16:M2): the field may
 * hold another typed since and not asked, whose verdict this is not. `verdict` is the reply's,
 * whether the open project can replace that baseline, as `ddd compare` exits on. */
export function verdictLine(verdict: boolean, baseline: string): string {
  return `This project ${verdict ? "can" : "cannot"} replace the baseline '${baseline}'.`;
}

/**
 * What the Compare tab holds while another tab is shown (16:M2): what its field holds and the
 * comparison last asked for - the verdict being that ask's answer, keyed by it - so that leaving
 * the tab and coming back finds both as they were left. Held in the page's memory, above the tab,
 * and never in the address, which a link or a bookmark would carry to another page; and of one
 * project, `project`, its description's path as the state names it: another project's tab starts
 * with nothing (`heldFor`), the verdict being about this one.
 */
export interface CompareHeld {
  readonly project: string;
  readonly typed: string;
  readonly asked: Ask | null;
}

/** What the Compare tab of `project` holds: `held` where that is of `project`, and otherwise
 * nothing typed and nothing asked - before the tab was first shown (`null`), or where what it held
 * is another project's. */
export function heldFor(held: CompareHeld | null, project: string): CompareHeld {
  return held !== null && held.project === project ? held : { project, typed: "", asked: null };
}

/** `held` with `typed` in its field, and the ask it holds untouched: typing asks nothing. */
export function typedIn(held: CompareHeld, typed: string): CompareHeld {
  return { ...held, typed };
}

/** `held` asking for what its field holds (`nextAsk`): the comparison its verdict will answer. */
export function askedIn(held: CompareHeld): CompareHeld {
  return { ...held, asked: nextAsk(held.asked, held.typed) };
}

/** What the Compare form says under its field: the paths it takes, and which of them run code. A
 * project or component given as the baseline is read as a description is, so the plugins it names
 * run; a dumped dictionary is data, and runs none. */
export const BASELINE_ACCEPTS =
  "Accepts a dumped dictionary, or a project or component description, at a path under the " +
  "directory ddd gui was started in. A project or component given as the baseline runs the " +
  "plugins it names; a dumped dictionary runs none.";
