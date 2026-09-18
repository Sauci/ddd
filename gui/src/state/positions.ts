/**
 * Where the reader dragged each module of one project, kept in that browser rather than on the
 * server: spec 5.1 - "the arrangement is the reader's, and local." One JSON object per project,
 * keyed by the project's own path, so that two open projects never share one arrangement.
 *
 * Storage is a convenience, never a condition of the canvas opening: every read and write is
 * wrapped so that an empty, unreadable or refused store behaves as no positions remembered,
 * rather than as a page that fails to render.
 */

function storageKey(project: string): string {
  return `ddd-gui:positions:${project}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** The arrangement the reader made for one project, as their browser remembers it. */
export function savedPositions(project: string): Record<string, { x: number; y: number }> {
  try {
    const raw = localStorage.getItem(storageKey(project));
    if (raw === null) return {};
    const parsed: unknown = JSON.parse(raw);
    return isRecord(parsed) ? (parsed as Record<string, { x: number; y: number }>) : {};
  } catch {
    return {};
  }
}

/** Remembers one module's position for one project, beside whatever else was remembered. */
export function rememberPosition(project: string, path: string, x: number, y: number): void {
  const positions = { ...savedPositions(project), [path]: { x, y } };
  try {
    localStorage.setItem(storageKey(project), JSON.stringify(positions));
  } catch {
    // A refusal to write - quota, a private tab, storage disabled - must not fail the drag
    // that asked for it.
  }
}

/** Forgets every position remembered for one project, e.g. before `Tidy` lays it out again. */
export function forgetPositions(project: string): void {
  try {
    localStorage.removeItem(storageKey(project));
  } catch {
    // Same convenience guarantee as rememberPosition.
  }
}
