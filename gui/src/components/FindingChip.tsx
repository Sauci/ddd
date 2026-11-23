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
