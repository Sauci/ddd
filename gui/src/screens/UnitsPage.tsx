import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getUnits, postEdit } from "../api/client";
import type { State } from "../api/types";
import { AdoptBannerView, AdoptPanelView } from "../components/AdoptBannerView";
import { UnitsTableView } from "../components/UnitsTableView";
import { planEdit, tabTitle } from "../lib/projectUnits";
import { Banner } from "../ui/Banner";
import { refusalOf, UnitPanel, usePlan } from "./UnitPanel";

interface Props {
  state: State | null;
  /** The unit whose panel is open, as the address names it. */
  unit: string | undefined;
  stopped: boolean;
  onUnit: (unit: string | undefined) => void;
}

/** The open project's Units tab (spec 5.1): every unit it states or lists, the panel of the one
 * selected, and adoption for a project with no units file (spec 5.3). */
export function UnitsPage({ state, unit, stopped, onUnit }: Props) {
  const queries = useQueryClient();
  const revision = state?.revision;
  const units = useQuery({
    queryKey: ["units", revision],
    queryFn: () => getUnits(),
    // The table stays while the next revision's units are read: swapped for a loading line on
    // every edit, it lost the reader's place and made the tab flash.
    placeholderData: (previous) => previous,
  });
  // The unit whose panel closed because nothing states or lists it any longer (spec 5.4), named
  // above the table until another unit is selected or the reader leaves the tab.
  const [gone, setGone] = useState<string | null>(null);
  // Whether the adoption's preview is open, in the panel's place beside the table.
  const [previewing, setPreviewing] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const adoptable = units.data?.adoptable ?? null;
  // Asked for as soon as the banner offers it, so that Adopt applies exactly what Show changes
  // shows; a project stating no unit has nothing to adopt, and nothing is asked.
  const adoption = usePlan(
    adoptable !== null && adoptable > 0 ? { action: "adopt" } : null,
    revision,
  );
  const adopt = useMutation({
    mutationFn: () => {
      const edit = adoption.data === undefined ? null : planEdit(adoption.data);
      if (edit === null) throw new Error("there is nothing to adopt");
      return postEdit(edit);
    },
    onMutate: () => setRefused(null),
    onSuccess: () => setPreviewing(false),
    onError: (error) => setRefused(refusalOf(error)),
    // Adopting changes every row and every plan: they are asked for again, and nothing can be
    // adopted a second time while they are.
    onSettled: () =>
      Promise.all([
        queries.invalidateQueries({ queryKey: ["units"] }),
        queries.invalidateQueries({ queryKey: ["unit"] }),
        queries.invalidateQueries({ queryKey: ["unit-plan"] }),
      ]),
  });

  if (units.data === undefined) {
    if (units.isError) return <Banner tone="error">{units.error.message}</Banner>;
    return <p className="quiet">Reading the project's units…</p>;
  }
  const select = (next: string | undefined) => {
    setGone(null);
    setPreviewing(false);
    onUnit(next);
  };
  const preview = unit === undefined && previewing ? (adoption.data ?? null) : null;
  return (
    <>
      <p className="summary">{tabTitle(units.data.units, units.data.vocabulary !== null)}</p>
      {/* A server that stopped answering leaves the table as it was, and says so above it. */}
      {units.isError && <Banner tone="error">{units.error.message}</Banner>}
      {gone !== null && (
        <Banner tone="warning">{gone} is no longer stated or listed in the open project.</Banner>
      )}
      {adoptable !== null && (
        <AdoptBannerView
          adoptable={adoptable}
          plan={adoption.data ?? null}
          refusal={refused ?? adoption.error?.message ?? null}
          onShowChanges={() => {
            select(undefined);
            setPreviewing(true);
          }}
          onAdopt={() => adopt.mutate()}
          busy={stopped || adopt.isPending}
        />
      )}
      <div className={unit !== undefined || preview !== null ? "with-panel" : undefined}>
        <div>
          <UnitsTableView units={units.data} selected={unit} onSelect={select} />
        </div>
        {unit !== undefined ? (
          <UnitPanel
            key={unit}
            name={unit}
            revision={revision}
            stopped={stopped}
            onClose={() => onUnit(undefined)}
            onGone={() => {
              setGone(unit);
              onUnit(undefined);
            }}
            onMoved={select}
          />
        ) : (
          preview !== null && (
            <AdoptPanelView
              adoptable={adoptable ?? 0}
              plan={preview}
              onAdopt={() => adopt.mutate()}
              busy={stopped || adopt.isPending}
              onClose={() => setPreviewing(false)}
            />
          )
        )}
      </div>
    </>
  );
}
