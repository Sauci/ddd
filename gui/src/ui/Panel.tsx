import type { ReactNode } from "react";
import { Button } from "./Button";

interface Props {
  title: string;
  meta?: string;
  onClose: () => void;
  children: ReactNode;
}

/** A panel beside the page's main view, named by its title so a reader can find it again. */
export function Panel({ title, meta, onClose, children }: Props) {
  return (
    <aside className="panel" aria-label={title}>
      <header className="panel-header">
        <h2>{title}</h2>
        <Button variant="link" aria-label={`Close ${title}`} onPress={onClose}>
          Close
        </Button>
      </header>
      {meta !== undefined && <p className="panel-meta">{meta}</p>}
      {children}
    </aside>
  );
}
