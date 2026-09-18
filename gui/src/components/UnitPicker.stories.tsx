import { useState } from "react";
import { pickerSections } from "../lib/units";
import { DISAGREEING, FREE_UNITS } from "../stories/fixtures";
import { UnitPicker } from "./UnitPicker";

export default { title: "Components / UnitPicker" };

function Field({ open = false }: { open?: boolean }) {
  const [typed, setTyped] = useState("%");
  return (
    <UnitPicker
      name="ValueA"
      sections={pickerSections("ValueA", DISAGREEING.declarations, FREE_UNITS, typed)}
      typed={typed}
      onTyped={setTyped}
      onPick={() => undefined}
      note={undefined}
      isDisabled={false}
      autoFocus={open}
    />
  );
}

export const Closed = () => <Field />;
export const Open = () => <Field open />;
