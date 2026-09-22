import { useState } from "react";
import type { Finding, FixReply, State } from "../api/types";
import { noRouteReason, routeHref, routeLabel } from "../lib/findings";
import {
  DID_NOT_LOAD,
  ID_FIX,
  MISSING_ID,
  PROJECT_FINDINGS,
  STORAGE_MISMATCH,
  UNKNOWN_RPM_FINDING,
} from "../stories/fixtures";
import { FindingPanelView } from "./FindingPanelView";

export default { title: "Components / FindingPanelView" };

interface Props {
  finding: Finding;
  state: State;
  fixes?: FixReply | null;
  /** The fix chosen from the start, so `FixChosen` and `Refused` open already previewing it. */
  chosen?: string;
  changesShown?: boolean;
  refusal?: string | null;
}

/** The panel over one scenario's fixtures, with its own choice and Show changes: `label`, `href`
 * and `reason` are what `../lib/findings` says of the finding, exactly as the tab itself will
 * ask before handing them down. */
function View({
  finding,
  state,
  fixes = null,
  chosen: initiallyChosen,
  changesShown: initiallyShown = false,
  refusal = null,
}: Props) {
  const [chosen, setChosen] = useState<string | undefined>(initiallyChosen);
  const [changesShown, setChangesShown] = useState(initiallyShown);
  return (
    <FindingPanelView
      finding={finding}
      label={routeLabel(finding, state)}
      href={routeHref(finding)}
      reason={noRouteReason(finding, state)}
      onOpen={() => undefined}
      fixes={fixes}
      chosen={chosen}
      onChoose={setChosen}
      changesShown={changesShown}
      onChangesShown={setChangesShown}
      onApply={() => undefined}
      refusal={refusal}
      busy={false}
      onClose={() => undefined}
    />
  );
}

/** A finding with notes as well as a route: the declaration it was compared against, and the
 * file that holds it. */
export const LeadsToAVariable = () => <View finding={STORAGE_MISMATCH} state={PROJECT_FINDINGS} />;

export const LeadsToAUnit = () => <View finding={UNKNOWN_RPM_FINDING} state={PROJECT_FINDINGS} />;

export const LeadsNowhere = () => <View finding={DID_NOT_LOAD} state={PROJECT_FINDINGS} />;

export const WithAFix = () => <View finding={MISSING_ID} state={PROJECT_FINDINGS} fixes={ID_FIX} />;

export const FixChosen = () => (
  <View
    finding={MISSING_ID}
    state={PROJECT_FINDINGS}
    fixes={ID_FIX}
    chosen="Give 'ValueA' an id"
    changesShown
  />
);

export const Refused = () => (
  <View
    finding={MISSING_ID}
    state={PROJECT_FINDINGS}
    fixes={ID_FIX}
    chosen="Give 'ValueA' an id"
    refusal="sensor_hub.ddd.json changed on disk, so nothing was written. The panel now shows the file as it is."
  />
);
