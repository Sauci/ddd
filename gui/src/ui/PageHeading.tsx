import { type ReactNode, useEffect, useRef } from "react";
import { takePageHeading } from "../app/focus";

/**
 * A page's heading: what names the page, and where the keyboard's focus goes after a change of
 * page, or a panel closing beside no table (16:I13) - drawn later than the change, a component's
 * page once its file is read, it takes the focus as it is drawn. Focusable from the page alone,
 * never a stop of Tab's.
 */
export function PageHeading({ children }: { children: ReactNode }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (heading.current !== null) takePageHeading(heading.current);
  });
  return (
    <h1 ref={heading} tabIndex={-1} data-heading="page">
      {children}
    </h1>
  );
}
