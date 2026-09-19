import type { ReactNode } from "react";

/** A short label on a tinted ground: a check's name, or a count. */
export function Chip({
  tone,
  children,
}: {
  tone: "error" | "warning" | "neutral";
  children: ReactNode;
}) {
  return <span className={`chip ${tone}`}>{children}</span>;
}
