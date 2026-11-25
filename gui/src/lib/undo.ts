import type {
  ConstantPlanRequest,
  FilesPlanRequest,
  RasterPlanRequest,
  SectionPlanRequest,
  TypePlanRequest,
  UnitPlanRequest,
} from "../api/client";
import type { Finding, PlanReply, State, UndoneChange, UndoPreview } from "../api/types";
import type { Mode } from "./declarations";
import { relativeToProject } from "./findings";
import { elementLabel } from "./objectValues";
import { isStale } from "./refusals";
import { changedNames, type ShownChange } from "./units";

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

/** What a change of one of the project's constants is called when it comes to be undone - as
 * `typeLabel`'s, with `add` and `remove` besides: a constant, unlike a type, can be declared
 * and taken away by the same tab that edits it. */
export function constantLabel(plan: ConstantPlanRequest): string {
  if (plan.action === "rename") return fitted(`the rename of '${plan.name}' to '${plan.to}'`);
  if (plan.action === "add") return fitted(`'${plan.name}' declared as a constant`);
  if (plan.action === "remove") return fitted(`'${plan.name}' removed from the constants`);
  return fitted(`the ${plan.key} of ${plan.name}`);
}

/** What a change of one of the project's sections is called when it comes to be undone - as
 * `constantLabel`'s, `add` and `remove` besides: a section, like a constant, can be declared and
 * taken away by the same tab that edits it. */
export function sectionLabel(plan: SectionPlanRequest): string {
  if (plan.action === "rename") return fitted(`the rename of '${plan.name}' to '${plan.to}'`);
  if (plan.action === "add") return fitted(`'${plan.name}' declared as a section`);
  if (plan.action === "remove") return fitted(`'${plan.name}' removed from the sections`);
  return fitted(`the ${plan.key} of ${plan.name}`);
}

/** What a change of one of the project's rasters is called when it comes to be undone - as
 * `sectionLabel`'s, `add` and `remove` besides: a raster, like a section, can be declared and
 * taken away by the same tab that edits it. */
export function rasterLabel(plan: RasterPlanRequest): string {
  if (plan.action === "rename") return fitted(`the rename of '${plan.name}' to '${plan.to}'`);
  if (plan.action === "add") return fitted(`'${plan.name}' declared as a raster`);
  if (plan.action === "remove") return fitted(`'${plan.name}' removed from the rasters`);
  return fitted(`the ${plan.key} of ${plan.name}`);
}

/** What a change of the project's files is called when it comes to be undone, in words true of
 * what the change did - to the includes, never "the project": a file a pattern keeps in stays part
 * of the project once its own entry is gone (`FilesPlanReply.kept_by`).
 *
 * A `create`'s new file by the name `answered` - the plan the server gave for it - creates it
 * under: the name of its change that carries no fingerprint, as a created file's change alone
 * does (`PlannedChange.fingerprint`). `ddd.file_plans.create_plan` makes that name from the one
 * typed and a suffix of its own, and the label takes it as made rather than making it again. An
 * `add`'s by `path` exactly as typed, relative to the description or absolute, since that text is
 * the entry the includes gain. A `remove`'s by its key - a row's absolute path - named relative to
 * `project`'s directory (`relativeToProject`), as the table names a pattern's child: a pattern in a
 * directory reads `lib/*.ddd.json`, never its last part, which another pattern may end in - a base
 * name loses the very directory that tells the two apart. The cost: a key reached through a link
 * to a directory is named by where it leads, a spelling no entry has; and a key outside the
 * description's directory by its base name alone, `relativeToProject`'s own fallback. */
export function filesLabel(plan: FilesPlanRequest, answered: PlanReply, project: string): string {
  if (plan.action === "create") return fitted(`the creation of ${createdBy(answered)}`);
  if (plan.action === "add") return fitted(`'${plan.path}' added to the includes`);
  return fitted(`'${relativeToProject(plan.path, project)}' removed from the includes`);
}

/** Every file `answered` creates, quoted by its name among the files the plan writes - one, for
 * every plan `create_plan` makes. */
