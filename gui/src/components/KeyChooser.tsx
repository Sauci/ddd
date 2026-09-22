import type { UnitsReply, VariableKeyOffer } from "../api/types";
import { pickerSections, rawOf } from "../lib/units";
import { chooserSections, enteredValue } from "../lib/variableKeys";
import { ComboBox } from "../ui/ComboBox";
import { UnitPicker } from "./UnitPicker";

export interface KeyChooserProps {
  /** The key's offer, as the panel's own answer carries it. */
  offer: VariableKeyOffer;
  /** Whose key it is - a variable's name or a type's - for the field's label and the first
   * section's title. */
  owner: string;
  /** What already states a unit, for the unit picker's first section: every declaration's for a
   * variable, the one value it states for a type. */
  inPlay: ReadonlyMap<string | null, string[]>;
  /** Which key is being chosen. */
  keyName: string;
  units: UnitsReply;
  /** What the field reads: what is being typed, else the value settled on. */
  typed: string;
  /** What narrows the list: "" unless the reader is typing (part 1's rule, spec 5.3). */
  narrow: string;
  onTyped: (text: string) => void;
  onChosen: (raw: string | null) => void;
  /** The list closed or the field was left: what was typed there is dropped. */
  onPickerClosed: () => void;
  /** The two fields of a range, while the key is `limits`. */
  range: { min: string; max: string };
  onRange: (range: { min: string; max: string }) => void;
  note: string | undefined;
  busy: boolean;
  /** A new value on every request to focus the field; `null` asks for no focus. */
  focus: number | null;
  /** "focus" opens the list as the field takes the focus, for a story to photograph it open. */
  pickerTrigger?: "input" | "focus" | undefined;
}

/** One key's chooser (spec 5.2): the values in play, state nothing, and the field the key takes.
 * A picture of its props. */
export function KeyChooser(props: KeyChooserProps) {
  const { keyName, units } = props;
  const offer = props.offer;
  if (offer.editor === "unit") {
    return (
      <UnitPicker
        label={`Unit of ${props.owner}`}
        sections={pickerSections(props.owner, props.inPlay, units, props.narrow)}
        typed={props.typed}
        onTyped={props.onTyped}
        onPick={(unit) => props.onChosen(rawOf(unit))}
        onClose={props.onPickerClosed}
        note={props.note}
        isDisabled={props.busy}
        autoFocus={props.focus}
        menuTrigger={props.pickerTrigger}
      />
    );
  }
  const sections = chooserSections(offer, props.owner, keyName, props.narrow);
  return (
    <div className="key-chooser">
      <ComboBox
        label={`${label(keyName)} of ${props.owner}`}
        inputValue={props.typed}
        onInputChange={props.onTyped}
        sections={sections}
        onPick={(id) => {
          const chosen = sections.flatMap((section) => section.choices).find((e) => e.id === id);
          if (chosen !== undefined) props.onChosen(chosen.raw);
        }}
        onEnter={(text) => {
          const raw = enteredValue(sections, keyName, text);
          if (raw !== undefined) props.onChosen(raw);
        }}
        onClose={props.onPickerClosed}
        note={props.note}
        isDisabled={props.busy}
        autoFocus={props.focus}
        menuTrigger={props.pickerTrigger}
      />
      {offer.editor === "limits" && (
        <div className="key-range">
          <label>
            Min
            <input
              type="text"
              inputMode="decimal"
              value={props.range.min}
              disabled={props.busy}
              onChange={(event) => props.onRange({ ...props.range, min: event.target.value })}
            />
          </label>
          <label>
            Max
            <input
              type="text"
              inputMode="decimal"
              value={props.range.max}
              disabled={props.busy}
              onChange={(event) => props.onRange({ ...props.range, max: event.target.value })}
            />
          </label>
        </div>
      )}
    </div>
  );
}

/** The key as the field's label spells it: `x_axis` reads "X axis". */
function label(key: string): string {
  const words = key.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
