import type { ReactNode } from "react";

/**
 * A page's heading: what names the page, and where the keyboard's focus goes where it has nowhere
 * better - a panel closing beside no table (16:I13). Focusable from the page alone, never a stop of
 * Tab's.
 */
export function PageHeading({ children }: { children: ReactNode }) {
  return (
    <h1 tabIndex={-1} data-heading="page">
      {children}
    </h1>
  );
}
