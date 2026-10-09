/** One of the page's stylesheets as the page found it before drawing: its address, and whether
 * it loaded. */
export interface SheetLoad {
  href: string;
  loaded: boolean;
}

/** Whether a stylesheet loaded, from the sheet its link holds once its load has ended: only a
 * sheet whose rules the page can read did (spec 2026-10-08 §6). A link the network failed holds
 * none, as the HTML standard has it, or, in Chromium, a sheet whose rules no page may read, as
 * if it came from another origin: its `cssRules` throws a `SecurityError` (measured in Chrome
 * 153). Every stylesheet of this page is from its own origin, which its Content-Security-Policy
 * (`default-src 'self'`) allows alone, so one that loaded can be read. */
export function sheetLoaded(sheet: { readonly cssRules: unknown } | null): boolean {
  if (sheet === null) return false;
  try {
    void sheet.cssRules;
  } catch {
    return false;
  }
  return true;
}

/** The addresses of the page's stylesheets to ask for once more before it draws: those that did
 * not load (spec 2026-10-08 §6). On Windows a stylesheet's request was seen refused a socket
 * (`net::ERR_NO_BUFFER_SPACE`, run 37760106344), and the page then drew unstyled. Each address
 * once, in the page's order, however many links name it. */
export function sheetsToAskAgain(sheets: readonly SheetLoad[]): string[] {
  const again: string[] = [];
  for (const sheet of sheets) {
    if (!sheet.loaded && !again.includes(sheet.href)) again.push(sheet.href);
  }
  return again;
}
