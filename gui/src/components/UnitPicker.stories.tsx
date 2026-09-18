import { useState } from "react";
import { pickerSections } from "../lib/units";
import { DISAGREEING, FREE_UNITS } from "../stories/fixtures";
import { UnitPicker } from "./UnitPicker";

export default { title: "Components / UnitPicker" };

/** Mirrors VariablePanel.tsx: `typed` stays `undefined` until the reader edits the field, so
 * the field shows the starting unit (here, `%`) while the list stays unnarrowed until something
 * is actually typed - opening the picker must still list everything, not just `%`. */
function Field({ autoFocus = null }: { autoFocus?: number | null }) {
  const [typed, setTyped] = useState<string | undefined>(undefined);
  return (
    <UnitPicker
      name="ValueA"
      sections={pickerSections("ValueA", DISAGREEING.declarations, FREE_UNITS, typed ?? "")}
      typed={typed ?? "%"}
      onTyped={setTyped}
      onPick={() => undefined}
      note={undefined}
      isDisabled={false}
      autoFocus={autoFocus}
    />
  );
}

export const Closed = () => <Field />;
export const Open = () => <Field autoFocus={1} />;
