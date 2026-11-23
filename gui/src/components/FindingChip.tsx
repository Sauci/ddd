import type { Finding } from "../api/types";
import { toneOf } from "../lib/findings";
import { Chip } from "../ui/Chip";

/** A finding's check as a chip, toned by its severity, with the severity's own word after it, so
 * that the severity is not told by the colour alone (`ddd check`'s words: error, warning, info). The
 * word ends in a space of its own, so that the next chip of a cell reads as a word apart. */
export function FindingChip({ severity, check }: { severity: Finding["severity"]; check: string }) {
  return (
    <>
      <Chip tone={toneOf(severity)}>{check}</Chip>
      <span className="severity-word"> {severity}</span>{" "}
    </>
  );
}

/** A finding's chip and its word on a table's one line - the Findings tab's, Compare's - where the
 * word is drawn whole at any width, being what says the severity where the colour cannot (16:M14):
 * a check's name too long to stand beside it in its column is cut short in its chip instead, which
 * the panel its row opens names whole (`.finding-line`, ui.css). */
export function FindingLine({ severity, check }: { severity: Finding["severity"]; check: string }) {
  return (
    <span className="finding-line">
      <FindingChip severity={severity} check={check} />
    </span>
  );
}
