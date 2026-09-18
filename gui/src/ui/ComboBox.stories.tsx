import { useState } from "react";
import { ComboBox, type ComboSection } from "./ComboBox";

export default { title: "UI / ComboBox" };

const SECTIONS: ComboSection[] = [
  {
    id: "declared",
    title: "Declared for ValueA",
    choices: [
      { id: "declared:%", label: "%", detail: "SensorHub, UserInterface" },
      { id: "declared:rpm", label: "rpm", detail: "Controller" },
    ],
  },
  { id: "none", title: "No unit", choices: [{ id: "none:", label: "no unit", detail: "" }] },
];

/** The field over a caller whose own value is `%`: what is typed is dropped when the list
 * closes, as ComboBox's contract asks of every caller. */
function Field({ open = false, note }: { open?: boolean; note?: string }) {
  const [typed, setTyped] = useState<string | undefined>(undefined);
  return (
    <ComboBox
      label="Unit of ValueA"
      inputValue={typed ?? "%"}
      onInputChange={setTyped}
      sections={SECTIONS}
      onPick={() => undefined}
      onEnter={() => undefined}
      onClose={() => setTyped(undefined)}
      note={note}
      autoFocus={open ? 1 : null}
      // The list only opens on focus when asked to, which is what photographs it open.
      menuTrigger={open ? "focus" : "input"}
    />
  );
}

export const Closed = () => <Field />;
export const Open = () => <Field open />;
export const WithNote = () => <Field note="Not one of this project's units" />;
