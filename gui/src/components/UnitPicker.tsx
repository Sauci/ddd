import { enteredUnit, type UnitSection } from "../lib/units";
import { ComboBox } from "../ui/ComboBox";

interface Props {
  /** What the field is for: "Unit of ValueA", "Rename RPM to". */
  label: string;
  sections: readonly UnitSection[];
  typed: string;
  onTyped: (text: string) => void;
  onPick: (unit: string | null) => void;
  /** The list closed or the field was left: whatever was typed is dropped. */
  onClose: () => void;
  note: string | undefined;
  isDisabled: boolean;
  /** A new value on every request to focus the field; `null` asks for no focus. */
  autoFocus: number | null;
  /** "focus" opens the list as the field takes the focus, for a story to photograph it open. */
  menuTrigger?: "input" | "focus" | undefined;
}

/** A unit to choose - a variable's, or the spelling a unit is renamed to: the sections of
 * lib/units.ts or lib/projectUnits.ts in React Aria's combobox. */
export function UnitPicker({
  label,
  sections,
  typed,
  onTyped,
  onPick,
  onClose,
  note,
  isDisabled,
  autoFocus,
  menuTrigger,
}: Props) {
  return (
    <ComboBox
      label={label}
      inputValue={typed}
      onInputChange={onTyped}
      sections={sections}
      onPick={(id) => {
        const chosen = sections
          .flatMap((section) => section.choices)
          .find((entry) => entry.id === id);
        if (chosen !== undefined) onPick(chosen.unit);
      }}
      onEnter={(text) => {
        const unit = enteredUnit(sections, text);
        if (unit !== undefined) onPick(unit);
      }}
      onClose={onClose}
      note={note}
      isDisabled={isDisabled}
      autoFocus={autoFocus}
      menuTrigger={menuTrigger}
    />
  );
}
