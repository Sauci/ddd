import { type ReactNode, useLayoutEffect, useRef, useState } from "react";
import { openerNow, panelDrawn, panelGone, returnFromPanel } from "../app/focus";
import { Button } from "./Button";

interface Props {
  title: string;
  meta?: string;
  onClose: () => void;
  children: ReactNode;
}

/** A panel beside the page's main view, named by its title so a reader can find it again. Close
 * gives the focus back to where it was opened from (`returnFromPanel`, 16:I13): the control holding
 * the focus as it was first drawn, which its slot keeps while panels follow one another there. */
export function Panel({ title, meta, onClose, children }: Props) {
  const aside = useRef<HTMLElement>(null);
  const [opener] = useState(openerNow);
  useLayoutEffect(() => {
    const slot = aside.current === null ? null : panelDrawn(aside.current, title, opener);
    return () => panelGone(slot);
  }, [title, opener]);
  return (
    <aside ref={aside} className="panel" aria-label={title}>
      <header className="panel-header">
        <h2 tabIndex={-1} data-heading="panel">
          {title}
        </h2>
        <Button
          variant="link"
          aria-label={`Close ${title}`}
          onPress={() => {
            if (aside.current !== null) returnFromPanel(aside.current);
            onClose();
          }}
        >
          Close
        </Button>
      </header>
      {meta !== undefined && <p className="panel-meta">{meta}</p>}
      {children}
    </aside>
  );
}
