import type { CompareReply, Finding } from "../api/types";
import { type FindingRow, keyedFindings } from "./findings";
import { baseName } from "./units";

/**
 * Why a comparison's finding leads nowhere - never `noRouteReason`, which answers that question
 * for the *open project's own* findings by asking what today's `state.files` says about the
 * finding's file. That is safe there because a Findings-tab finding is always about a file of
 * the very state being asked. A comparison finding is not one of those:
 *
 * - `compare`'s own findings (interface and storage differences) are filed on the candidate's
 *   whole project rather than a place in one file - `route_of` already answers `null` for
 *   exactly that shape, pointer `""` included.
 * - the baseline's own findings are marked route-less **at the source**, regardless of where
 *   their path resolves to - even one that happens to name a file of the open project, which
 *   comparing a project against itself makes legal (spec 2026-09-26-gui-compare-design.md §3).
 *
 * Reading `noRouteReason`'s own branches: asked of a baseline finding whose file resolves to the
 * *same* path as a live, loaded, `component`-kind file of the open project - with a pointer that
 * still names a real declaration there - every branch but the last is skipped and it answers
 * "there is nothing at that place any more", which is false; there is something there, this
 * finding is simply not about it. Whether the open project's own analysis can actually produce
 * that exact pointer collision is a narrower question than this function needs to answer, and I
 * have not driven that literal case by hand - only a milder one, a baseline at a *different* path
 * sharing a display name only, which does not reach that branch at all. What is certain without
 * running anything is `fromBaseline`, not `state`, so this takes that instead: a baseline finding
 * cannot be answered wrong by a question it is never asked.
 */
export function compareRouteReason(fromBaseline: boolean): string {
  return fromBaseline
    ? "it is the baseline's own finding, not a place in your project"
    : "it is about the whole delivery being compared, not a place in one file";
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
