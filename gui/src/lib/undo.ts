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
import { refusedRead } from "./kept";
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
 * until the reader's next choice in the strip - Put back pressed again, the files read again, or
 * the strip closed - as a panel holds its own (`Refused`, lib/refusals.ts): what it says is worded
 * as the stack stands when it is said (`undoRefusal`). A `stale` one of an entry a newer one
 * covered goes as well, once that entry is back on top (`heldUnder`).
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
  /** Whether the state has named a newer entry on top since the strip held this `stale` refusal:
   * the entry may come back to the top, and the refusal goes then (`heldUnder`). */
  covered: boolean;
}

/** The refusal the strip holds once the Put back of `entry` was refused, whatever its code. */
export function undoRefused(error: Error, entry: Entry): UndoRefused {
  return {
    at: entry.at,
    label: entry.label,
    message: error.message,
    stale: isStale(error),
    covered: false,
  };
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
 * already - the preview of an entry asked again is refused again in the same words, and said once -
 * or a `stale` refusal of the same entry: an entry the server took off with one is refused as no
 * longer on top by any ask after it, which would say its going twice (16:M23). The first stands,
 * the strip asking no entry's preview again while it holds one (`previewAsked`). */
export function holding(
  held: readonly UndoRefused[],
  refused: UndoRefused,
): readonly UndoRefused[] {
  const already = held.some(
    (each) => same(each, refused) || (each.stale && refused.stale && each.at === refused.at),
  );
  return already ? held : [...held, refused];
}

/** Whether the strip asks for the preview of `entry`: not while it holds a `stale` refusal of it -
 * until the reader's next choice in the strip lets the refusal go, asking for the preview again
 * among them (`UndoShown.askAgain`), or the entry comes back to the top from under a newer one
 * (`heldUnder`). The server took the entry off with that refusal, and asked again it refuses it as
 * no longer on top; or it keeps the entry where a file could not be read, which the reader asks to
 * read again once they have mended it. A revision landing keys the preview anew, and asked then,
 * the same entry was asked twice - its going said twice (16:M23). */
export function previewAsked(held: readonly UndoRefused[], entry: { at: number }): boolean {
  return !held.some((refused) => refused.stale && refused.at === entry.at);
}

/** What the strip holds once the state names `top` on top: each `stale` refusal of an entry under
 * it marked `covered`, and those of `top` itself so marked let go. An entry a newer one covers
 * comes back to the top once another window undoes the newer edit, or the server takes it off, and
 * is offered whole then, its preview asked anew (`previewAsked`): a `stale` refusal of it, held
 * before the newer one went, may no longer hold - one as no longer on top no longer does. Any other
 * stays until the reader's next choice: one of the entry on top, never covered, keeps its preview
 * held back - the state may not yet name the edit the server refused it for - and one of an entry
 * gone, undone or taken off, keeps its words, numbers never reused. The very same list where
 * nothing moves. */
export function heldUnder(held: readonly UndoRefused[], top: Entry | null): readonly UndoRefused[] {
  if (top === null) return held;
  const standing = held
    .filter((refused) => !(refused.covered && refused.at === top.at))
    .map((refused) =>
      refused.stale && !refused.covered && refused.at < top.at
        ? { ...refused, covered: true }
        : refused,
    );
  const moved =
    standing.length !== held.length || standing.some((refused, at) => refused !== held[at]);
  return moved ? standing : held;
}

/** An answer the strip keeps to the preview of the entry numbered `at`: what an ask of that
 * entry's preview gets without asking the server (`answerOf`). */
export interface Answering<T> {
  at: number;
  answer: T;
}

/** The answer an ask of `entry`'s preview gets without asking the server: the one the strip keeps
 * for that entry, else `null`. A revision landing while an answer is on its way keys the preview
 * anew, and asked of the server again then, the same entry was asked twice (16:M23); another
 * entry's answer is none of this one's. */
export function answerOf<T>(answering: Answering<T> | null, entry: { at: number }): T | null {
  return answering !== null && answering.at === entry.at ? answering.answer : null;
}

/** What the strip keeps once `answer` has come: the very answer, where the strip holds the `stale`
 * refusal it came with (`held`), until the reader's next choice forgets it with what the strip
 * holds - decided at the ask, so that an ask in the frame before the refusal is drawn gets it and
 * sends nothing (16:M23); else nothing, where the answer kept was that one - an answer come, or a
 * refusal not held, the next revision asking the server again. An answer asked since, of another
 * entry, is kept as it is. */
export function settledAnswering<T>(
  answering: Answering<T> | null,
  answer: T,
  held: boolean,
): Answering<T> | null {
  return answering !== null && answering.answer === answer && !held ? null : answering;
}

/**
 * What the Undo strip says of `refused`, as the stack stands:
 * - refused `stale`, the server's own sentence, which names the file or the edit, and what it
 *   means for the reader: once the entry has left the stack (`gone`) - the server takes it off
 *   where the disk moved past it - that it can no longer be undone, the button naming another by
 *   then; while it is still there, as it stands, never as one no longer to be undone (a file that
 *   only could not be read keeps its entry). That nothing was put back, unless the strip says a
 *   refusal of the same entry before it that was not `stale` (`after`): an undo the disk refused
 *   half way put a file back and could not write it forward again, which that one says;
 * - any other, the server's own reason.
 */
export function undoRefusal(refused: UndoRefused, gone: boolean, after = false): string {
  if (!refused.stale) return `The undo was refused: ${refused.message}`;
  const meaning = gone ? `, so ${refused.label} can no longer be undone` : "";
  const nothing = after ? "" : ". Nothing was put back";
  return `${refused.message}${meaning}${nothing}; the page shows the files as they are.`;
}

/** What the Undo strip says in its preview's place where the preview failed - the server failing
 * on it, or not answering - rather than refusing it (`refusedRead`): no undo was asked, and nothing
 * was refused, so the strip says that reading the files failed, in the words of the failure. */
export function previewFailed(message: string): string {
  return `Reading the files failed: ${message}.`;
}

/** What the Undo button says once nothing is left to undo while the strip still says why an entry
 * left the stack: pressed, it closes the strip, and the control goes with it. */
export const NOTHING_LEFT = "Nothing left to undo";

/** What the Undo control and the strip it opens draw (`undoShown`). */
export interface UndoShown {
  /** What the button says: `Undo` and the entry on top (`undoButton`), `NOTHING_LEFT` with none
   * left while a refusal is said, and `null` where the control is not drawn at all. */
  label: string | null;
  /** Every refusal the strip says, in the order they came, each keyed by the entry it is of - and a
   * preview's failure, which is said among them in a sentence of its own (`previewFailed`). */
  refusals: readonly { key: string; text: string }[];
  /** The entry the strip offers to put back, once its preview has come: its line, its changes and
   * its Put back. `null` while none is. */
  preview: UndoPreview | null;
  /** Whether the strip says it is reading the files: the preview of the entry on top is asked for,
   * has not come, and nothing refused of it is said. */
  reading: boolean;
  /** Whether the strip offers to read the files again, where it offers nothing to put back: the
   * preview of the entry on top was refused - the server's answer, not a failure - and the server
   * keeps that entry, as it keeps one whose file could not be read (R22); or the strip asks no
   * preview of it, holding a `stale` refusal of it (`previewAsked`). */
  askAgain: boolean;
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
 *   open, or another window - goes unsaid, the newer one offered whole (branch 2, D0): the entry
 *   refused may come back to the top, and is offered whole then, its preview asked anew - `held`
 *   is what `heldUnder` leaves, which lets a `stale` refusal of it go as it comes back.
 * - **The preview's own refusal** is said in its place, and nothing is offered to put back: asked
 *   again and refused, the preview before it is no longer what the undo would do. One refused
 *   `stale` is the strip's to hold as its entry's (`previewRefused`), and is said once. A preview
 *   that failed - the server failing on it, or not answering - was refused by nobody, and is said
 *   so, in a sentence of its own (`previewFailed`).
 * - **Beside a refusal held of the entry on top**, said as it stands, the strip offers that entry
 *   again, whole, and so its Put back (R22): the reader may mend the file - make it readable or
 *   writable - and press again, with no need to close the strip, as a panel offers its plan beside
 *   a refusal held of its Apply (`offerShown`, lib/refusals.ts). Beside one that is not `stale` - a
 *   file that could not be written - as the revision on screen previews it, asked anew as each
 *   lands; beside a `stale` one as the strip read it before the refusal, which no revision asks
 *   again (`previewAsked`): once one lands, the strip offers to read the files again in its place.
 *   One the server took off is offered so until the state says it went.
 * - **Beside the preview's own refusal** of the entry on top - a refusal (`refusedRead`), the
 *   server keeping the entry, as it keeps one whose file could not be read - the strip offers to
 *   read the files again (R22): mended, the file is previewed there, and the entry offered whole
 *   once it is, never a Put back of files the strip has not read. A preview that failed - the
 *   server failing, or not answering - is asked again as the page's other failed reads are: at the
 *   next revision, or once the strip is closed and opened.
 */
export function undoShown(
  held: readonly UndoRefused[],
  state: State | null,
  asked: { data: UndoPreview | undefined; error: Error | null },
): UndoShown {
  const top = state?.undoable ?? null;
  const standing = held.filter((refused) => top === null || refused.at >= top.at);
  const own = top === null || asked.error === null ? null : undoRefused(asked.error, top);
  const failed = own !== null && !refusedRead(asked.error);
  const said =
    own === null || standing.some((refused) => same(refused, own)) ? standing : [...standing, own];
  const refusals = said.map((refused, index) => ({
    key: `${refused.at}:${refused.stale}:${refused.message}`,
    text:
      failed && refused === own
        ? previewFailed(refused.message)
        : undoRefusal(
            refused,
            top === null || refused.at > top.at,
            said.slice(0, index).some((before) => before.at === refused.at && !before.stale),
          ),
  }));
  const offered =
    top !== null && asked.error === null && asked.data !== undefined && asked.data.at === top.at
      ? asked.data
      : null;
  const asks = top !== null && previewAsked(held, top);
  const reading = asks && asked.error === null && offered === null;
  const askAgain = top !== null && offered === null && (!asks || refusedRead(asked.error));
  const label = undoButton(state) ?? (refusals.length > 0 ? NOTHING_LEFT : null);
  return { label, refusals, preview: offered, reading, askAgain };
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
