import type { ReactNode } from "react";

/**
 * A plain table of what a panel lists, as `.panel-declarations` draws it - a type's members and
 * uses, a constant's, a raster's, a section's, Compare's renames - in a box of its own, which
 * scrolls the table sideways where the window is too narrow for it, rather than the page (16:M9).
 */
export function PanelTable({ children }: { children: ReactNode }) {
  return (
    <div className="panel-table">
      <table className="panel-declarations">{children}</table>
    </div>
  );
}
