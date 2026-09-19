import { useState } from "react";
import { ADOPTION, UNADOPTED_UNITS } from "../stories/fixtures";
import { AdoptBannerView, AdoptPanelView } from "./AdoptBannerView";
import { UnitsTableView } from "./UnitsTableView";

export default { title: "Components / AdoptBannerView" };

/** The Units tab of a project with no units file, laid out as UnitsPage.tsx lays it out: the
 * banner, then the table, with the adoption's preview beside it once Show changes opened it. */
function Tab({ previewing = false }: { previewing?: boolean }) {
  const [shown, setShown] = useState(previewing);
  return (
    <>
      <AdoptBannerView
        adoptable={UNADOPTED_UNITS.adoptable ?? 0}
        plan={ADOPTION}
        refusal={null}
        onShowChanges={() => setShown(true)}
        onAdopt={() => undefined}
        busy={false}
      />
      <div className={shown ? "with-panel" : undefined}>
        <div>
          <UnitsTableView
            units={UNADOPTED_UNITS}
            selected={undefined}
            onSelect={() => setShown(false)}
          />
        </div>
        {shown && (
          <AdoptPanelView
            adoptable={UNADOPTED_UNITS.adoptable ?? 0}
            plan={ADOPTION}
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
