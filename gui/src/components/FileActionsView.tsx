import { useRef } from "react";
import type { FilesPlanReply } from "../api/types";
import { asksComponentName, type FileRemoval, previewOf } from "../lib/files";
import { shownChanges } from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { ComboBox } from "../ui/ComboBox";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";

export interface FileActionsViewProps {
  onNewFile: () => void;
  onAddFile: () => void;
}

/**
 * The Files tab's two actions that start from no row (design §3): New file and Add a file, above
 * the table, each opening its form beside it where a row's own panel would open. Remove starts
 * from a row instead - selecting one opens `RemoveFileView` - so it has no button here.
 */
export function FileActionsView({ onNewFile, onAddFile }: FileActionsViewProps) {
  return (
    <div className="file-actions">
      <Button variant="secondary" onPress={onNewFile}>
        New file
      </Button>
      <Button variant="secondary" onPress={onAddFile}>
        Add a file
      </Button>
    </div>
  );
}

/**
 * Where one of the three actions stands: its plan once it has come, and why it cannot be applied -
 * the two facts `ConstantPanelView`'s own `Offer` keeps for each of a constant's changes, less its
 * `pending`: these plans are never kept on screen while the next is asked for, as `SharedAdd`'s
 * own three - debounced the same way (spec §6) - keep none of theirs either (fix round 2).
 */
export interface FileOffer {
  /** The plan; `null` while it is being asked for, when it was refused, and while the form does
   * not yet hold what the request needs (`fileCreate`, `fileAdd`). */
  plan: FilesPlanReply | null;
  /** Why the plan was refused when asked for - the server's own sentence - or why applying it
   * was; `null` when neither was (`refusalShown`, `lib/refusals.ts`, chose which). */
  refusal: string | null;
}

export interface NewFileViewProps {
  /** `FilesReply.project`: what the preview names a file relative to, as the table does. */
  project: string;
  /** The kinds the chooser offers: `FilesReply.creatable`, the server's own list in its own order,
   * never a copy of it made here. */
  creatable: readonly string[];
  /** What the Kind field holds: any text, since the chooser takes what is typed as readily as
   * what is picked - the server refuses a kind it creates no file of, in its own words. */
  kind: string;
  onKind: (text: string) => void;
  /** The chooser's own pick or Enter, apart from typing (`onKind`): a discrete commit, which
   * `FilesPage.tsx` takes at once rather than waiting out a pause as it does for typing (spec
   * §6, Ruling T12-3). */
  onKindPicked: (text: string) => void;
  /** What the File name field holds: the name before `.ddd.json`, which the server adds. */
  name: string;
  onName: (text: string) => void;
  /** What the Component name field holds, drawn for a component alone (`asksComponentName`). */
  component: string;
  onComponent: (text: string) => void;
  offer: FileOffer;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  /** Applying, or the server stopped: nothing can be changed or applied. */
  busy: boolean;
  onClose: () => void;
}

/**
 * New file (design §3): a kind, a name, and a component's name for a component - then the plan
 * the server makes of them, or its refusal, asked for again once the reader pauses (debounced,
 * spec §6 - `FilesPage.tsx`'s own concern, not this picture of props); applied the way every
 * other panel applies its own. Nothing here judges a name: a name with a dot, a file there
 * already, a component's name taken are each the server's to refuse, in its words.
 */
