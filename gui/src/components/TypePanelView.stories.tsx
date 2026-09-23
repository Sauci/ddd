import { useState } from "react";
import type { PlanReply, TypeReply } from "../api/types";
import { textOf, unitLabel } from "../lib/units";
import {
  EXTERNAL_TYPE,
  PROJECT_UNITS,
  SCALAR_TYPE,
  SET_UNIT,
  STRUCT_TYPE,
} from "../stories/fixtures";
import { TypePanelView } from "./TypePanelView";

export default { title: "Components / TypePanelView" };

interface Props {
  reply: TypeReply;
  /** The key whose chooser is open, or unopened when left out. */
  on?: string;
  preview?: PlanReply | null;
  shown?: boolean;
  refusal?: string;
  /** What the Rename field starts on: the type's own name, unless a scenario means to show it
   * already typed - a refusal only ever appears with the offending name still in the field. */
  renameTo?: string | null;
}

/** The panel over one scenario's fixtures, with its own selection, typing, description and
 * rename state - as TypePanel.tsx (Task 9) will keep them.
 *
 * As in VariablePanel.tsx: `typed` stays `undefined` until the reader edits the field, so it
 * shows the label of the type's own value until one is chosen. */
function PanelStory({
  reply,
  on,
  preview = null,
  shown = false,
  refusal,
  renameTo: renameSeed = null,
}: Props) {
  const [selected, setSelected] = useState<string | undefined>(on);
  const [typed, setTyped] = useState<string | undefined>(undefined);
  const [chosen, setChosen] = useState<string | null | undefined>(undefined);
  const [range, setRange] = useState({ min: "", max: "" });
  const [description, setDescription] = useState(reply.description);
  const [renameTo, setRenameTo] = useState<string | null>(renameSeed);
  const [changesShown, setChangesShown] = useState(shown);
  const select = (key: string | undefined) => {
    setSelected(key);
    setTyped(undefined);
    setChosen(undefined);
    setRange({ min: "", max: "" });
    setChangesShown(false);
  };
  return (
    <TypePanelView
      type={reply}
      units={PROJECT_UNITS}
      selected={selected}
      onSelect={select}
      typed={typed ?? startingLabel(reply, selected, chosen)}
      narrow={typed ?? ""}
      onTyped={setTyped}
      onChosen={(raw) => {
        setChosen(raw);
        setTyped(undefined);
      }}
      onPickerClosed={() => setTyped(undefined)}
      range={range}
      onRange={setRange}
      description={description}
      onDescription={setDescription}
      renameTo={renameTo}
      onRenameTo={setRenameTo}
      preview={preview}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => undefined}
      onOpen={() => undefined}
      refusal={refusal ?? null}
      busy={false}
      onClose={() => undefined}
    />
  );
}

/** What the chooser's field reads while nothing is being typed: the value settled on, labelled
 * the way its editor shows one - only "unit" is ever opened here, as the spec's own six
 * scenarios ask for, but every editor at least falls back to the raw text moved to json. */
function startingLabel(
  reply: TypeReply,
  key: string | undefined,
  chosen: string | null | undefined,
): string {
  if (key === undefined) return "";
  const offer = reply.keys.find((entry) => entry.key === key);
  const raw = chosen === undefined ? (offer?.values[0]?.raw ?? null) : chosen;
  const value = textOf(raw ?? undefined);
  return offer?.editor === "unit" ? unitLabel(value) : (value ?? "");
}

/** Temperature_t: its four keys and their values, and Description - closed, nothing selected. */
export const AScalar = () => <PanelStory reply={SCALAR_TYPE} />;

/** The unit row selected: the picker open on degC, in play as the type's own value. */
export const AKeyChosen = () => <PanelStory reply={SCALAR_TYPE} on="unit" preview={SET_UNIT} />;

/** The same, with Show changes open: the one hunk that moves degC to K. */
export const ChangesShown = () => (
  <PanelStory reply={SCALAR_TYPE} on="unit" preview={SET_UNIT} shown />
);

/** Sensor_t: no "What it fixes" table, its four members, one with dimensions, its two uses. */
export const AStructure = () => <PanelStory reply={STRUCT_TYPE} />;

/** DriverStatus_t: an external's own header line, and its one use inside Sensor_t. */
export const AnExternal = () => <PanelStory reply={EXTERNAL_TYPE} />;

/** Renaming Temperature_t to a name already declared: `rename_problem`'s own sentence, where
 * the consequence line would otherwise stand - no Show changes, no Apply under it. */
export const RenameRefused = () => (
  <PanelStory
    reply={SCALAR_TYPE}
    renameTo="Sample_t"
    refusal="'Sample_t' is the name of the type 'Sample_t', which shares c's namespace with the variables"
  />
);
