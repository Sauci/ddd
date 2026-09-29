import { useState } from "react";
import type { PlanReply } from "../api/types";
import { ADD_RASTER, ADD_SECTION } from "../stories/fixtures";
import { SharedAddView } from "./SharedAddView";

export default { title: "Components / SharedAddView" };

interface Props {
  /** What the Vocabulary field starts on: "" for the form the Declare an entry button opens. */
  vocabulary?: string;
  /** What the Name field starts on: a route's own name, or "" for a form opened by the button. */
  typed?: string;
  raw?: string;
  access?: string;
  alignment?: string;
  event?: string;
  plan?: PlanReply;
}

/** The form over one scenario's fixtures, holding its own fields as SharedPage.tsx keeps them -
 * the chooser included, so that what the form draws follows from what is in its own field. */
function FormStory({
  vocabulary: chosen = "",
  typed: name = "",
  raw: value = "",
  access: initialAccess = "",
  alignment: initialAlignment = "",
  event: initialEvent = "",
  plan,
}: Props) {
  const [vocabulary, setVocabulary] = useState(chosen);
  const [typed, setTyped] = useState(name);
  const [raw, setRaw] = useState(value);
  const [access, setAccess] = useState(initialAccess);
  const [alignment, setAlignment] = useState(initialAlignment);
  const [event, setEvent] = useState(initialEvent);
  const [changesShown, setChangesShown] = useState(false);
  return (
    <SharedAddView
      vocabulary={vocabulary}
      onVocabulary={setVocabulary}
      typed={typed}
      onTyped={setTyped}
      raw={raw}
      onRaw={setRaw}
      access={access}
      onAccess={setAccess}
      alignment={alignment}
      onAlignment={setAlignment}
      event={event}
      onEvent={setEvent}
      plan={plan ?? null}
      refusal={null}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => undefined}
      busy={false}
      onClose={() => undefined}
    />
  );
}

/** The form as the table's Declare an entry button opens it: the chooser unset, no vocabulary
 * named in the title, and not a field beyond it - which of them a reader is asked for is the
 * first thing this form has to be told. */
export const NothingChosenYet = () => <FormStory />;

/** The chooser on constants, as `unknown-constant`'s route leaves it (spec 5.3): the name filled
 * in from the address, a name and a value to state, and no value typed yet, so nothing is
 * previewed. */
export const DeclaringAConstant = () => <FormStory vocabulary="constants" typed="PRESSURE_CELLS" />;

/** The chooser on sections, where the same form asks for three fields instead of two: both keys
 * the model defaults for neither, with .eol_log's declaration previewed under them - the line
 * naming the file it is appended to, and the button that writes it. */
export const DeclaringASection = () => (
  <FormStory
    vocabulary="sections"
    typed=".eol_log"
    access="read-write"
    alignment="8"
    plan={ADD_SECTION}
  />
);

/** The chooser on rasters, where the same form asks for one field beyond the name: the model
 * defaults `cycle` and `description` both, so `event` is all `add` requires (`RASTERS.required`).
 * 20ms's declaration is previewed under it - and it is an entry with no `cycle` key at all, which
 * is the shape `_entry_text`'s own filter exists to write: a raster that is not cyclic is a real
 * kind of raster, and the panel this form opens onto is where a reader states one if there is one
 * to state. It is also where `unknown-raster`'s route arrives - UNKNOWN_RASTER names 20ms, which
 * no file declares, so its finding leads here with the name already filled in. */
export const DeclaringARaster = () => (
  <FormStory vocabulary="rasters" typed="20ms" event="3" plan={ADD_RASTER} />
);