export function NewFileView(props: NewFileViewProps) {
  return (
    <Panel title="New file" onClose={props.onClose}>
      <div className="declare-fields">
        <ComboBox
          label="Kind"
          inputValue={props.kind}
          onInputChange={props.onKind}
          sections={[
            {
              id: "kinds",
              title: "Kind",
              choices: props.creatable.map((kind) => ({ id: kind, label: kind, detail: "" })),
            },
          ]}
          // The choice's own id is the word the field holds, so picking one from the list and
          // typing it out by hand leave the form in the very same state - `SharedAddView`'s own
          // chooser takes a vocabulary the same way. `onPick` and `onEnter` go to `onKindPicked`,
          // never `onKind`: both are a discrete commit, not typing, however the field reads
          // afterwards.
          onPick={props.onKindPicked}
          onEnter={props.onKindPicked}
          onClose={() => undefined}
          isDisabled={props.busy}
        />
        <label className="panel-field">
          File name
          <input
            type="text"
            value={props.name}
            disabled={props.busy}
            onChange={(event) => props.onName(event.target.value)}
          />
        </label>
        {asksComponentName(props.kind) && (
          <label className="panel-field">
            Component name
            <input
              type="text"
              value={props.component}
              disabled={props.busy}
              onChange={(event) => props.onComponent(event.target.value)}
            />
          </label>
        )}
      </div>
      {/* Where the file goes, in the words `create_plan`'s docstring states it in: beside the
          description, and appended to its includes in the same edit - the one shape
          `session._confined` lets a file be created in. */}
      <p className="file-note">
        The file is created beside the project description and added to its includes.
      </p>
      <Preview
        offer={props.offer}
        project={props.project}
        removing={null}
        variant="primary"
        changesShown={props.changesShown}
        onChangesShown={props.onChangesShown}
        onApply={props.onApply}
        busy={props.busy}
      />
    </Panel>
  );
}

export interface AddFileViewProps {
  /** `FilesReply.project`: what the preview names a file relative to - an error the added file
   * brings among them - as the table names a pattern's matched file. */
  project: string;
  /** What the Path field holds, sent exactly as typed (`fileAdd`). */
  path: string;
  onPath: (text: string) => void;
  offer: FileOffer;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  busy: boolean;
  onClose: () => void;
}

/**
 * Add a file (design §3): a path, then the plan the server makes of it, asked for again once the
 * reader pauses (debounced, spec §6 - `FilesPage.tsx`'s own concern, not this picture of props) -
 * with the errors the server counts the file bringing, listed as it lists them, and never refused
 * for them: the spec's "informs rather than refuses". Where the server could not judge what the
 * file brings, its own sentence says so, drawn as it comes; nothing here says it in other words.
 */
export function AddFileView(props: AddFileViewProps) {
  return (
    <Panel title="Add a file" onClose={props.onClose}>
      <div className="declare-fields">
        <label className="panel-field">
          Path
          <input
            type="text"
            value={props.path}
            disabled={props.busy}
            onChange={(event) => props.onPath(event.target.value)}
          />
        </label>
      </div>
      {/* What the path is read against, as `add_plan` reads it - joined to the description's
          own directory - and that the text itself is the entry appended, as its docstring says:
          "appended to the root's includes as written". */}
      <p className="file-note">
        A path from the project description's directory, added to its includes as written.
      </p>
      <Preview
        offer={props.offer}
        project={props.project}
        removing={null}
        variant="primary"
        changesShown={props.changesShown}
        onChangesShown={props.onChangesShown}
        onApply={props.onApply}
        busy={props.busy}
      />
    </Panel>
  );
}

export interface RemoveFileViewProps {
  /** The row the route selects, and the plan asked for it (`fileRemoval`). */
  removal: FileRemoval;
  /** `FilesReply.project`: what the file a pattern keeps in is named relative to. */
  project: string;
  /** The press that asks the plan, present while it waits (`removalAsked`, `lib/files.ts`). */
  waiting?: (() => void) | undefined;
  offer: FileOffer;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  busy: boolean;
  onClose: () => void;
}

/**
 * A row's own panel (design §3's Remove): the plan the server makes of taking its entry out of
 * the includes, asked for as soon as the row is selected within the page, or the server's refusal
 * in its own words - a file whose declarations something uses, naming the first error it would
 * leave; a file only a pattern brings in, naming the pattern. The page never decides on its own
 * whether Remove is possible: the button is drawn under a plan the server made, and nowhere else.
 *
 * The row the page was loaded with waits instead (`waiting`, P18b-10): its plan re-analyses the
 * project, running its plugins, so the panel waits - saying only that what removing the row would
 * change is planned when the reader asks - and offers the press that asks it. The press leaves the
 * keyboard's focus on the region it was in (ruling P19a-20).
 *
 * An allowed removal carries, where there is one, the server's sentence saying it was not judged,
 * and the pattern that keeps the file in the project all the same - of the three values only a
 * files plan carries, `kept_by` is the one the page puts into words of its own (`previewOf`).
 */
