import type { PlanReply } from "../api/types";
import { adoptionSentence } from "../lib/projectUnits";
import { consequence, shownChanges } from "../lib/units";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { Panel } from "../ui/Panel";
import { Changes } from "./Changes";

export interface AdoptBannerViewProps {
  /** How many units adoption would list: 0 for a project that states none. */
  adoptable: number;
  /** Whether the project has a units file already - one listing no unit, adoption being offered
   * - which opts it in all the same: the sentence then says no stated unit is in the vocabulary,
   * rather than that none is checked. */
  hasUnitsFile: boolean;
  /** The adoption's plan once it has come; `null` while it is asked for, or when it was refused. */
  plan: PlanReply | null;
  /** Why the plan was refused, or why applying it was; `null` when neither was. */
  refusal: string | null;
  /** Opens the adoption's preview in the panel beside the table. */
  onShowChanges: () => void;
  onAdopt: () => void;
  /** Adopting, or the server stopped: nothing can be adopted. */
  busy: boolean;
}

/** The banner above the table of a project whose units files list no unit (spec 5.3): a picture
 * of its props. */
export function AdoptBannerView({
  adoptable,
  hasUnitsFile,
  plan,
  refusal,
  onShowChanges,
  onAdopt,
  busy,
}: AdoptBannerViewProps) {
  return (
    <Banner tone="warning">
      <div className="adopt-banner">
        <p>{adoptionSentence(adoptable, hasUnitsFile)}</p>
        {plan !== null && plan.changes.length > 0 && (
          <div className="adopt-actions">
            <Button variant="link" onPress={onShowChanges}>
              Show changes
            </Button>
            <Button variant="primary" isDisabled={busy} onPress={onAdopt}>
              {adoptLabel(adoptable)}
            </Button>
          </div>
        )}
      </div>
      {refusal !== null && <p className="adopt-refusal">{refusal}</p>}
    </Banner>
  );
}

export interface AdoptPanelViewProps {
  adoptable: number;
  plan: PlanReply;
  onAdopt: () => void;
  busy: boolean;
  /** Closes the preview: its Close and its Hide changes alike. */
  onClose: () => void;
}

/** The adoption's preview in the panel beside the table (spec 5.3): the new file and the project
 * description's new line, or the entries a units file declaring nothing is filled with, then
 * Adopt. A picture of its props. */
export function AdoptPanelView({ adoptable, plan, onAdopt, busy, onClose }: AdoptPanelViewProps) {
  return (
    <Panel title="Adopt a vocabulary" meta={consequence(plan.changes)} onClose={onClose}>
      <Changes changes={shownChanges(plan.changes)} />
      <div className="panel-actions">
        <Button variant="link" onPress={onClose}>
          Hide changes
        </Button>
        <Button variant="primary" isDisabled={busy} onPress={onAdopt}>
          {adoptLabel(adoptable)}
        </Button>
      </div>
    </Panel>
  );
}

function adoptLabel(adoptable: number): string {
  return `Adopt ${adoptable} unit${adoptable === 1 ? "" : "s"}`;
}
