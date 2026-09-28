import { useState } from "react";
import type { PlanReply } from "../api/types";
import { ADD_SECTION } from "../stories/fixtures";
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
  plan,
}: Props) {
  const [vocabulary, setVocabulary] = useState(chosen);
  const [typed, setTyped] = useState(name);
  const [raw, setRaw] = useState(value);
  const [access, setAccess] = useState(initialAccess);
  const [alignment, setAlignment] = useState(initialAlignment);
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
