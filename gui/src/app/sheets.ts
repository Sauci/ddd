import { sheetLoaded, sheetsToAskAgain } from "../lib/sheets";

/** Asks once more for each of the page's stylesheets the network failed, and resolves once each
 * such ask has loaded or failed (spec 2026-10-08 §6). Run before the page draws: the module
 * script running this waits for the parser's own stylesheets to load or fail, so a link whose
 * sheet did not load here (`sheetLoaded`) is one that failed. A second failure leaves the page
 * as it would have been. Anything this throws rejects what it answers, for the page to draw
 * all the same (`main.tsx`). */
export async function askSheetsAgain(document: Document): Promise<void> {
  const links = [...document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')];
  const again = sheetsToAskAgain(
    links.map((link) => ({ href: link.href, loaded: sheetLoaded(link.sheet) })),
  );
  await Promise.all(
    again.map(
      (href) =>
        new Promise<void>((resolve) => {
          const link = document.createElement("link");
          link.rel = "stylesheet";
          link.href = href;
          link.addEventListener("load", () => resolve());
          link.addEventListener("error", () => resolve());
          document.head.append(link);
        }),
    ),
  );
}
