import type { Finding } from "../api/types";

/**
 * Each finding of a list, paired with a React key stable across re-renders of that list.
 *
 * Position alone is not a key: the list is rebuilt on every revision, and an unrelated finding
 * appearing or disappearing earlier in it would shift every key after it. Content alone is not
 * enough either, since the API sends no line or column: a consumer whose unit and limits both
 * disagree gets two `definition-mismatch` findings at the same pointer, and a producer with
 * several disagreeing consumers gets one finding mirrored onto it per consumer, so two distinct
 * findings can share severity, check, pointer and message. The key is that content together
 * with which repeat of it this is - 0 for the first, 1 for the next with the same content, and
 * so on - which tells such findings apart while staying stable when a differently-keyed finding
 * elsewhere in the list comes or goes.
 */
export function keyedFindings(findings: readonly Finding[]): (readonly [Finding, string])[] {
  const seen = new Map<string, number>();
  return findings.map((finding) => {
    const content = JSON.stringify([
      finding.severity,
      finding.check,
      finding.pointer,
      finding.message,
    ]);
    const occurrence = seen.get(content) ?? 0;
    seen.set(content, occurrence + 1);
    return [finding, `${content}#${occurrence}`] as const;
  });
}

/**
 * A list of findings with each statement in it once: the first of those that share severity,
 * check and message, wherever they are filed.
 *
 * The analysis files a disagreement on each of the files it concerns - mirrored onto the
 * producer for every consumer that disagrees with it - so that an editor shows it in each. A list
 * that speaks of one variable across its files, as its panel's does, would say the same sentence
 * once per file.
 */
export function distinctFindings(findings: readonly Finding[]): Finding[] {
  const said = new Set<string>();
  return findings.filter((finding) => {
    const statement = JSON.stringify([finding.severity, finding.check, finding.message]);
    if (said.has(statement)) return false;
    said.add(statement);
    return true;
  });
}
