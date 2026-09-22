import { baseName, hunkLines, type ShownChange } from "../lib/units";

/**
 * The lines each file will get, as Show changes prints them: a variable's panel, a unit's, the
 * adoption's preview and the undo strip alike. A file with no line of its own - one a change
 * creates, or one an undo takes away - is named by what happens to it instead.
 */
export function Changes({ changes }: { changes: readonly ShownChange[] }) {
  return (
    <div className="changes">
      {changes.flatMap((change) =>
        change.hunks.map((hunk) => (
          <pre key={`${change.file} ${hunk.line}`} className="hunk">
            <span className="where">
              {baseName(change.file)}, {change.note ?? `line ${hunk.line}`}
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
