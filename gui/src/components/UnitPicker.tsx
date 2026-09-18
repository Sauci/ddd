import type { UnitSection } from "../lib/units";
import { ComboBox } from "../ui/ComboBox";

interface Props {
  name: string;
  sections: readonly UnitSection[];
  typed: string;
  onTyped: (text: string) => void;
  onPick: (unit: string | null) => void;
  note: string | undefined;
  isDisabled: boolean;
  /** A new value on every request to focus the field; `null` asks for no focus. */
  autoFocus: number | null;
}

/** The unit of one variable: the sections of lib/units.ts in React Aria's combobox. */
export function UnitPicker({
  name,
  sections,
  typed,
  onTyped,
  onPick,
  note,
  isDisabled,
  autoFocus,
}: Props) {
  return (
    <ComboBox
      label={`Unit of ${name}`}
      inputValue={typed}
      onInputChange={onTyped}
      sections={sections}
      onPick={(id) => {
        const chosen = sections
          .flatMap((section) => section.choices)
          .find((entry) => entry.id === id);
        if (chosen !== undefined) onPick(chosen.unit);
      }}
      note={note}
      isDisabled={isDisabled}
      autoFocus={autoFocus}
    />
  );
}
