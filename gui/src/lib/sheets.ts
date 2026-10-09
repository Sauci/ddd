/** One of the page's stylesheets as the page found it before drawing: its address, and whether
 * the network answered it. */
export interface SheetLoad {
  href: string;
  loaded: boolean;
}

/** Whether the network answered a stylesheet's request, from the sheet its link holds once
 * loading has ended: only a sheet whose rules the page can read did (spec 2026-10-08 §6, the GET
 * rule's "never after any HTTP answer"). A link the network failed holds none, as the HTML
 * standard has it, or, in Chromium, a sheet whose rules no page may read, as if it came from
 * another origin: its `cssRules` throws a `SecurityError`. An HTTP error answer holds a sheet
 * too, empty but readable, so it counts as answered, the way the GET rule counts one (both
 * measured in Chrome 153). Every stylesheet of this page is from its own origin, which its
 * Content-Security-Policy (`default-src 'self'`) allows alone, so one the network answered can
 * be read. */
export function sheetLoaded(sheet: { readonly cssRules: unknown } | null): boolean {
  if (sheet === null) return false;
  try {
    void sheet.cssRules;
  } catch {
    return false;
  }
  return true;
}

/** The addresses of the page's stylesheets to ask for once more before it draws: those the
 * network failed (spec 2026-10-08 §6). On Windows a stylesheet's request was seen refused a
 * socket (`net::ERR_NO_BUFFER_SPACE`, run 37760106344), and the page then drew unstyled. Each
 * address once, in the page's order, however many links name it. */
export function sheetsToAskAgain(sheets: readonly SheetLoad[]): string[] {
  const again: string[] = [];
  for (const sheet of sheets) {
    if (!sheet.loaded && !again.includes(sheet.href)) again.push(sheet.href);
  }
  return again;
}
