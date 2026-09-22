import type { UnitPlanRequest } from "../api/client";
import type { Finding } from "../api/types";

/** The longest label `POST /api/edit` takes; see `Changes.label` in src/ddd/gui/contract.py. */
const LIMIT = 120;

/** What settling a key on every declaration of a variable is called when it comes to be
 * undone: the key reads as the noun it is - "the unit of ValueA", "the limits of ValueB". */
export function settleLabel(name: string, key: string): string {
  return fitted(`the ${key} of ${name}`);
}

/** What a change of the project's units is called. */
export function unitLabel(plan: UnitPlanRequest): string {
  if (plan.action === "adopt") return "the vocabulary adopted";
  if (plan.action === "rename") return fitted(`the rename of '${plan.unit}' to '${plan.to}'`);
  if (plan.action === "describe") return fitted(`the description of '${plan.unit}'`);
  if (plan.action === "add") return fitted(`'${plan.unit}' added to the vocabulary`);
  return fitted(`'${plan.unit}' removed from the vocabulary`);
}

/**
 * What a fix applied from the Findings tab is called.
 *
 * The one fix the tab offers is `missing-id`, whose route names the declaration it stamps, so
 * the sentence can name it too. Any other fix is named by its own title, which is the best the
 * page has and reads well enough after "Undo".
 */
export function fixLabel(finding: Finding, title: string): string {
  const named = finding.route === null ? null : finding.route.name;
  if (finding.check === "missing-id" && named !== null) return fitted(`the identity of ${named}`);
  return fitted(title);
}

/** A label as the api takes it: a long one cut short, so that no edit is ever refused for the
 * length of a name somebody chose. */
function fitted(label: string): string {
  return label.length <= LIMIT ? label : `${label.slice(0, LIMIT - 1)}…`;
}
