import type { ReactNode } from "react";

/** A message across the page: an error is announced at once, a warning when the reader is ready. */
export function Banner({ tone, children }: { tone: "error" | "warning"; children: ReactNode }) {
  return (
    <div className={`banner ${tone}`} role={tone === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}
