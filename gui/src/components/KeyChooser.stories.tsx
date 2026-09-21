import { useState } from "react";
import type { VariableReply } from "../api/types";
import { labelOfRaw, limitsOf, startingRaw } from "../lib/variableKeys";
import { DISAGREEING, FREE_UNITS, SHAPED } from "../stories/fixtures";
import { KeyChooser } from "./KeyChooser";

export default { title: "Components / KeyChooser" };

interface Props {
  variable: VariableReply;
  keyName: string;
  /** Opens the list on mount, for a story to photograph it. */
  open?: boolean;
}

/** Mirrors VariablePanel.tsx (Task 6): `typed` stays `undefined` until the reader edits the
 * field, so it shows the label of the value settled on, seeded here with `startingRaw` and
 * `labelOfRaw` exactly as the screen will. */
function Field({ variable, keyName, open = false }: Props) {
  const [chosen, setChosen] = useState<string | null>(startingRaw(variable, keyName));
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [range, setRange] = useState(limitsOf(chosen));
  return (
    <KeyChooser
      variable={variable}
      keyName={keyName}
      units={FREE_UNITS}
      chosen={chosen}
      typed={typed ?? labelOfRaw(variable, keyName, chosen)}
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(raw) => {
        setChosen(raw);
        setTyped(undefined);
        setRange(limitsOf(raw));
      }}
      onPickerClosed={() => setTyped(undefined)}
      range={range}
      onRange={setRange}
      note={undefined}
      busy={false}
      focus={open ? 1 : null}
      pickerTrigger={open ? "focus" : "input"}
    />
  );
}

/** A naming chooser: SHAPED's axis indexes EngineSpeed, and OilPressure is offered beside it. */
export const Names = () => <Field variable={SHAPED} keyName="input" open />;

/** The eleven datatypes, uint8 - already declared - filtered out of the list below it. */
export const Datatypes = () => <Field variable={DISAGREEING} keyName="datatype" open />;

export const TrueOrFalse = () => <Field variable={DISAGREEING} keyName="volatile" open />;

/** SHAPED's two declarations disagree about `limits`: the Min/Max fields start filled with the
 * producer's range. Closed, since the open list's popover would sit exactly where the range
 * fields render and hide them - the same reason a field is normally photographed closed. */
export const Range = () => <Field variable={SHAPED} keyName="limits" />;

/** `conversion` is carried, never composed (spec 2): the list offers only what is declared. */
export const InPlayOnly = () => <Field variable={DISAGREEING} keyName="conversion" open />;
