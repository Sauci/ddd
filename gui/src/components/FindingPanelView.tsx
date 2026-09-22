import type { MouseEvent } from "react";
import type { Finding, FixReply } from "../api/types";
import { baseName, consequence } from "../lib/units";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";

export interface FindingPanelViewProps {
  finding: Finding;
  /** What the button that follows it says, or `null` when it leads nowhere. */
  label: string | null;
  /** The address it carries, so the link is a real one; `null` with `label`. */
  href: string | null;
  /** Why it leads nowhere, said when `label` is `null`. */
  reason: string;
  /** Following it, without a reload - `LinkTabs`' own pairing of an href with a handler. */
  onOpen: () => void;
  fixes: FixReply | null;
  /** The title of the fix being previewed, or `undefined` while none is. */
  chosen: string | undefined;
  onChoose: (title: string | undefined) => void;
  changesShown: boolean;
  onChangesShown: (shown: boolean) => void;
  onApply: () => void;
  refusal: string | null;
  busy: boolean;
  onClose: () => void;
}

/** One finding's panel (spec 5.2), drawn from what the api answered: a picture of its props. */
export function FindingPanelView(props: FindingPanelViewProps) {
  const { finding, label, href, reason, fixes, chosen, refusal, busy } = props;
  return (
    <Panel title={finding.check} meta={baseName(finding.file)} onClose={props.onClose}>
      <p>
        <Chip tone={toneOf(finding.severity)}>{finding.check}</Chip>{" "}
        <span className="quiet">{finding.severity}</span>
      </p>
      <p>{finding.message}</p>
      {finding.notes.length > 0 && (
        <ul className="panel-notes">
          {finding.notes.map((note) => (
            <li key={`${note.pointer} ${note.file ?? ""} ${note.message}`}>
              {note.message}
              {note.file !== null && (
                <>
                  {" "}
                  <span className="quiet">{baseName(note.file)}</span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {label !== null && href !== null ? (
        <p>
          <a
            className="button primary"
            href={href}
            onClick={(event: MouseEvent<HTMLAnchorElement>) => {
              // A modified or secondary click asks the browser for a new tab or window.
              const modified = event.ctrlKey || event.metaKey || event.shiftKey || event.altKey;
              if (modified || event.button !== 0) return;
              event.preventDefault();
              props.onOpen();
            }}
          >
            {label}
          </a>
        </p>
      ) : (
        <p className="quiet">{reason}</p>
      )}
      {fixes?.fixes.map((fix) => (
        <section key={fix.title} className="panel-offer" aria-label={fix.title}>
          <Button
            variant={fix.title === chosen ? "primary" : "secondary"}
            isDisabled={busy}
            onPress={() => props.onChoose(fix.title === chosen ? undefined : fix.title)}
          >
            {fix.title}
          </Button>
          {fix.title === chosen &&
            (refusal !== null ? (
              <p className="panel-refusal" role="status">
                {refusal}
              </p>
            ) : (
              <p className="consequence">{consequence(fix.changes)}</p>
            ))}
          {fix.title === chosen && refusal === null && fix.changes.length > 0 && (
            <>
              {props.changesShown && <Changes changes={fix.changes} />}
              <div className="panel-actions">
                <Button variant="link" onPress={() => props.onChangesShown(!props.changesShown)}>
                  {props.changesShown ? "Hide changes" : "Show changes"}
                </Button>
                <Button variant="primary" isDisabled={busy} onPress={props.onApply}>
                  Apply to {fix.changes.length} file{fix.changes.length === 1 ? "" : "s"}
                </Button>
              </div>
            </>
          )}
        </section>
      ))}
    </Panel>
  );
}

/** The chip's tone for a severity; `info` is the quiet one the design system calls neutral. */
function toneOf(severity: Finding["severity"]) {
  return severity === "error" ? "error" : severity === "warning" ? "warning" : "neutral";
}
