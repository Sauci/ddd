import type { TypePlanRequest, UnitPlanRequest } from "../api/client";
import type { Finding, State, UndoneChange } from "../api/types";
import type { Mode } from "./declarations";
import { elementLabel } from "./objectValues";
import { baseName, type ShownChange } from "./units";

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

/** What a change of one of the project's types is called when it comes to be undone. */
export function typeLabel(plan: TypePlanRequest): string {
  if (plan.action === "rename") return fitted(`the rename of '${plan.name}' to '${plan.to}'`);
  return fitted(`the ${plan.key} of ${plan.name}`);
}

/** What a declaration added to a component's interface is called when it comes to be undone -
 * the verb the mode settled on, naming the variable and the component it joins: "reading ValueC
 * into Controller", "declaring Pressure in Controller". */
export function declareLabel(mode: Mode, typed: string, component: string): string {
  return mode === "read"
    ? fitted(`reading ${typed} into ${component}`)
    : fitted(`declaring ${typed} in ${component}`);
}

/** What a declaration taken out of a component's interface is called when it comes to be
 * undone - the variable and the component it leaves, the same two names `declareLabel` joins
 * the other way. */
export function removeLabel(name: string, component: string): string {
  return fitted(`removing ${name} from ${component}`);
}

/** What setting one element of an object's values is called when it comes to be undone - the
 * cell `elementLabel` phrases and the object it belongs to: "element 3 of CurveA", "element 2,
 * 4 of MapA". */
export function valueLabel(name: string, row: number, column: number, shape: number[]): string {
  return fitted(`${elementLabel(row, column, shape)} of ${name}`);
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

/** An undo's changes as `Changes` prints them: a file the edit created is taken away again, and
 * is named as removed. */
export function shownUndo(changes: readonly UndoneChange[]): ShownChange[] {
  return changes.map(({ file, gone, hunks }) => ({ file, hunks, note: gone ? "removed" : null }));
}

/** What the Undo button says, or `null` when there is nothing to undo: no project open yet, no
 * state arrived yet, or a session that has written nothing. */
export function undoButton(state: State | null): string | null {
  const undoable = state?.undoable ?? null;
  return undoable === null ? null : `Undo ${undoable.label}`;
}

/** What an undo would put back, in one sentence naming the files, as part 1's consequence line
 * names the files a change is applied to. */
export function undoConsequence(changes: readonly UndoneChange[]): string {
  const files = changes.map((change) => baseName(change.file));
  return `Puts back ${plural(files.length)}: ${files.join(", ")}`;
}

/** What the button that writes says. */
export function undoAction(changes: readonly UndoneChange[]): string {
  return `Put back ${plural(changes.length)}`;
}

function plural(count: number): string {
  return `${count} file${count === 1 ? "" : "s"}`;
}
