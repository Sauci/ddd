import type { CompareReply, Finding, State } from "../api/types";
import { type FindingRow, keyedFindings, noRouteReason } from "./findings";
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
  if (row.fromBaseline) return "it is the baseline's own finding, not a place in your project";
  if (row.finding.pointer === "") {
    return "it is about the whole delivery being compared, not a place in one file";
  }
  return noRouteReason(row.finding, state);
}

/** One row of the Compare tab's table: `FindingRow`'s three fields, and which side of the
 * comparison it came from - structurally, from which field of `CompareReply` it was read out
 * of, never by matching a message's own text (`CompareReply.baseline_findings`'s own docstring
 * is explicit that a page must not do that). */
export interface CompareRow extends FindingRow {
  fromBaseline: boolean;
}

/** The Compare tab's own rows: `reply.findings` and `reply.baseline_findings` combined, worst
 * first, each carrying which one it came from. `findingRows` cannot build these - a `State`'s
 * own findings are only ever the open project's, one field, no second kind to tell apart - so
 * this reasons the same way (`keyedFindings`, then the Findings tab's own severity order) rather
 * than reusing it. The File column names a baseline row as the baseline's own, plainly: its file
 * can display with the very name one of the candidate's own files has (comparing a project
 * against itself is legal), and `sensor_hub.ddd.json` alone would then read as the reader's own
 * file rather than the baseline's. */
export function compareRows(reply: CompareReply): CompareRow[] {
  const rank: Record<Finding["severity"], number> = { error: 0, warning: 1, info: 2, ignore: 3 };
  const fromBaseline = new Set<Finding>(reply.baseline_findings);
  return keyedFindings([...reply.findings, ...reply.baseline_findings])
    .map(([finding, key]) => {
      const baseline = fromBaseline.has(finding);
      return { finding, key, fromBaseline: baseline, file: fileLabel(finding, baseline) };
    })
    .sort((one, other) => rank[one.finding.severity] - rank[other.finding.severity]);
}

/** The File column's own text: plain for a comparison's own finding, the same `baseName` the
 * Findings tab shows; named as the baseline's for one of those, so the display name it happens
 * to share with a candidate file (if any) cannot read as the reader's own. */
function fileLabel(finding: Finding, fromBaseline: boolean): string {
  const name = baseName(finding.file);
  return fromBaseline ? `the baseline's ${name}` : name;
}
