import type { PlannedChange } from "../api/types";
import { baseName, hunkLines } from "../lib/units";

/**
 * The lines each file will get, as Show changes prints them: a variable's panel, a unit's and
 * the adoption's preview alike. A file the change creates has no line of its own yet, and is
 * named as new.
 */
export function Changes({ changes }: { changes: readonly PlannedChange[] }) {
  return (
    <div className="changes">
      {changes.flatMap((change) =>
        change.hunks.map((hunk) => (
          <pre key={`${change.file} ${hunk.line}`} className="hunk">
            <span className="where">
              {baseName(change.file)}, {change.fingerprint === null ? "new" : `line ${hunk.line}`}
            </span>
            {hunkLines(hunk).map((line) => (
              <span key={line.key} className={line.sign === "-" ? "removed" : "added"}>
                {line.sign} {line.text}
              </span>
            ))}
          </pre>
        )),
      )}
    </div>
  );
}