export function RemoveFileView(props: RemoveFileViewProps) {
  // Where the press that asks the plan puts the keyboard's focus: the button pressed goes as the
  // plan is asked, and focus left on it would fall to the page's body, a keyboard's place lost.
  // Moved by hand, as ComboBox's own `autoFocus` moves it.
  const region = useRef<HTMLElement>(null);
  const waiting = props.waiting;
  return (
    <Panel title={props.removal.title} onClose={props.onClose}>
      {/* Focusable by the page alone (`tabIndex` -1), never a stop of Tab's own: kept so once the
          plan is drawn, since focus on an element that stops being focusable falls to the body. */}
      <section
        ref={region}
        tabIndex={-1}
        className="panel-offer"
        aria-label="Remove from the includes"
      >
        {waiting !== undefined ? (
          <>
            <p className="quiet">
              Opened from an address: what removing it would change is planned when you ask.
            </p>
            <Button
              variant="secondary"
              onPress={() => {
                region.current?.focus();
                waiting();
              }}
            >
              Plan its removal
            </Button>
          </>
        ) : (
          <Preview
            offer={props.offer}
            project={props.project}
            removing={props.removal.request.path}
            variant="secondary"
            changesShown={props.changesShown}
            onChangesShown={props.onChangesShown}
            onApply={props.onApply}
            busy={props.busy}
          />
        )}
      </section>
    </Panel>
  );
}

/**
 * One action's preview: why it cannot be applied, if it cannot; then, once its plan has come,
 * what `previewOf` (`lib/files.ts`) says it draws beside the plan - the errors the server counts an
 * added file bringing, the server's sentence where the change could not be judged, the pattern
 * keeping a removed file in - then what the change writes, its lines once Show changes opens them,
 * and the button applying it, where `previewOf` says there is one. The shape of
 * `ConstantPanelView`'s own `Outcome`, with the three lines only a files plan carries. What is
 * drawn, and in what words, is `previewOf`'s to decide; only whether the changes are open is this
 * view's, being the reader's own toggle.
 */
function Preview({
  offer,
  project,
  removing,
  variant,
  changesShown,
  onChangesShown,
  onApply,
  busy,
}: {
  offer: FileOffer;
  /** `FilesReply.project`: what the preview names its files relative to. */
  project: string;
  /** The key a removal was asked with, or `null` for New file and Add (`previewOf`). */
  removing: string | null;
  variant: "primary" | "secondary";
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  busy: boolean;
}) {
  const { plan, refusal } = offer;
  const preview = plan === null ? null : previewOf(plan, project, removing);
  return (
    <>
      {refusal !== null && (
        <p className="panel-refusal" role="status">
          {refusal}
        </p>
      )}
      {plan !== null && preview !== null && (
        <>
          {preview.brought.length > 0 && (
            <ul className="panel-findings file-brings">
              {/* The check and the file it is filed on, then the server's message on a line of
                  its own: a file after the message would read as the sentence's last word. */}
              {preview.brought.map((row) => (
                <li key={row.key}>
                  <Chip tone="error">{row.check}</Chip> <span className="quiet">{row.file}</span>
                  <p>{row.message}</p>
                </li>
              ))}
            </ul>
          )}
          {preview.unjudged !== null && <p className="file-unjudged">{preview.unjudged}</p>}
          {preview.kept !== null && <p className="file-note">{preview.kept}</p>}
          <p className="consequence">{preview.consequence}</p>
          {preview.apply !== null && (
            <>
              {changesShown && <Changes changes={shownChanges(plan.changes)} />}
              <div className="panel-actions">
                <Button variant="link" onPress={() => onChangesShown(!changesShown)}>
                  {changesShown ? "Hide changes" : "Show changes"}
                </Button>
                <Button variant={variant} isDisabled={busy} onPress={onApply}>
                  {preview.apply}
                </Button>
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
