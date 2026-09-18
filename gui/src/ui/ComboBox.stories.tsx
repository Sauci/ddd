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

function Field({ open = false, note }: { open?: boolean; note?: string }) {
  const [value, setValue] = useState("%");
  return (
    <ComboBox
      label="Unit of ValueA"
      inputValue={value}
      onInputChange={setValue}
      sections={SECTIONS}
      onPick={() => undefined}
      note={note}
      autoFocus={open ? 1 : null}
    />
  );
}

export const Closed = () => <Field />;
export const Open = () => <Field open />;
export const WithNote = () => <Field note="Not one of this project's units" />;
