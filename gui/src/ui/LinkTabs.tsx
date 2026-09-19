import type { MouseEvent } from "react";

export interface LinkTab {
  href: string;
  label: string;
  current: boolean;
  onFollow: () => void;
}

/** Tabs that are addresses, so a reload and the back button keep the one open. */
export function LinkTabs({ label, tabs }: { label: string; tabs: readonly LinkTab[] }) {
  return (
    <nav className="tabs" aria-label={label}>
      {tabs.map((tab) => (
        <a
          key={tab.href}
          href={tab.href}
          aria-current={tab.current ? "page" : undefined}
          onClick={(event: MouseEvent<HTMLAnchorElement>) => {
            // A modified or secondary click asks the browser for a new tab or window.
            const modified = event.ctrlKey || event.metaKey || event.shiftKey || event.altKey;
            if (modified || event.button !== 0) return;
            event.preventDefault();
            tab.onFollow();
          }}
        >
          {tab.label}
        </a>
      ))}
    </nav>
  );
}
