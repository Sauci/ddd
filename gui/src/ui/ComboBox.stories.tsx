import { useState } from "react";
import type { DeclarableName } from "../api/types";
import { nameList } from "../lib/declarations";
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

/** 1,200 names a large project could offer a component, `C00000_O0000` on, twelve to a component. */
const MANY_NAMES: DeclarableName[] = Array.from({ length: 1200 }, (_, index) => {
  const component = `C${String(Math.floor(index / 12)).padStart(5, "0")}`;
  return {
    name: `${component}_O${String(index % 12).padStart(4, "0")}`,
    kind: "measurement",
    producer: component,
    scopes: ["input"],
  };
});

/** A list drawn to a cap, as the declare form's Name list is (`nameList`, lib/declarations.ts):
 * fifty of the 1,200 names, scrolling in the list's own box, and the line at its foot saying how
 * many more match. Opened on focus with nothing typed, which is what photographs it open. */
export const OpenToACap = () => {
  const [typed, setTyped] = useState("");
  const names = nameList(MANY_NAMES, typed);
  return (
    <ComboBox
      label="Name"
      inputValue={typed}
      onInputChange={setTyped}
      sections={names.sections}
      footnote={names.footnote}
      onPick={setTyped}
      onEnter={setTyped}
      onClose={() => undefined}
      autoFocus={1}
      menuTrigger="focus"
    />
  );
};
