import type { Finding } from "../api/types";

/** How the baseline's own errors are captioned wherever `ddd.deliveries.read_baseline` forwards
 * one (`src/ddd/deliveries.py`) - the one signal the wire carries for "this is the baseline's
 * fact, not the candidate's": `CompareReply.findings`'s own docstring names this prefix as what
 * marks such a finding apart from `compare`'s own. */
const BASELINE_PREFIX = "in the baseline: ";

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
 * Asking `state.files` about a baseline finding would answer a question about the *live* project
 * rather than about why a fact reported of the *baseline* has nothing to open, and could answer
 * it wrong: task 2's own regression (fixed at `59b4793`, "never route a baseline finding") is
 * exactly a baseline finding whose path coincides with a live, loaded component file - asked of
 * `noRouteReason`, that file's current, live shape would answer "there is nothing at that place
 * any more" for a place that, right now, still has something at it. This reasons from the
 * finding alone, so it cannot repeat that mistake.
 */
export function compareRouteReason(finding: Finding): string {
  return finding.message.startsWith(BASELINE_PREFIX)
    ? "it is the baseline's own finding, not a place in your project"
    : "it is about the whole delivery being compared, not a place in one file";
}