function createdBy(answered: PlanReply): string {
  const names = changedNames(answered.changes);
  return answered.changes
    .flatMap((change, at) => (change.fingerprint === null ? [`'${names[at]}'`] : []))
    .join(", ");
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

/** What an undo of a pasted table is called: the object, not an element, because a paste is
 * every element at once. */
export function pasteLabel(name: string): string {
  return fitted(`the values of ${name}`);
}

/** What the cells typed into the grid and applied together are called when they come to be
 * undone: the one element they set (`valueLabel`), or how many of the object's they set - "3
 * elements of CurveA", which one undo puts back. */
export function valuesLabel(
  name: string,
  cells: readonly { row: number; column: number }[],
  shape: number[],
): string {
  const [only] = cells;
  if (only !== undefined && cells.length === 1) {
    return valueLabel(name, only.row, only.column, shape);
  }
  return fitted(`${cells.length} elements of ${name}`);
}

/**
 * What a fix applied from the Findings tab is called.
 *
 * The tab offers the fixes `ddd.finding_fixes` plans: a `missing-id` finding's identity, and a
 * `definition-mismatch` finding's reconciliations, one for each key it disagrees on. An
 * identity's route names the declaration it stamps, so the sentence names it too. Any other fix
 * is named by its own title, which is the best the page has, said as a fix: a title is a sentence
 * of its own, and after "Undo" it ran on as one.
 */
export function fixLabel(finding: Finding, title: string): string {
  const named = finding.route === null ? null : finding.route.name;
  if (finding.check === "missing-id" && named !== null) return fitted(`the identity of ${named}`);
  return fitted(`the fix "${title}"`);
}

/** A label as the api takes it: a long one cut short, so that no edit is ever refused for the
 * length of a name somebody chose. Counted and cut in code points, as the api counts the limit:
 * cut in UTF-16 units, a character past the plane of the first 65,536 - an emoji - was cut in
 * half, and the lone half refused the edit as json no file can hold (3:M5). */
function fitted(label: string): string {
  const points = [...label];
  return points.length <= LIMIT ? label : `${points.slice(0, LIMIT - 1).join("")}…`;
}

/** An undo's changes as `Changes` prints them: a file the edit created is taken away again, and
 * is named as removed. */
export function shownUndo(changes: readonly UndoneChange[]): ShownChange[] {
  return changes.map(({ file, gone, hunks }) => ({ file, hunks, note: gone ? "removed" : null }));
}

/** An entry of the undo stack as the state names it (`State.undoable`). */
interface Entry {
  at: number;
  label: string;
}

/**
 * What the Undo strip holds of a refusal of one entry's undo, its preview's or its Put back's,
 * until the reader's next choice in the strip - Put back pressed again, or the strip closed - as a
 * panel holds its own (`Refused`, lib/refusals.ts): what it says is worded as the stack stands
 * when it is said (`undoRefusal`).
 *
 * `stale` is the server's code for a file the entry would put back gone, changed on disk, or that
 * could not be read - or for the entry no longer the one on top. The server takes the entry off
 * the stack where the disk moved past it (`ddd.gui.session.Session.undo`), and keeps it where a
 * file only could not be read: the page reads which from the state, as the stack moves.
 */
export interface UndoRefused {
  /** The entry the refusal is of (`UndoableEdit.at`). */
  at: number;
  /** What the page calls that entry. */
  label: string;
  /** The server's own sentence. */
  message: string;
  stale: boolean;
}

/** The refusal the strip holds once the Put back of `entry` was refused, whatever its code. */
export function undoRefused(error: Error, entry: Entry): UndoRefused {
  return { at: entry.at, label: entry.label, message: error.message, stale: isStale(error) };
}

/** What the strip holds once the preview of `entry` was refused: the refusal, where it is `stale`,
 * which the server may have taken the entry off the stack with, so that the strip says why the
 * entry went beside the one under it once the state names that one; none for any other, which the
 * strip says in the preview's place for as long as the preview stands refused (`undoShown`). */
export function previewRefused(error: Error, entry: Entry): UndoRefused | null {
  return isStale(error) ? undoRefused(error, entry) : null;
}

/** Whether two refusals are one: of one entry, in one code and in the same words. */
function same(one: UndoRefused, other: UndoRefused): boolean {
  return one.at === other.at && one.stale === other.stale && one.message === other.message;
}

/** `held` with `refused` after the others, and the very same list where it holds that refusal
 * already: the preview of an entry asked again is refused again in the same words, and said once. */
export function holding(
  held: readonly UndoRefused[],
  refused: UndoRefused,
): readonly UndoRefused[] {
  return held.some((each) => same(each, refused)) ? held : [...held, refused];
}

/**
 * What the Undo strip says of `refused`, as the stack stands:
 * - refused `stale`, the server's own sentence, which names the file or the edit, and what it
 *   means for the reader: once the entry has left the stack (`gone`) - the server takes it off
 *   where the disk moved past it - that it can no longer be undone, the button naming another by
 *   then; while it is still there, as it stands, never as one no longer to be undone (a file that
 *   only could not be read keeps its entry);
 * - any other, the server's own reason.
 */
export function undoRefusal(refused: UndoRefused, gone: boolean): string {
  if (!refused.stale) return `The undo was refused: ${refused.message}`;
  const meaning = gone ? `, so ${refused.label} can no longer be undone` : "";
  return `${refused.message}${meaning}. Nothing was put back; the page shows the files as they are.`;
}

/** What the Undo button says once nothing is left to undo while the strip still says why an entry
 * left the stack: pressed, it closes the strip, and the control goes with it. */
export const NOTHING_LEFT = "Nothing left to undo";

/** What the Undo control and the strip it opens draw (`undoShown`). */
export interface UndoShown {
  /** What the button says: `Undo` and the entry on top (`undoButton`), `NOTHING_LEFT` with none
   * left while a refusal is said, and `null` where the control is not drawn at all. */
  label: string | null;
  /** Every refusal the strip says, in the order they came, each keyed by the entry it is of. */
  refusals: readonly { key: string; text: string }[];
  /** The entry the strip offers to put back, once its preview has come: its line, its changes and
   * its Put back. `null` while none is. */
  preview: UndoPreview | null;
  /** Whether the strip says it is reading the files: the preview of the entry on top is asked for,
   * has not come, and nothing refused of it is said. */
  reading: boolean;
}

/**
 * What the Undo strip says and offers (16:M23): the refusals it holds (`held`), the state's entry
 * on top, and that entry's preview as its query has it (`asked`).
 *
 * - **An entry that has left the stack** - the server took it off, its preview or its Put back
 *   refused because the disk moved past it - is said, as no longer to be undone, for as long as
 *   the strip holds its refusal, beside whatever the stack's top then offers: the entry under it,
 *   offered whole, its preview and its Put back, with no need to close the strip. Each entry taken
 *   off while the strip is open is said, in the order they went: the save that refused one often
 *   refuses the next, an edit before it having written the same file. An entry left the stack is
 *   one above the state's top, numbers only ever growing, or any where the stack is empty.
 * - **A refusal held of an entry a newer one covers** - an edit a panel makes while the strip is
 *   open - goes unsaid, the newer one offered whole (branch 2, D0): the entry refused may come
 *   back to the top, and is offered whole then.
 * - **The preview's own refusal** is said in its place, and nothing is offered to put back: asked
 *   again and refused, the preview before it is no longer what the undo would do. One refused
 *   `stale` is the strip's to hold as its entry's (`previewRefused`), and is said once.
 * - **Beside a refusal held of the entry on top**, said as it stands, the strip offers that entry
 *   again, whole, as the revision on screen previews it, and so its Put back (R22): the reader may
 *   mend the file - make it readable or writable - and press again, with no need to close the
 *   strip, as a panel offers its plan beside a refusal held of its Apply (`offerShown`,
 *   lib/refusals.ts). One the server took off is offered so until the state says it went.
 */
export function undoShown(
  held: readonly UndoRefused[],
  state: State | null,
  asked: { data: UndoPreview | undefined; error: Error | null },
): UndoShown {
  const top = state?.undoable ?? null;
  const standing = held.filter((refused) => top === null || refused.at >= top.at);
  const own = top === null || asked.error === null ? null : undoRefused(asked.error, top);
  const said =
    own === null || standing.some((refused) => same(refused, own)) ? standing : [...standing, own];
  const refusals = said.map((refused) => ({
    key: `${refused.at}:${refused.stale}:${refused.message}`,
    text: undoRefusal(refused, top === null || refused.at > top.at),
  }));
  const offered =
    top !== null && asked.error === null && asked.data !== undefined && asked.data.at === top.at
      ? asked.data
      : null;
  const reading = top !== null && asked.error === null && offered === null;
  const label = undoButton(state) ?? (refusals.length > 0 ? NOTHING_LEFT : null);
  return { label, refusals, preview: offered, reading };
}

/** What the Undo button says, or `null` when there is nothing to undo: no project open yet, no
 * state arrived yet, or a session that has written nothing. */
export function undoButton(state: State | null): string | null {
  const undoable = state?.undoable ?? null;
  return undoable === null ? null : `Undo ${undoable.label}`;
}

/** What an undo would do, in one sentence naming the files, as part 1's consequence line names the
 * files a change is applied to: those it puts back, and apart from them those it takes away, which
 * its preview names gone - "Puts back 1 file: demo.ddd.json, and removes 1 file: units.ddd.json",
 * as the heading's line says them once the undo is answered (`writtenSentence`, 16:I13). Each file
 * is told apart among every file the undo writes (`changedNames`). */
export function undoConsequence(changes: readonly UndoneChange[]): string {
  const names = changedNames(changes);
  const back = changes.flatMap((change, at) => (change.gone ? [] : [`${names[at]}`]));
  const gone = changes.flatMap((change, at) => (change.gone ? [`${names[at]}`] : []));
  const said = [
    ...(back.length > 0 || gone.length === 0
      ? [`puts back ${plural(back.length)}: ${back.join(", ")}`]
      : []),
    ...(gone.length === 0 ? [] : [`removes ${plural(gone.length)}: ${gone.join(", ")}`]),
  ].join(", and ");
  return `${said.charAt(0).toUpperCase()}${said.slice(1)}`;
}

/** What the button that writes says, counting the files it takes away apart from those it puts
 * back, as the line above it does: "Put back 1 file and remove 1 file". */
export function undoAction(changes: readonly UndoneChange[]): string {
  const gone = changes.filter((change) => change.gone).length;
  const back = changes.length - gone;
  if (gone === 0) return `Put back ${plural(back)}`;
  if (back === 0) return `Remove ${plural(gone)}`;
  return `Put back ${plural(back)} and remove ${plural(gone)}`;
}

function plural(count: number): string {
  return `${count} file${count === 1 ? "" : "s"}`;
}

/** The queries an undo leaves alone, by the first part of their key.
 *
 * - **What an analysis made**: the graph, a comparison against a baseline, the findings - the
 *   Findings tab's pages and a component's own whole file's - and an object's values, which
 *   `GET /api/values` reads off the analysed dictionary rather than its file. An undo changes none
 *   of them before its own analysis lands, and that moves the revision each of their keys holds,
 *   so they are asked for anew then. Where a listed finding leads is read off its file as it
 *   stands, and asked again before then it could lead to what the undo put back while its words
 *   still name what the analysis read; its own analysis answers both at once.
 * - **The strip's own preview**: the undo closes the strip, and the entry it previews next is the
 *   one the next state names, under a key of its own - asked again, the preview of the entry put
 *   back is refused as no longer on top.
 * - **No file's**: the session, and the projects found.
 */
const LEFT_ALONE: ReadonlySet<unknown> = new Set([
  "graph",
  "compare",
  "findings",
  "values",
  "undo",
  "session",
  "projects",
]);

/**
 * Whether a query is asked for again once an undo has put its files back (spec §6: the change
 * shows where it was made): only what the undo can change before its own analysis lands. An undo
 * can put back any edit - an interface, a vocabulary's entry, the project's own includes - and is
 * answered before its analysis, so the revision a screen keys its queries by moves only an
 * analysis later: every query drawing a file as it stands, a tab's rows, an entry's panel or a
 * plan whose fingerprints the undo spent is asked again now. What its analysis changes is asked
 * for once that lands, by the revision in its key (`LEFT_ALONE`).
 */
export function askedAgainAfterUndo(queryKey: readonly unknown[]): boolean {
  return !LEFT_ALONE.has(queryKey[0]);
}
