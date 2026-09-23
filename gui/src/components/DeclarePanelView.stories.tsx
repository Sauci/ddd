import { useState } from "react";
import type { DeclarableReply, PlanReply } from "../api/types";
import { DECLARABLE } from "../stories/fixtures";
import { DeclarePanelView } from "./DeclarePanelView";

export default { title: "Components / DeclarePanelView" };

interface Props {
  reply?: DeclarableReply;
  typed?: string;
  kind?: string;
  scope?: string;
  values?: Record<string, string>;
  dimensions?: string[];
  plan?: PlanReply | null;
  refusal?: string | null;
}

/** The panel over one scenario's starting state, holding what the reader has typed or chosen as
 * DeclarePanel.tsx (Task 8) will: every field's own state, narrowed to nothing until the reader
 * types into it. */
function View({
  reply = DECLARABLE,
  typed: startTyped = "",
  kind: startKind = "",
  scope: startScope = "",
  values: startValues = {},
  dimensions: startDimensions = [],
  plan = null,
  refusal = null,
}: Props) {
  const [typed, setTyped] = useState(startTyped);
  const [kind, setKind] = useState(startKind);
  const [scope, setScope] = useState(startScope);
  const [values, setValues] = useState(startValues);
  const [typed_, setTyped_] = useState<Record<string, string | undefined>>({});
  const [dimensions, setDimensions] = useState(startDimensions);
  const [changesShown, setChangesShown] = useState(false);
  return (
    <DeclarePanelView
      reply={reply}
      typed={typed}
      kind={kind}
      scope={scope}
      values={values}
      typed_={typed_}
      dimensions={dimensions}
      plan={plan}
      refusal={refusal}
      changesShown={changesShown}
      busy={false}
      onTyped={setTyped}
      onKind={setKind}
      onScope={setScope}
      onValue={(key, raw) => setValues((old) => ({ ...old, [key]: raw }))}
      onTyped_={(key, text) => setTyped_((old) => ({ ...old, [key]: text }))}
      onDimensions={setDimensions}
      onChangesShown={setChangesShown}
      onApply={() => undefined}
      onClose={() => undefined}
    />
  );
}

/** Nothing typed yet: the name and scope fields alone, and the sentence asking for a name. */
export const NothingChosenYet = () => <View />;

/** BlockA, one of the nine names Controller could read: no kind or keys, and the sentence names
 * UserInterface as its producer. */
export const AVariableChosenToRead = () => <View typed="BlockA" scope="input" />;

/** Pressure, a name the project has never seen, as a measurement: the storage it names
 * (`datatype`) carries the identity conversion with it, invisibly - `keysOf` offers no field for
 * that key. */
export const ANewMeasurement = () => (
  <View
    typed="Pressure"
    kind="measurement"
    scope="input"
    values={{ volatile: "true", datatype: '"uint8"' }}
  />
);

/** CurveC's `axis` key is the `editor: "name"` chooser, offering the project's own axes -
 * AxisA and AxisB - rather than free text. */
export const ANewCurve = () => (
  <View
    typed="CurveC"
    kind="curve"
    scope="input"
    values={{ volatile: "true", axis: '"AxisA"', datatype: '"float32"' }}
  />
);

/** BlockC's shape, drawn by Task 5's `DimensionsField`, sits among the kind's other keys rather
 * than beside them - it is simply the key whose row the form draws differently. */
export const ANewValueBlock = () => (
  <View
    typed="BlockC"
    kind="value_block"
    scope="input"
    values={{ volatile: "true", datatype: '"uint8"' }}
    dimensions={["4", "8"]}
  />
);

/** ValueA is not one of the nine names Controller could read, so the form treats it as a new
 * name - the hazard spec 5.2 states rather than hides - until the server refuses it. */
export const ANameTheProjectRefuses = () => (
  <View
    typed="ValueA"
    kind="measurement"
    scope="input"
    values={{ volatile: "true", datatype: '"uint8"' }}
    refusal="'ValueA' is already declared by this project"
  />
);
