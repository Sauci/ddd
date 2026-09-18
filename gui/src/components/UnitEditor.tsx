import { useEffect, useRef, useState } from "react";

interface Props {
  name: string;
  unit: string;
  disabled: boolean;
  onConfirm: (unit: string) => void;
}

/** A unit shown as a button; editing it takes Enter to confirm and Escape to cancel. */
export function UnitEditor({ name, unit, disabled, onConfirm }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(unit);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) input.current?.focus();
  }, [editing]);

  if (!editing) {
    return (
      <button
        type="button"
        className="value"
        aria-label={`Change unit of ${name}`}
        disabled={disabled}
        onClick={() => {
          setDraft(unit);
          setEditing(true);
        }}
      >
        {unit === "" ? <span className="quiet">none</span> : unit}
      </button>
    );
  }
  return (
    <input
      ref={input}
      className="unit"
      aria-label={`Unit of ${name}`}
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          setEditing(false);
          if (draft !== unit) onConfirm(draft);
        } else if (event.key === "Escape") {
          setEditing(false);
        }
      }}
      onBlur={() => setEditing(false)}
    />
  );
}
