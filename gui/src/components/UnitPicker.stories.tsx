import { useState } from "react";
import { pickerSections } from "../lib/units";
import { DISAGREEING, FREE_UNITS } from "../stories/fixtures";
import { UnitPicker } from "./UnitPicker";

export default { title: "Components / UnitPicker" };

/** Mirrors VariablePanel.tsx: `typed` stays `undefined` until the reader edits the field, and
 * again once the list closes, so the field shows the unit settled on (here, `%`) while the list
 * stays unnarrowed until something is actually typed - opening the picker must still list
 * everything, not just `%`. */
function Field({ open = false }: { open?: boolean }) {
  const [typed, setTyped] = useState<string | undefined>(undefined);
  return (
    <UnitPicker
      name="ValueA"
      sections={pickerSections("ValueA", DISAGREEING.declarations, FREE_UNITS, typed ?? "")}
      typed={typed ?? "%"}
      onTyped={setTyped}
      onPick={() => undefined}
      onClose={() => setTyped(undefined)}
      note={undefined}
      isDisabled={false}
      autoFocus={open ? 1 : null}
      menuTrigger={open ? "focus" : "input"}
    />
  );
}

export const Closed = () => <Field />;
export const Open = () => <Field open />;
