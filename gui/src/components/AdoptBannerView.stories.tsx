import { useState } from "react";
import type { PlanReply, UnitsReply } from "../api/types";
import { hasUnitsFile } from "../lib/projectUnits";
import { ADOPTION, EMPTIED_UNITS, FILLING, UNADOPTED_UNITS } from "../stories/fixtures";
import { AdoptBannerView, AdoptPanelView } from "./AdoptBannerView";
import { UnitsTableView } from "./UnitsTableView";

export default { title: "Components / AdoptBannerView" };

interface Props {
  /** The Units tab's reply: a project with no units file, unless a scenario says otherwise. */
  units?: UnitsReply;
  /** The adoption's plan, as the server answers it for that project. */
  plan?: PlanReply;
  previewing?: boolean;
}

/** The Units tab of a project whose units files list no unit, laid out as UnitsPage.tsx lays it
 * out: the banner, then the table, with the adoption's preview beside it once Show changes opened
 * it. */
function Tab({ units = UNADOPTED_UNITS, plan = ADOPTION, previewing = false }: Props) {
  const [shown, setShown] = useState(previewing);
  return (
    <>
      <AdoptBannerView
        adoptable={units.adoptable ?? 0}
        hasUnitsFile={hasUnitsFile(units)}
        plan={plan}
        refusal={null}
        onShowChanges={() => setShown(true)}
        onAdopt={() => undefined}
        busy={false}
      />
      <div className={shown ? "with-panel" : undefined}>
        <div>
          <UnitsTableView units={units} selected={undefined} onSelect={() => setShown(false)} />
        </div>
        {shown && (
          <AdoptPanelView
            adoptable={units.adoptable ?? 0}
            plan={plan}
            onAdopt={() => undefined}
            busy={false}
            onClose={() => setShown(false)}
          />
        )}
      </div>
    </>
  );
}

export const NoUnitsFile = () => <Tab />;

export const PreviewShown = () => <Tab previewing />;

/** A project whose units file declares nothing - what taking the last unit nothing states out of
 * its vocabulary leaves. The file opts it in all the same, so every unit it states is a row
 * outside the vocabulary carrying its `unknown-unit`, and the banner offers adopting them with
 * its second sentence: no stated unit is in the vocabulary, and adopting lists them in a units
 * file - that one, filled rather than a second written, which Show changes would show. */
export const AUnitsFileDeclaringNothing = () => <Tab units={EMPTIED_UNITS} plan={FILLING} />;
