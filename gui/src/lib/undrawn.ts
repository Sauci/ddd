/** What the page says in the place of a page it could not draw (15:I5): a screen threw while it was
 * drawn - a reply it cannot draw, say - and the one error boundary under the masthead
 * (`app/ErrorBoundary.tsx`) draws this line where the screen was. It says what failed in the words
 * of what was thrown: an error's message, or its name where it has none, and anything else thrown
 * as `String` writes it. */
export function undrawnSentence(thrown: unknown): string {
  const words = thrown instanceof Error ? thrown.message || thrown.name : String(thrown);
  return `This page could not be drawn: ${words}`;
}
