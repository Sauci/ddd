import type { MouseEvent } from "react";
import { hrefOf, type Route } from "../lib/route";
import type { Part } from "../lib/unloaded";

/** A sentence whose parts are words, or words leading to a page (`Part`, lib/unloaded.ts): each of
 * those an address, followed without a reload as the tabs are (`LinkTabs`), and plain words where
 * no address can carry the name it leads to (`hrefOf`). */
export function Sentence({
  parts,
  onFollow,
}: {
  parts: readonly Part[];
  onFollow: (to: Route) => void;
}) {
  return (
    <>
      {parts.map((part, index) => {
        if (typeof part === "string") return part;
        const href = hrefOf(part.to);
        if (href === null) return part.text;
        return (
          <a
            // biome-ignore lint/suspicious/noArrayIndexKey: a part is its own position in its sentence
            key={index}
            className="button link sentence-link"
            href={href}
            onClick={(event: MouseEvent<HTMLAnchorElement>) => {
              // A modified or secondary click asks the browser for a new tab or window.
              const modified = event.ctrlKey || event.metaKey || event.shiftKey || event.altKey;
              if (modified || event.button !== 0) return;
              event.preventDefault();
              onFollow(part.to);
            }}
          >
            {part.text}
          </a>
        );
      })}
    </>
  );
}
